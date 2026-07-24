"""
Metadata Retriever — no embeddings involved.

Searches indexed metadata directly: document name, page number, chunk type,
strategy, dates that appear in filenames. Used when the query targets a
document/page rather than content ("rapport_2025.pdf", "page 12 …").
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from ..types import BaseRetriever, AnalyzedQuery, RetrievedChunk

logger = logging.getLogger(__name__)


class MetadataRetriever(BaseRetriever):
    name = "metadata"

    def applies_to(self, q: AnalyzedQuery) -> bool:
        return bool(q.filenames or q.pages or q.dates or q.keywords)

    def retrieve(self, q: AnalyzedQuery, k: int) -> list[RetrievedChunk]:
        db = self.session_factory()
        try:
            clauses, params = [], {"sid": self.space.id}
            i = 0
            # filename targets (exact-ish name match)
            for fn in q.filenames:
                i += 1
                clauses.append(f"d.file_name ILIKE :fn{i}")
                params[f"fn{i}"] = f"%{fn}%"
            # date fragments in the file name (e.g. "2025")
            for dt in q.dates:
                i += 1
                clauses.append(f"d.file_name ILIKE :dt{i}")
                params[f"dt{i}"] = f"%{dt}%"
            # keyword hits in the file name ("the finance report")
            for kw in q.keywords[:4]:
                if len(kw) >= 4:
                    i += 1
                    clauses.append(f"d.file_name ILIKE :kw{i}")
                    params[f"kw{i}"] = f"%{kw}%"
            if not clauses and not q.pages:
                return []

            where = f"({' OR '.join(clauses)})" if clauses else "TRUE"
            page_sql = ""
            if q.pages:
                page_sql = "AND c.page = ANY(:pages)"
                params["pages"] = q.pages

            sql = text(f"""
                SELECT c.id, c.content, c.page, c.document_id, c.chunk_index,
                       c.chunk_type, c.image_path, c.parent_index
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.rag_space_id = :sid AND {where} {page_sql}
                ORDER BY d.file_name, c.page, c.chunk_index
                LIMIT :k
            """)
            params["k"] = max(k, 10)
            rows = db.execute(sql, params).fetchall()
        finally:
            db.close()

        n = len(rows) or 1
        return [
            RetrievedChunk(
                chunk_id=r.id, content=r.content, document_id=r.document_id,
                page=r.page or 1, chunk_index=r.chunk_index or 0,
                chunk_type=getattr(r, "chunk_type", None) or "text",
                image_path=getattr(r, "image_path", None),
                parent_index=getattr(r, "parent_index", None),
                # rank-based score: metadata matches are ordered, not scored
                score=round(1.0 - idx / n, 4), method=self.name,
            )
            for idx, r in enumerate(rows)
        ]
