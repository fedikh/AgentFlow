"""
Embedding generation — the public entry point used by the RAG pipeline.

    embed_texts(db, space, texts) -> list[list[float]]
    embed_query(db, space, text)  -> list[float]

Both resolve the space's embedding config (own key → company → local BGE-M3),
build the embedder, and embed.

DIMENSION GUARD (Batch 6): pgvector is fixed at 1024. If the resolved embedder
produces vectors of a different dimension (or fails), we fall back to the local
BGE-M3 model so indexing/search never breaks or corrupts the vector column.
Index-time and query-time both go through here with the SAME space config, so
they stay consistent.
"""
import logging

from app.services.embedding_factory.factory import get_embedder, local_embedder
from app.services.embedding_factory.resolver import resolve_embedding_config

logger = logging.getLogger(__name__)

PGVECTOR_DIM = 1024


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
        vecs = embedder.embed_documents(texts)
        if vecs and len(vecs[0]) != PGVECTOR_DIM:
            logger.warning(
                f"[EMB] {family} produced {len(vecs[0])}-d vectors, expected "
                f"{PGVECTOR_DIM}. Falling back to local BGE-M3 (re-embedding "
                f"needed to actually switch dimension)."
            )
            return local_embedder().embed_documents(texts)
        return vecs
    except Exception as e:
        logger.warning(f"[EMB] {family} embed_documents failed ({e}); using local")
        return local_embedder().embed_documents(texts)


def embed_query(db, space, text: str) -> list[float]:
    embedder, family = _embedder_for(db, space)
    try:
        vec = embedder.embed_query(text)
        if len(vec) != PGVECTOR_DIM:
            logger.warning(
                f"[EMB] {family} query vector is {len(vec)}-d, expected "
                f"{PGVECTOR_DIM}; using local BGE-M3"
            )
            return local_embedder().embed_query(text)
        return vec
    except Exception as e:
        logger.warning(f"[EMB] {family} embed_query failed ({e}); using local")
        return local_embedder().embed_query(text)
