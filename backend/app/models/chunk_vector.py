"""
ChunkVector models — the chunk_vectors_<dim> bucket tables, defined as
regular SQLAlchemy models so Base.metadata.create_all() creates them
(table + indexes) exactly like every other table. No startup DDL.

One model class exists per dimension in the embedding catalogs
(provider_models + model_registry): ChunkVector384, ChunkVector768, …
Adding a catalog model with a NEW dimension automatically adds its model
class here (the catalogs are the single source of truth), and create_all
creates the table at the next startup.

Column types per dimension:
  · dim ≤ 2000 → vector(dim),  HNSW cosine index (pgvector `vector` limit)
  · dim ≤ 4000 → halfvec(dim), HNSW cosine index (half precision,
                 negligible quality impact — e.g. 2560d / 3072d models)
  · dim > 4000 → halfvec(dim), NO index (exact scan only, still correct)
"""
import logging

from pgvector.sqlalchemy import HALFVEC, Vector
from sqlalchemy import Column, ForeignKey, Index, String

from app.database import Base

logger = logging.getLogger(__name__)

# pgvector HNSW index limits
HNSW_VECTOR_MAX = 2000   # max dims of an HNSW-indexed `vector` column
HNSW_HALFVEC_MAX = 4000  # max dims of an HNSW-indexed `halfvec` column

_models: dict[int, type] = {}


def chunk_vector_model(dim: int) -> type:
    """Return the mapped class for chunk_vectors_<dim>, building it on first
    use. Catalog dimensions are pre-built at import (see bottom of file);
    an off-catalog dimension gets its class (and later its table, via
    pgvector_store.ensure_bucket) on demand."""
    dim = int(dim)
    if dim in _models:
        return _models[dim]

    table = f"chunk_vectors_{dim}"
    coltype = HALFVEC(dim) if dim > HNSW_VECTOR_MAX else Vector(dim)

    indexes = [Index(f"{table}_space_idx", "rag_space_id")]
    if dim <= HNSW_HALFVEC_MAX:
        ops = "halfvec_cosine_ops" if dim > HNSW_VECTOR_MAX else "vector_cosine_ops"
        indexes.append(Index(
            f"{table}_hnsw", "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": ops},
        ))
    else:
        logger.warning(f"[VEC] dim {dim} exceeds HNSW limits — bucket runs unindexed")

    _models[dim] = type(
        f"ChunkVector{dim}",
        (Base,),
        {
            "__tablename__": table,
            "__table_args__": tuple(indexes),
            # Vector dies with its chunk (no delete hooks needed anywhere).
            "chunk_id": Column(String, ForeignKey("chunks.id", ondelete="CASCADE"),
                               primary_key=True),
            "rag_space_id": Column(String, nullable=False),
            "embedding": Column(coltype, nullable=False),
        },
    )
    return _models[dim]


def catalog_dims() -> set[int]:
    """Every distinct default dimension across the embedding catalogs."""
    from app.services.model_registry import EMBEDDING_MODELS
    from app.services.provider_models import EMBEDDING_PROVIDER_MODELS

    dims = {m["dim"] for models in EMBEDDING_PROVIDER_MODELS.values() for m in models}
    dims |= {m["dim"] for m in EMBEDDING_MODELS}
    return {int(d) for d in dims}


# Pre-build one model per catalog dimension at import time, so create_all()
# sees every bucket table exactly like any other model.
for _dim in sorted(catalog_dims()):
    chunk_vector_model(_dim)
