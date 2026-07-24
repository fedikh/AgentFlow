"""
Retrieval Engine — enterprise hybrid retrieval for the existing RAG platform.

    Query Analyzer → Retriever Orchestrator (dense / BM25 / metadata / exact,
    parallel) → Fusion (RRF / weighted) → optional Re-ranking (CrossEncoder /
    BGE / Cohere / Jina / Voyage) → Context Builder.

Public API:
    from app.services.retrieval import retrieve, load_config
    result = retrieve(db, space, "N° inscription 2300114")
    result["items"]        # ordered context, each with document/page/score/method

Configuration: defaults ← optional retrieval.json ← per-space settings
(top_k, semantic_weight, reranking_enabled, search_engine). See config.py.
"""
from .orchestrator import retrieve
from .config import RetrievalConfig, load_config
from .analyzer import analyze
from .types import BaseRetriever, RetrievedChunk, AnalyzedQuery

__all__ = [
    "retrieve", "RetrievalConfig", "load_config", "analyze",
    "BaseRetriever", "RetrievedChunk", "AnalyzedQuery",
]
