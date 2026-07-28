"""
Embedding generation — the public entry point used by the RAG pipeline.

    embed_texts(db, space, texts) -> list[list[float]]
    embed_query(db, space, text)  -> list[float]

Both resolve the space's embedding config (own key → company → local BGE-M3),
build the embedder, and embed.

DIMENSIONS: every model emits its NATIVE dimension — vectors land in
per-dimension bucket tables (chunk_vectors_<dim>, see pgvector_store.py), so
there is NO fixed target dimension anymore and no dimension-based fallback.
Index-time and query-time both go through here with the SAME space config,
so their dimensions always agree by construction. The local fallback only
fires when the configured embedder actually FAILS (bad key, network, …) —
and in that case indexing would store 1024-d BGE-M3 vectors, searched by the
same fallback at query time, so the system degrades consistently.
"""
import logging

from app.services.embedding_factory.factory import get_embedder, local_embedder
from app.services.embedding_factory.resolver import resolve_embedding_config

logger = logging.getLogger(__name__)


def _embedder_for(db, space):
    cfg = resolve_embedding_config(db, space)
    try:
        return get_embedder(
            family=cfg["family"],
            model=cfg["model"],
            api_key=cfg["api_key"],
            base_url=cfg.get("base_url", ""),
        ), cfg["family"]
    except Exception as e:
        logger.warning(f"[EMB] embedder build failed ({e}); using local")
        return local_embedder(), "LOCAL"


def embed_texts(db, space, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    embedder, family = _embedder_for(db, space)
    try:
        return embedder.embed_documents(texts)
    except Exception as e:
        logger.warning(f"[EMB] {family} embed_documents failed ({e}); using local")
        return local_embedder().embed_documents(texts)


def embed_query(db, space, text: str) -> list[float]:
    embedder, family = _embedder_for(db, space)
    try:
        return embedder.embed_query(text)
    except Exception as e:
        logger.warning(f"[EMB] {family} embed_query failed ({e}); using local")
        return local_embedder().embed_query(text)
