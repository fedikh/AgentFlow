"""
Dense Retriever — pgvector cosine search in the space's DIMENSION BUCKET
(chunk_vectors_<dim>, native model dims — see pgvector_store.py).

The bucket is picked from len(q.embedding): the query is embedded with the
space's current model, so query dim == stored dim by construction.

Uses the query embedding computed once by the orchestrator (q.embedding).
Supports fetch_k over-fetch, a similarity threshold, and optional MMR
(maximal marginal relevance) diversification computed in Python over the
fetched candidate embeddings.
"""
from __future__ import annotations

import json
import logging
import math

from ..types import BaseRetriever, AnalyzedQuery, RetrievedChunk

logger = logging.getLogger(__name__)


def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class DenseRetriever(BaseRetriever):
    name = "dense"

    def applies_to(self, q: AnalyzedQuery) -> bool:
        return q.embedding is not None

    def retrieve(self, q: AnalyzedQuery, k: int) -> list[RetrievedChunk]:
        from app.services import pgvector_store
        fetch_k = max(k, int(self.cfg.fetch_k)) if (self.cfg.mmr or self.cfg.fetch_k) else k

        db = self.session_factory()
        try:
            rows = pgvector_store.search(
                db, self.space.id, q.embedding, fetch_k, with_emb=bool(self.cfg.mmr))
        finally:
            db.close()

        out = []
        for r in rows:
            sim = float(r.sim)
            if self.cfg.similarity_threshold and sim < self.cfg.similarity_threshold:
                continue
            out.append((r, sim))

        if self.cfg.mmr and len(out) > k:
            out = self._mmr(q.embedding, out, k)
        else:
            out = out[:k]

        return [
            RetrievedChunk(
                chunk_id=r.id, content=r.content, document_id=r.document_id,
                page=r.page or 1, chunk_index=r.chunk_index or 0,
                chunk_type=getattr(r, "chunk_type", None) or "text",
                image_path=getattr(r, "image_path", None),
                parent_index=getattr(r, "parent_index", None),
                score=round(sim, 4), method=self.name,
            )
            for r, sim in out
        ]

    # Greedy MMR over the fetched candidates: balance similarity to the query
    # against similarity to what's already selected (diversity).
    def _mmr(self, qvec, cands, k):
        lam = float(self.cfg.mmr_lambda)
        embs = []
        for r, _ in cands:
            try:
                embs.append(json.loads(r.emb))
            except Exception:
                embs.append(None)
        selected, rest = [], list(range(len(cands)))
        while rest and len(selected) < k:
            best_i, best_v = None, -1e9
            for i in rest:
                rel = cands[i][1]
                div = 0.0
                if selected and embs[i] is not None:
                    div = max(
                        (_cos(embs[i], embs[j]) for j in selected if embs[j] is not None),
                        default=0.0,
                    )
                v = lam * rel - (1 - lam) * div
                if v > best_v:
                    best_i, best_v = i, v
            selected.append(best_i)
            rest.remove(best_i)
        return [cands[i] for i in selected]
