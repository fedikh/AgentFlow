"""
Cross-Encoder Re-ranking — stage 5. ALWAYS ON, never fatal.

The cross-encoder reads (query + chunk) TOGETHER — unlike embeddings, which
never see them side by side — giving a far more accurate relevance score.
The top rerank_top_n fused candidates are re-scored and re-ordered.

Models (cfg.reranker_provider):
    bge    → BAAI/bge-reranker-v2-m3, local via sentence-transformers
             CrossEncoder (free, cached on disk, the default)
    voyage → rerank-2.5, Voyage AI Rerank API. Key resolution order:
                 1. the space's own key   (rag_spaces.reranker_api_key_enc)
                 2. an admin VOYAGE provider key (api_providers)
                 3. the VOYAGE_API_KEY environment variable

Any failure (missing model/key, network, timeout) logs a warning and returns
the fused order untouched — retrieval quality degrades gracefully, queries
never break.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_BGE_DEFAULT = "BAAI/bge-reranker-v2-m3"
_VOYAGE_DEFAULT = "rerank-2.5"

_LOCAL_MODELS: dict = {}     # model name → CrossEncoder singleton


def resolve_reranker_key(db, space, source: str = "company") -> str:
    """Voyage key, honoring the user's choice (cfg.reranker_key_source):

        source="company" → the admin-deployed VOYAGE provider key
                           (api_providers), falling back to VOYAGE_API_KEY env
        source="own"     → the space's own encrypted key ONLY
                           (rag_spaces.reranker_api_key_enc)
    """
    if source == "own":
        return _space_key(space)
    return _company_key(db) or os.environ.get("VOYAGE_API_KEY", "")


def _space_key(space) -> str:
    enc = getattr(space, "reranker_api_key_enc", None)
    if not enc:
        return ""
    try:
        from app.services.providers_crypto import decrypt_key
        return decrypt_key(enc) or ""
    except Exception as e:
        logger.warning(f"[RETRIEVAL/rerank] own key decrypt failed: {e}")
        return ""


def _company_key(db) -> str:
    try:
        from app.models.api_provider import ApiProvider
        p = db.query(ApiProvider).filter(ApiProvider.family == "VOYAGE").first()
        if p and p.api_key_encrypted:
            from app.services.providers_crypto import decrypt_key
            return decrypt_key(p.api_key_encrypted) or ""
    except Exception as e:
        logger.warning(f"[RETRIEVAL/rerank] company key lookup failed: {e}")
    return ""


def rerank(cfg, query: str, chunks: list) -> list:
    """Re-order `chunks` by cross-encoder relevance. Fused order on failure."""
    if not chunks:
        return chunks
    head = chunks[: int(cfg.rerank_top_n)]
    tail = chunks[len(head):]
    try:
        if cfg.reranker_provider == "voyage":
            ranked = _voyage(cfg, query, head)
        else:
            ranked = _bge(cfg, query, head)
        return ranked + tail
    except Exception as e:
        logger.warning(f"[RETRIEVAL/rerank] {cfg.reranker_provider} failed ({e}) "
                       "— keeping fusion order")
        return chunks


def _apply_order(chunks, order_scores):
    """order_scores: [(index_into_chunks, 0..1 score)] highest first."""
    out = []
    for i, s in order_scores:
        c = chunks[i]
        c.score = round(float(s), 4)
        c.methods = set(c.methods or {c.method}) | {"rerank"}
        c.method = "+".join(sorted(c.methods))
        out.append(c)
    return out


def _bge(cfg, query, chunks):
    """Local CrossEncoder (sentence-transformers), model singleton."""
    from sentence_transformers import CrossEncoder
    name = cfg.reranker_model or _BGE_DEFAULT
    if name not in _LOCAL_MODELS:
        logger.info(f"[RETRIEVAL/rerank] loading local model {name}…")
        _LOCAL_MODELS[name] = CrossEncoder(name)
    model = _LOCAL_MODELS[name]
    # 1000-char cap: cross-encoder relevance saturates well before that, and
    # scoring time grows with passage length (CPU)
    scores = model.predict([(query, c.content[:1000]) for c in chunks])
    ranked = sorted(range(len(chunks)), key=lambda i: float(scores[i]), reverse=True)
    lo, hi = float(min(scores)), float(max(scores))
    span = (hi - lo) or 1.0
    return _apply_order(chunks, [(i, (float(scores[i]) - lo) / span) for i in ranked])


def _voyage(cfg, query, chunks):
    """Voyage AI Rerank API (rerank-2.5)."""
    import requests
    key = cfg.reranker_api_key or os.environ.get("VOYAGE_API_KEY", "")
    if not key:
        raise RuntimeError("no Voyage API key (space key / provider / env)")
    r = requests.post(
        "https://api.voyageai.com/v1/rerank",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": cfg.reranker_model or _VOYAGE_DEFAULT,
            "query": query,
            "documents": [c.content[:4000] for c in chunks],
            "top_k": len(chunks),
        },
        timeout=20,
    )
    r.raise_for_status()
    data = r.json().get("data", [])
    return _apply_order(chunks, [(d["index"], float(d["relevance_score"])) for d in data])
