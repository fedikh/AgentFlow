"""
Exact-Match Retriever — identifiers are NEVER left to embeddings.

Registration numbers, invoice numbers, employee ids, UUIDs, emails, phone
numbers, product/document ids… are matched literally in chunk content (and the
document name), including separator-stripped variants ("23-00-114" ↔
"2300114"). Exact hits get the maximum score so fusion keeps them on top.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import text

from ..types import BaseRetriever, AnalyzedQuery, RetrievedChunk

logger = logging.getLogger(__name__)


class ExactMatchRetriever(BaseRetriever):
    name = "exact"

    def applies_to(self, q: AnalyzedQuery) -> bool:
        return bool(q.identifiers)

    def retrieve(self, q: AnalyzedQuery, k: int) -> list[RetrievedChunk]:
        variants = []
        for ident in q.identifiers:
            v = ident["value"]
            variants.append(v)
            bare = re.sub(r"[\s.-]", "", v)
            if bare != v:
                variants.append(bare)
        variants = list(dict.fromkeys(variants))[:8]
        if not variants:
            return []

        db = self.session_factory()
        try:
            clauses, params = [], {"sid": self.space.id, "k": max(k, 20)}
            for i, v in enumerate(variants):
                params[f"v{i}"] = f"%{v}%"
                # match content as-is AND content with separators stripped, so
                # "2300114" finds "N° 23-00-114" too.
                clauses.append(
                    f"(c.content ILIKE :v{i} "
                    f" OR REGEXP_REPLACE(c.content, '[\\s.-]', '', 'g') ILIKE :v{i}"
                    f" OR d.file_name ILIKE :v{i})"
                )
            sql = text(f"""
                SELECT c.id, c.content, c.page, c.document_id, c.chunk_index,
                       c.chunk_type, c.image_path, c.parent_index
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.rag_space_id = :sid AND ({' OR '.join(clauses)})
                ORDER BY c.document_id, c.page, c.chunk_index
                LIMIT :k
            """)
            rows = db.execute(sql, params).fetchall()
        finally:
            db.close()

        return [
            RetrievedChunk(
                chunk_id=r.id, content=r.content, document_id=r.document_id,
                page=r.page or 1, chunk_index=r.chunk_index or 0,
                chunk_type=getattr(r, "chunk_type", None) or "text",
                image_path=getattr(r, "image_path", None),
                parent_index=getattr(r, "parent_index", None),
                score=1.0, method=self.name,     # literal hit = maximum confidence
            )
            for r in rows
        ]
