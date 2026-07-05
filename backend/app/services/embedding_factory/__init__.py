"""
Embedding Factory package — mirror of the LLM factory, for embeddings.

Public API:
    from app.services.embedding_factory import embed_texts, embed_query, get_embedder

  embed_texts(db, space, texts) / embed_query(db, space, text)
      → resolve the space's embedding config and embed (own key → company →
        local BGE-M3), with a 1024-dim guard for pgvector safety.

  get_embedder(family, model, api_key, base_url)
      → low-level: build an embedder for any family (LOCAL / OPENAI / VOYAGE).

  resolve_embedding_config(db, space)
      → which provider/key/model to use for a space's embeddings.
"""
from app.services.embedding_factory.factory import get_embedder, local_embedder
from app.services.embedding_factory.resolver import resolve_embedding_config
from app.services.embedding_factory.generate import embed_texts, embed_query

__all__ = [
    "get_embedder",
    "local_embedder",
    "resolve_embedding_config",
    "embed_texts",
    "embed_query",
]
