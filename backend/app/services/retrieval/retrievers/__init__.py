"""The two search branches:

    vector  — pgvector + HNSW, cosine (semantic)
    keyword — PostgreSQL FTS: tsvector + GIN + ts_rank, all-language (lexical)
"""
from .keyword import KeywordRetriever
from .vector import VectorRetriever

__all__ = ["VectorRetriever", "KeywordRetriever"]
