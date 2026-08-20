"""
The vector store — our own Vanna persistence layer.

Vanna's VannaBase defines the storage interface; we implement it over the
data_vectors_<dim> bucket tables (the chunk_vectors pattern), so every
vector in the platform lives in the same house: created by create_all,
HNSW cosine index, GENERATED tsvector for the keyword branch, strictly
partitioned by data_source_id.

Two things this buys over Vanna's stock stores:
  · HYBRID retrieval (vector + FTS + RRF) instead of cosine-only
  · the same embedding resolution as the RAG spaces (company / own key /
    local), so an agent's embedding model is the one chosen in its UI

Row taxonomy — `kind` is the index, `tag` is the provenance:
    kind = ddl | sql | business          (the three RAG indexes)
    tag  = NULL for schema-derived rows, <file name> for document chunks
           → re-training wipes only tag IS NULL, so uploaded documents
             survive, and deleting a document removes exactly its chunks.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def embed_text(source_id: str, text: str, use_cache: bool = True) -> list[float]:
    """Embedding through the platform factory (company → own key → local),
    behind the RAG query-embedding cache — repeated questions (FAQ phrasing,
    evaluation runs) skip the model call entirely."""
    from app.database import SessionLocal
    from app.models.data_agent import DataSource
    from app.services.embedding_factory import embed_query
    from app.services.retrieval import embed_cache

    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(DataSource.id == source_id).first()
        model_id = (f"{getattr(source, 'embedding_provider', '')}:"
                    f"{getattr(source, 'embedding_model', '')}")
        if use_cache:
            hit = embed_cache.get(model_id, text)
            if hit is not None:
                return hit
        vec = embed_query(db, source, text)
        if use_cache:
            embed_cache.put(model_id, text, vec, 3600)
        return vec
    finally:
        db.close()


def resolve_dim(db, source) -> int:
    """The source's embedding dimension — probed once, then stored."""
    if source.embedding_dim:
        return int(source.embedding_dim)
    dim = len(embed_text(source.id, "dimension probe"))
    source.embedding_dim = dim
    db.commit()
    return dim


def bucket_model(db, source):
    """The data_vectors_<dim> mapped class for this source (table ensured —
    an off-catalog dimension gets its table on first use)."""
    from app.database import engine
    from app.models.data_vector import data_vector_model
    model = data_vector_model(resolve_dim(db, source))
    model.__table__.create(bind=engine, checkfirst=True)
    return model


def wipe(db, source, kinds=None, schema_only: bool = True) -> int:
    """Delete indexed knowledge. schema_only keeps document chunks (tag set)."""
    model = bucket_model(db, source)
    q = db.query(model).filter(model.data_source_id == source.id)
    if kinds:
        q = q.filter(model.kind.in_(list(kinds)))
    if schema_only:
        q = q.filter(model.tag.is_(None))
    n = q.delete(synchronize_session=False)
    db.commit()
    return n


def build_store_class():
    """Deferred: importing vanna pulls heavy deps — never at module import."""
    import pandas as pd
    from vanna.base import VannaBase

    from app.services.data_agent.config import (KIND_BUSINESS, KIND_DDL,
                                                KIND_SQL, RetrievalConfig)

    class AgentFlowVectorStore(VannaBase):
        """Vanna persistence + HYBRID retrieval over data_vectors_<dim>."""

        def __init__(self, source_id: str, config=None):
            VannaBase.__init__(self, config=config)
            self._source_id = source_id
            self._retrieval: RetrievalConfig = (config or {}).get(
                "retrieval_config") or RetrievalConfig()
            self.n_results = self._retrieval.n_ddl

        # ── embeddings ──
        def generate_embedding(self, data: str, **kwargs) -> list[float]:
            return embed_text(self._source_id, data)

        # ── writes ──
        def _session(self):
            from app.database import SessionLocal
            return SessionLocal()

        def _insert(self, kind: str, content: str, question=None, tag=None) -> str:
            from app.models.data_agent import DataSource
            db = self._session()
            try:
                source = db.query(DataSource).filter(
                    DataSource.id == self._source_id).first()
                model = bucket_model(db, source)
                text_for_vector = f"{question}\n{content}" if question else content
                row = model(data_source_id=self._source_id, kind=kind,
                            content=content, question=question, tag=tag,
                            embedding=self.generate_embedding(text_for_vector))
                db.add(row)
                db.commit()
                return row.id
            finally:
                db.close()

        def add_ddl(self, ddl: str, **kwargs) -> str:
            return self._insert(KIND_DDL, ddl, tag=kwargs.get("tag"))

        def add_documentation(self, documentation: str, **kwargs) -> str:
            return self._insert(KIND_BUSINESS, documentation, tag=kwargs.get("tag"))

        def add_question_sql(self, question: str, sql: str, **kwargs) -> str:
            return self._insert(KIND_SQL, sql, question=question)

        # ── reads: HYBRID (vector + keyword + RRF), one index at a time ──
        def _search(self, kind: str, question: str) -> list:
            from app.models.data_agent import DataSource
            from app.services.data_agent.retrieval.hybrid import search_kind
            db = self._session()
            try:
                source = db.query(DataSource).filter(
                    DataSource.id == self._source_id).first()
                model = bucket_model(db, source)
                emb = self.generate_embedding(question)      # hybrid: always
                chunks = search_kind(db, model, source, kind, question,
                                     emb, self._retrieval)
                ids = [c.chunk_id for c in chunks]
                if not ids:
                    return []
                rows = {r.id: r for r in db.query(model)
                        .filter(model.id.in_(ids)).all()}
                return [rows[i] for i in ids if i in rows]   # keep fused order
            finally:
                db.close()

        def get_related_ddl(self, question: str, **kwargs) -> list:
            return [r.content for r in self._search(KIND_DDL, question)]

        def get_related_documentation(self, question: str, **kwargs) -> list:
            """Business context = schema-derived knowledge (this store) +
            uploaded DOCUMENTS (the platform RAG engine over the agent's
            hidden knowledge space)."""
            out = [r.content for r in self._search(KIND_BUSINESS, question)]
            db = self._session()
            try:
                from app.models.data_agent import DataSource
                from app.services.data_agent.retrieval.hybrid import \
                    retrieve_documents
                source = db.query(DataSource).filter(
                    DataSource.id == self._source_id).first()
                out += [c.content for c in
                        retrieve_documents(db, source, question, self._retrieval)]
            except Exception as e:
                logger.warning(f"[DATA-AGENT/docs] {e!r}")
            finally:
                db.close()
            return out

        def get_similar_question_sql(self, question: str, **kwargs) -> list:
            return [{"question": r.question, "sql": r.content}
                    for r in self._search(KIND_SQL, question)]

        # ── management (Training-data panel) ──
        def get_training_data(self, **kwargs):
            from app.models.data_agent import DataSource
            db = self._session()
            try:
                source = db.query(DataSource).filter(
                    DataSource.id == self._source_id).first()
                model = bucket_model(db, source)
                rows = (db.query(model)
                        .filter(model.data_source_id == self._source_id).all())
                return pd.DataFrame([{
                    "id": r.id, "training_data_type": r.kind,
                    "question": r.question, "content": r.content, "tag": r.tag,
                } for r in rows])
            finally:
                db.close()

        def remove_training_data(self, id: str, **kwargs) -> bool:
            from app.models.data_agent import DataSource
            db = self._session()
            try:
                source = db.query(DataSource).filter(
                    DataSource.id == self._source_id).first()
                model = bucket_model(db, source)
                n = (db.query(model)
                     .filter(model.id == id,
                             model.data_source_id == self._source_id)
                     .delete(synchronize_session=False))
                db.commit()
                return n > 0
            finally:
                db.close()

    return AgentFlowVectorStore
