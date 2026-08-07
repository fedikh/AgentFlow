"""
Keyword Search (lexical) — PostgreSQL Full Text Search.

    tsvector  — the GENERATED chunks.content_tsv column: each chunk was
                indexed with the stemming config of ITS OWN detected
                language (fr → french, en → english, else simple)
    tsquery   — websearch_to_tsquery over the SAME three configs, so the
                query matches every chunk whatever language it was indexed
                in ("congés" finds "congé" in French rows, "days" finds
                "day" in English rows — no query-side language detection)
    GIN index — chunks_content_tsv_gin serves the @@ matches
    ts_rank   — relevance, normalization 32 → scores in 0..1

Recall ladder: exact phrase semantics first (websearch AND), then the
transform variants, then an OR of the words — stops at the first level
that returns rows.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from ..types import BaseRetriever, Query, RetrievedChunk

logger = logging.getLogger(__name__)

_SQL = text("""
    WITH tsq AS (
        SELECT websearch_to_tsquery('french',  :q) AS fr,
               websearch_to_tsquery('english', :q) AS en,
               websearch_to_tsquery('simple',  :q) AS si
    )
    SELECT c.id, c.content, c.page, c.document_id, c.chunk_index,
           c.chunk_type, c.image_path,
           GREATEST(ts_rank(c.content_tsv, tsq.fr, 32),
                    ts_rank(c.content_tsv, tsq.en, 32),
                    ts_rank(c.content_tsv, tsq.si, 32)) AS score
    FROM chunks c, tsq
    WHERE c.rag_space_id = :sid
      AND (c.content_tsv @@ tsq.fr OR c.content_tsv @@ tsq.en
           OR c.content_tsv @@ tsq.si)
    ORDER BY score DESC, c.document_id, c.chunk_index
    LIMIT :k
""")


class KeywordRetriever(BaseRetriever):
    name = "keyword"

    def retrieve(self, q: Query, k: int) -> list[RetrievedChunk]:
        fetch_k = max(k, int(self.cfg.keyword_k))
        # recall ladder: cleaned query → transform variants → OR of the words
        candidates = [q.text, *q.variants]
        candidates.append(" OR ".join(q.text.split()))

        db = self.session_factory()          # branch-owned — not closed here
        try:
            rows = []
            for qtext in candidates:
                if not qtext.strip():
                    continue
                rows = db.execute(
                    _SQL, {"q": qtext, "sid": self.space.id, "k": fetch_k}
                ).fetchall()
                if rows:
                    break
        except Exception as e:
            logger.warning(f"[RETRIEVAL/keyword] query failed: {e}")
            rows = []

        return [
            RetrievedChunk(
                chunk_id=r.id, content=r.content, document_id=r.document_id,
                page=r.page or 1, chunk_index=r.chunk_index or 0,
                chunk_type=getattr(r, "chunk_type", None) or "text",
                image_path=getattr(r, "image_path", None),
                score=round(float(r.score), 4), method=self.name,
            )
            for r in rows
        ]
