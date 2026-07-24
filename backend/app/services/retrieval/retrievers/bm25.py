"""
BM25 Retriever — lexical search with rank_bm25 (Okapi BM25).

Beats embeddings on numbers, codes, IDs, filenames and exact phrases.

The per-space corpus (tokenized chunks + BM25 index) is cached in memory and
invalidated when the space's chunks change (fingerprint = count + max id) or
after a TTL — so repeated queries don't re-tokenize thousands of chunks.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import unicodedata

from sqlalchemy import text

from ..types import BaseRetriever, AnalyzedQuery, RetrievedChunk

logger = logging.getLogger(__name__)

_CACHE: dict = {}          # space_id -> {"fp","ts","rows","tokens","bm25"}
_LOCK = threading.Lock()


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tokenize(s: str) -> list:
    """Lowercase, accent-strip, split on non-alphanumerics — keeps numbers and
    codes intact ('INV-2024' → ['inv','2024'] AND the joined 'inv2024')."""
    s = _strip_accents((s or "").lower())
    parts = re.findall(r"[a-z0-9]+", s)
    joined = [m.group(0).replace("-", "").replace(".", "")
              for m in re.finditer(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", s)]
    return parts + [j for j in joined if j not in parts]


class BM25Retriever(BaseRetriever):
    name = "bm25"

    def _fingerprint(self, db):
        # id is cast to text — works for integer AND uuid/string chunk ids.
        row = db.execute(
            text("SELECT COUNT(*) AS n, COALESCE(MAX(id::text), '') AS m "
                 "FROM chunks WHERE rag_space_id = :sid"),
            {"sid": self.space.id},
        ).fetchone()
        return (int(row.n), str(row.m))

    def _corpus(self):
        db = self.session_factory()
        try:
            fp = self._fingerprint(db)
            ttl = int(self.cfg.bm25_cache_ttl_s)
            with _LOCK:
                entry = _CACHE.get(self.space.id)
                if entry and entry["fp"] == fp and time.time() - entry["ts"] < ttl:
                    return entry
            rows = db.execute(
                text("""SELECT id, content, page, document_id, chunk_index,
                               chunk_type, image_path, parent_index
                        FROM chunks WHERE rag_space_id = :sid"""),
                {"sid": self.space.id},
            ).fetchall()
        finally:
            db.close()

        tokens = [tokenize(r.content) for r in rows]
        engine, bm25 = self._build_index(tokens)
        entry = {"fp": fp, "ts": time.time(), "rows": rows, "bm25": bm25,
                 "engine": engine, "tokens": tokens}
        with _LOCK:
            _CACHE[self.space.id] = entry
        logger.info(f"[RETRIEVAL/bm25] indexed {len(rows)} chunks for space "
                    f"{self.space.id} via {engine}")
        return entry

    def _build_index(self, tokens):
        """Prefer bm25s (fast, modern, sparse-matrix scoring); fall back to
        rank_bm25 so retrieval keeps working if bm25s is unavailable."""
        if not tokens:
            return ("none", None)
        k1, b = float(self.cfg.bm25_k1), float(self.cfg.bm25_b)
        try:
            import bm25s
            idx = bm25s.BM25(k1=k1, b=b)
            try:
                idx.index(tokens, show_progress=False)
            except TypeError:
                idx.index(tokens)
            return ("bm25s", idx)
        except Exception as e:
            logger.warning(f"[RETRIEVAL/bm25] bm25s unavailable ({e}); using rank_bm25")
            from rank_bm25 import BM25Okapi
            return ("rank_bm25", BM25Okapi(tokens, k1=k1, b=b))

    def retrieve(self, q: AnalyzedQuery, k: int) -> list[RetrievedChunk]:
        entry = self._corpus()
        bm25, rows = entry["bm25"], entry["rows"]
        if not bm25:
            return []

        # query tokens: raw + expansions + identifier variants
        qtok = tokenize(q.raw)
        for e in q.expansions:
            qtok += tokenize(e)
        qtok = list(dict.fromkeys(qtok))
        if not qtok:
            return []

        k = max(k, int(self.cfg.bm25_k))
        if entry.get("engine") == "bm25s":
            import numpy as np
            scores = bm25.get_scores(qtok)          # bm25s: vectorized ndarray
            scores = np.asarray(scores).ravel()
        else:
            scores = bm25.get_scores(qtok)          # rank_bm25: python list
        ranked = sorted(range(len(rows)), key=lambda i: scores[i], reverse=True)[:k]
        out = []
        for i in ranked:
            if scores[i] <= 0:
                break
            r = rows[i]
            out.append(RetrievedChunk(
                chunk_id=r.id, content=r.content, document_id=r.document_id,
                page=r.page or 1, chunk_index=r.chunk_index or 0,
                chunk_type=getattr(r, "chunk_type", None) or "text",
                image_path=getattr(r, "image_path", None),
                parent_index=getattr(r, "parent_index", None),
                score=round(float(scores[i]), 4), method=self.name,
            ))
        return out
