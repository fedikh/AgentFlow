"""
Vector Search (semantic) — pgvector + HNSW + cosine similarity.

Chunk embeddings live in per-dimension bucket tables chunk_vectors_<dim>
with an HNSW cosine index (models/chunk_vector.py). The orchestrator embeds
the query once with the space's own embedding model, so query dim == stored
dim by construction; this retriever searches the bucket with pgvector's
`<=>` operator via pgvector_store.search().
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from ..types import BaseRetriever, Query, RetrievedChunk

logger = logging.getLogger(__name__)


class VectorRetriever(BaseRetriever):
    name = "vector"

    def retrieve(self, q: Query, k: int) -> list[RetrievedChunk]:
        if q.embedding is None:
            return []
        from app.services import pgvector_store

        db = self.session_factory()          # branch-owned — not closed here
        # pgvector ≥ 0.8: keep walking the HNSW graph until enough rows
        # survive the rag_space_id filter (no-op on older versions)
        try:
            db.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        except Exception:
            db.rollback()
        rows = pgvector_store.search(
            db, self.space.id, q.embedding, max(k, int(self.cfg.fetch_k)))

        return [
            RetrievedChunk(
                chunk_id=r.id, content=r.content, document_id=r.document_id,
                page=r.page or 1, chunk_index=r.chunk_index or 0,
                chunk_type=getattr(r, "chunk_type", None) or "text",
                image_path=getattr(r, "image_path", None),
                score=round(float(r.sim), 4), method=self.name,
            )
            for r in rows
        ]
