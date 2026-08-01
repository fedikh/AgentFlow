"""
Retrieval Engine — PostgreSQL-native, switchable search mode.

    Query Transformation (LLM, on by default) →
    [ Vector: pgvector + HNSW, cosine ∥ Keyword: PostgreSQL FTS —
      tsvector + GIN + ts_rank, all indexed languages ] →
    Reciprocal Rank Fusion (hybrid) →
    Cross-Encoder Re-ranking (BGE v2-m3 local / rerank-2.5 Voyage) →
    Context Construction → LLM

Search mode per space: "hybrid" (recommended) | "vector" | "keyword".

Public API:
    from app.services.retrieval import retrieve, load_config
    result = retrieve(db, space, "leave policy for EMP2300114")
    result["items"]     # final context, each with document/page/score/method
"""
from .config import RetrievalConfig, load_config
from .orchestrator import retrieve
from .types import BaseRetriever, Query, RetrievedChunk

__all__ = ["retrieve", "RetrievalConfig", "load_config",
           "BaseRetriever", "RetrievedChunk", "Query"]
