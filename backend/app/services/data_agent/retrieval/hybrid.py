"""
Hybrid retrieval over the three knowledge indexes (the "RAG Index" of the
architecture): prompt→SQL pairs · DDLs · Business.

Each index is searched SEPARATELY — a pooled search would let 30 DDL blocks
crowd out 3 glossary entries, and then the prompt loses exactly the piece
that carries the business meaning.

Per index, two branches (the RAG-space pattern, reused verbatim):

    vector    pgvector cosine on the HNSW index      → semantic match
    keyword   PostgreSQL FTS on the GENERATED tsvector → exact literal match

Rare literal tokens — table names, column names, KPI codes — are precisely
what embeddings handle worst and what schema knowledge is made of, so the
keyword branch matters MORE here than in document RAG.

The two rankings are merged with Reciprocal Rank Fusion (the existing
fusion.py — no score normalization needed) and optionally re-ordered by the
existing cross-encoder reranker.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import func, or_, text

from app.services.data_agent.config import (KIND_BUSINESS, KINDS,
                                            RetrievalConfig)
from app.services.retrieval.fusion import fuse
from app.services.retrieval.types import Query, RetrievedChunk

logger = logging.getLogger(__name__)

# ── Query enhancement, memoized per question ──────────────────────────────
# The RAG engine transforms the query once per question (in its keyword
# branch). Here THREE indexes are searched for one question, so without a
# memo the same LLM call would run three times. Tiny TTL cache: one call per
# question, reused by the DDL / SQL / Business searches and by the document
# branch.
_ENHANCE_TTL = 300.0
_ENHANCE_MAX = 256
_enhance_cache: dict[tuple[str, str], tuple[float, str]] = {}


def _enhanced(db, source, question: str, cfg: RetrievalConfig) -> str:
    """The question the KEYWORD branch searches with — rewritten, spell-fixed
    and de-noised by the agent's own LLM when enabled, exactly like the RAG
    engine. Any failure keeps the original question."""
    if not cfg.transform_enabled or not (question or "").strip():
        return question
    key = (str(source.id), question)
    now = time.time()
    hit = _enhance_cache.get(key)
    if hit and now - hit[0] < _ENHANCE_TTL:
        return hit[1]
    try:
        from app.services.retrieval.transforms import enhance_query
        q = Query(raw=question)
        enhance_query(db, source, q)          # mutates q in place
        out = (q.cleaned or question).strip() or question
    except Exception as e:
        logger.warning(f"[DATA-AGENT/transform] {e!r} — original question kept")
        out = question
    if len(_enhance_cache) >= _ENHANCE_MAX:
        _enhance_cache.clear()
    _enhance_cache[key] = (now, out)
    return out


def _as_chunks(rows, method: str) -> list[RetrievedChunk]:
    """Adapt store rows to the shared RetrievedChunk so fusion/rerank —
    written for the RAG pipeline — work unchanged."""
    return [RetrievedChunk(
        chunk_id=r.id, content=r.content, document_id=r.kind,
        page=1, chunk_index=0, chunk_type=r.kind,
        score=0.0, method=method,
    ) for r in rows]


def _vector_branch(db, model, source_id, kind, embedding, k):
    return (db.query(model)
            .filter(model.data_source_id == source_id, model.kind == kind)
            .order_by(model.embedding.cosine_distance(embedding))
            .limit(int(k)).all())


def _keyword_branch(db, model, source_id, kind, question, k):
    """websearch_to_tsquery + ts_rank on the GIN-indexed tsvector, with an
    OR-of-words fallback so a long question still matches something."""
    words = [w for w in (question or "").split() if len(w) > 1]
    if not words:
        return []
    candidates = [question, " OR ".join(words)]
    for q in candidates:
        try:
            tsq = func.websearch_to_tsquery("simple", q)
            rows = (db.query(model)
                    .filter(model.data_source_id == source_id,
                            model.kind == kind,
                            model.content_tsv.op("@@")(tsq))
                    .order_by(func.ts_rank(model.content_tsv, tsq).desc())
                    .limit(int(k)).all())
            if rows:
                return rows
        except Exception as e:
            logger.debug(f"[DATA-AGENT/keyword] {e!r}")
            db.rollback()
    return []


def search_kind(db, model, source, kind: str, question: str,
                embedding, cfg: RetrievalConfig) -> list:
    """One index → the fused, capped list of chunks."""
    top_n = cfg.top_n(kind)
    if top_n <= 0:
        return []
    source_id = source.id if hasattr(source, "id") else str(source)

    # Both branches, always — hybrid is the design, not an option. The vector
    # branch is skipped only when no embedding could be produced (model
    # unavailable), and keyword search alone keeps the agent answering.
    branches: dict[str, list] = {}
    if embedding is not None:
        branches["vector"] = _as_chunks(
            _vector_branch(db, model, source_id, kind, embedding, cfg.fetch_k),
            "vector")
    # Like the RAG engine, only the keyword branch searches the enhanced
    # query — the vector branch embeds the question as the user asked it.
    kw_question = _enhanced(db, source, question, cfg) if hasattr(source, "id") else question
    branches["keyword"] = _as_chunks(
        _keyword_branch(db, model, source_id, kind, kw_question, cfg.keyword_k),
        "keyword")

    if not branches:
        return []
    if len(branches) == 1:
        fused = list(next(iter(branches.values())))
    else:
        fused = fuse(branches, rrf_k=cfg.rrf_k)

    if len(fused) > 1:
        fused = _rerank(db, cfg, question, fused)
    return fused[:top_n]


def _rerank(db, cfg: RetrievalConfig, question: str, chunks: list) -> list:
    """Cross-encoder re-ordering — the RAG reranker, same models and the same
    key resolution (company provider → own encrypted key). Non-fatal."""
    try:
        from types import SimpleNamespace

        from app.services.retrieval.rerank import rerank, resolve_reranker_key
        key = ""
        if cfg.reranker_provider == "voyage":
            # resolve_reranker_key reads `reranker_api_key_enc` off the space;
            # the agent keeps its own key inside retrieval_params instead.
            holder = SimpleNamespace(
                reranker_api_key_enc=cfg.reranker_api_key_enc or None)
            key = resolve_reranker_key(db, holder, cfg.reranker_key_source)
        shim = SimpleNamespace(reranker_provider=cfg.reranker_provider,
                               reranker_model=cfg.reranker_model,
                               reranker_api_key=key,
                               rerank_top_n=cfg.rerank_top_n,
                               rerank_char_cap=cfg.rerank_char_cap)
        return rerank(shim, question, chunks)
    except Exception as e:
        logger.warning(f"[DATA-AGENT/rerank] {e!r} — keeping fusion order")
        return chunks


def retrieve_documents(db, source, question: str, cfg: RetrievalConfig) -> list:
    """Business DOCUMENTS — retrieved by the platform's RAG engine over the
    agent's hidden knowledge space. Whole pipeline reused as-is: hybrid
    vector + FTS, RRF, optional rerank, context assembly."""
    from app.services.data_agent.knowledge.space import get_space
    from app.services.retrieval import retrieve as rag_retrieve
    from app.services.retrieval.config import load_config

    space = get_space(db, source)
    if space is None:
        return []
    try:
        rcfg = load_config(space)
        rcfg.top_k = max(1, int(cfg.n_business))
        # The agent's panel owns these — the hidden space is never configured
        # directly, so its own values must not win here.
        rcfg.search_mode = "hybrid"
        rcfg.rrf_k = cfg.rrf_k
        rcfg.fetch_k = cfg.fetch_k
        rcfg.keyword_k = cfg.keyword_k
        rcfg.reranker_provider = cfg.reranker_provider
        rcfg.reranker_model = cfg.reranker_model
        rcfg.reranker_key_source = cfg.reranker_key_source
        rcfg.rerank_top_n = cfg.rerank_top_n
        rcfg.rerank_char_cap = cfg.rerank_char_cap
        if cfg.reranker_provider == "voyage" and cfg.reranker_api_key_enc:
            from types import SimpleNamespace

            from app.services.retrieval.rerank import resolve_reranker_key
            rcfg.reranker_api_key = resolve_reranker_key(
                db, SimpleNamespace(reranker_api_key_enc=cfg.reranker_api_key_enc),
                cfg.reranker_key_source)
        # Enhancement happens here (memoized, shared with the three indexes),
        # so the RAG engine must not run it a second time.
        question = _enhanced(db, source, question, cfg)
        rcfg.transform_enabled = False
        items = rag_retrieve(db, space, question, rcfg).get("items") or []
    except Exception as e:
        logger.warning(f"[DATA-AGENT/documents] {e!r}")
        return []
    return [RetrievedChunk(
        chunk_id=f"doc:{it.get('document')}:{i}",
        content=f"[{it.get('document')}] {it.get('content') or ''}",
        document_id=str(it.get("document") or ""), page=it.get("page") or 1,
        chunk_index=i, chunk_type="document",
        score=float(it.get("score") or 0), method=it.get("method") or "rag",
    ) for i, it in enumerate(items)]


def retrieve_all(db, source, question: str, cfg: RetrievalConfig,
                 embedding=None) -> dict:
    """All three indexes at once → {kind: [RetrievedChunk]}. This is the
    payload the prompt is built from AND the explainability trace.

    The Business index has two sources, merged here: schema-derived knowledge
    (FK map, descriptions, sample values, glossary) from data_vectors, and
    uploaded DOCUMENTS from the RAG engine."""
    from app.services.data_agent.vanna.store import bucket_model

    model = bucket_model(db, source)
    out: dict[str, list] = {}
    for kind in KINDS:
        try:
            out[kind] = search_kind(db, model, source, kind, question,
                                    embedding, cfg)
        except Exception as e:
            logger.warning(f"[DATA-AGENT/retrieval:{kind}] {e!r}")
            db.rollback()
            out[kind] = []
    out[KIND_BUSINESS] = (out.get(KIND_BUSINESS) or []) + \
        retrieve_documents(db, source, question, cfg)
    return out


def count_by_kind(db, source) -> dict:
    """How much knowledge is indexed, per index — shown in the UI."""
    from app.services.data_agent.vanna.store import bucket_model
    model = bucket_model(db, source)
    rows = (db.query(model.kind, func.count(model.id))
            .filter(model.data_source_id == source.id)
            .group_by(model.kind).all())
    counts = {k: 0 for k in KINDS}
    counts.update({k: int(n) for k, n in rows})
    return counts
