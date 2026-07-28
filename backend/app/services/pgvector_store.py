"""
pgvector Store — dimension-bucket tables, so every embedding model runs at
its NATIVE dimension (no more fit-to-1024 pad/truncate).

Design ("dimension per space"):
  · A space's dimension comes from its embedding model (recorded on
    rag_spaces.embedding_dim the first time it embeds).
  · Vectors live in per-dimension bucket tables:
        chunk_vectors_<dim> (chunk_id PK → chunks.id ON DELETE CASCADE,
                             rag_space_id, embedding vector(<dim>))
    All spaces sharing a dimension share a bucket; queries always filter by
    space, so isolation is unchanged.
  · Each bucket gets its own HNSW cosine index — pgvector indexes require a
    fixed dimension, which is exactly why buckets exist.
  · dim > 2000: pgvector's HNSW limit for `vector` is 2000 dims, so big
    models (3072-dim OpenAI large / Gemini) use `halfvec` (indexable up to
    4000, half precision — negligible quality impact).
  · ON DELETE CASCADE means document/space deletion needs NO extra hooks:
    deleting chunks rows deletes their vectors automatically.
  · Model switch → new dim → vectors go to the new bucket; the space's
    re-index flow (already enforced on config drift) rebuilds everything.

The legacy chunks.embedding vector(1024) column is no longer read or
written; startup migration copies its data into chunk_vectors_1024 once.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)

# HNSW on plain `vector` is capped at 2000 dims → halfvec above that.
_HNSW_VECTOR_MAX = 2000
_HALFVEC_MAX = 4000

_ensured: set[int] = set()   # buckets confirmed to exist (per process)


def _table(dim: int) -> str:
    return f"chunk_vectors_{int(dim)}"


def _coltype(dim: int) -> str:
    return f"halfvec({int(dim)})" if dim > _HNSW_VECTOR_MAX else f"vector({int(dim)})"


def _ops(dim: int) -> str:
    return "halfvec_cosine_ops" if dim > _HNSW_VECTOR_MAX else "vector_cosine_ops"


def bucket_ddl(dim: int) -> list[str]:
    """Idempotent DDL for one dimension bucket (used by startup migrations too)."""
    t = _table(dim)
    ddl = [
        f"""CREATE TABLE IF NOT EXISTS {t} (
                chunk_id TEXT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
                rag_space_id TEXT NOT NULL,
                embedding {_coltype(dim)} NOT NULL
            )""",
        f"CREATE INDEX IF NOT EXISTS {t}_space_idx ON {t} (rag_space_id)",
    ]
    if dim <= _HALFVEC_MAX:
        ddl.append(f"CREATE INDEX IF NOT EXISTS {t}_hnsw ON {t} "
                   f"USING hnsw (embedding {_ops(dim)})")
    else:
        # beyond halfvec's index limit: exact scan only (still correct, slower)
        logger.warning(f"[VEC] dim {dim} exceeds HNSW limits — bucket runs unindexed")
    return ddl


def ensure_bucket(db, dim: int) -> None:
    """Create the bucket table + indexes for `dim` if missing (idempotent)."""
    if dim in _ensured:
        return
    for sql in bucket_ddl(dim):
        db.execute(text(sql))
    db.flush()
    _ensured.add(dim)


def _vec_literal(vec) -> str:
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


def upsert_vectors(db, dim: int, rows: list) -> None:
    """rows: [(chunk_id, rag_space_id, vector)] — writes into the dim bucket."""
    ensure_bucket(db, dim)
    t = _table(dim)
    sql = text(f"""
        INSERT INTO {t} (chunk_id, rag_space_id, embedding)
        VALUES (:cid, :sid, :emb)
        ON CONFLICT (chunk_id) DO UPDATE
            SET embedding = EXCLUDED.embedding, rag_space_id = EXCLUDED.rag_space_id
    """)
    for cid, sid, vec in rows:
        db.execute(sql, {"cid": cid, "sid": sid, "emb": _vec_literal(vec)})


def search(db, space_id: str, query_vec: list, limit: int, with_emb: bool = False) -> list:
    """Cosine search in the space's dimension bucket, hydrated with the chunk
    row in one JOIN. Bucket = len(query_vec) — the query is embedded with the
    space's current model, so the dimensions always agree."""
    dim = len(query_vec)
    t = _table(dim)
    exists = db.execute(text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = :t"), {"t": t}).first()
    if not exists:
        return []
    emb_col = ", v.embedding::text AS emb" if with_emb else ""
    sql = text(f"""
        SELECT c.id, c.content, c.page, c.document_id, c.chunk_index,
               c.chunk_type, c.image_path, c.parent_index,
               1 - (v.embedding <=> :q) AS sim{emb_col}
        FROM {t} v
        JOIN chunks c ON c.id = v.chunk_id
        WHERE v.rag_space_id = :sid
        ORDER BY v.embedding <=> :q
        LIMIT :k
    """)
    q = _vec_literal(query_vec)
    return db.execute(sql, {"q": q, "sid": space_id, "k": limit}).fetchall()


def space_vector_count(db, space_id: str, dim: int) -> int:
    t = _table(dim)
    try:
        return int(db.execute(text(
            f"SELECT count(*) FROM {t} WHERE rag_space_id = :s"), {"s": space_id}).scalar() or 0)
    except Exception:
        return 0
