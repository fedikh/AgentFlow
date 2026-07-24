"""
Re-ranking layer — optional, pluggable, NEVER fatal.

Providers (cfg.reranker_provider):
    cross_encoder : SentenceTransformers CrossEncoder (local, default
                    "cross-encoder/ms-marco-MiniLM-L-6-v2")
    bge           : BGE reranker via CrossEncoder (local, "BAAI/bge-reranker-base")
    cohere        : Cohere Rerank API      (COHERE_API_KEY)
    jina          : Jina AI Reranker API   (JINA_API_KEY)
    voyage        : Voyage Rerank API      (VOYAGE_API_KEY)

Any failure (missing key, model download, network, timeout) logs a warning and
returns the fused order untouched — retrieval quality degrades gracefully,
queries never break.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_LOCAL_MODELS: dict = {}      # model name -> CrossEncoder singleton

_DEFAULTS = {
    "cross_encoder": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "bge": "BAAI/bge-reranker-v2-m3",                       # best local quality
    "jina_local": "jinaai/jina-reranker-v2-base-multilingual",
    "flashrank": "ms-marco-MiniLM-L-12-v2",                  # tiny + fast (ONNX)
    "cohere": "rerank-v3.5",
    "jina": "jina-reranker-v2-base-multilingual",
    "voyage": "rerank-2",
}

_FLASHRANK: dict = {}     # model name -> flashrank Ranker singleton


def _apply_order(chunks, order_scores):
    """order_scores: list of (index_into_chunks, score) — highest first."""
    out = []
    for i, s in order_scores:
        c = chunks[i]
        c.score = round(float(s), 4)
        c.method = c.method + "+rerank" if "rerank" not in c.method else c.method
        out.append(c)
    return out


def _local_cross_encoder(model_name, query, chunks):
    from sentence_transformers import CrossEncoder
    if model_name not in _LOCAL_MODELS:
        logger.info(f"[RETRIEVAL/rerank] loading local model {model_name}…")
        _LOCAL_MODELS[model_name] = CrossEncoder(model_name)
    model = _LOCAL_MODELS[model_name]
    scores = model.predict([(query, c.content[:2000]) for c in chunks])
    ranked = sorted(range(len(chunks)), key=lambda i: float(scores[i]), reverse=True)
    # min-max normalize CE logits to 0..1 for consistent downstream scores
    lo, hi = float(min(scores)), float(max(scores))
    span = (hi - lo) or 1.0
    return _apply_order(chunks, [(i, (float(scores[i]) - lo) / span) for i in ranked])


def _flashrank(model_name, query, chunks):
    """FlashRank — small ONNX cross-encoders, very fast on CPU, no torch."""
    from flashrank import Ranker, RerankRequest
    if model_name not in _FLASHRANK:
        logger.info(f"[RETRIEVAL/rerank] loading FlashRank {model_name}…")
        _FLASHRANK[model_name] = Ranker(model_name=model_name)
    ranker = _FLASHRANK[model_name]
    req = RerankRequest(
        query=query,
        passages=[{"id": i, "text": c.content[:2000]} for i, c in enumerate(chunks)],
    )
    results = ranker.rerank(req)
    return _apply_order(chunks, [(int(r["id"]), float(r["score"])) for r in results])


def _api_rerank(provider, model_name, query, chunks):
    import requests
    docs = [c.content[:2000] for c in chunks]
    if provider == "cohere":
        key = os.environ.get("COHERE_API_KEY")
        if not key:
            raise RuntimeError("COHERE_API_KEY not set")
        r = requests.post(
            "https://api.cohere.com/v2/rerank",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model_name, "query": query, "documents": docs},
            timeout=20,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        return _apply_order(chunks, [(x["index"], x["relevance_score"]) for x in results])
    if provider == "jina":
        key = os.environ.get("JINA_API_KEY")
        if not key:
            raise RuntimeError("JINA_API_KEY not set")
        r = requests.post(
            "https://api.jina.ai/v1/rerank",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model_name, "query": query, "documents": docs},
            timeout=20,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        return _apply_order(
            chunks, [(x["index"], x.get("relevance_score", 0.0)) for x in results])
    if provider == "voyage":
        key = os.environ.get("VOYAGE_API_KEY")
        if not key:
            raise RuntimeError("VOYAGE_API_KEY not set")
        r = requests.post(
            "https://api.voyageai.com/v1/rerank",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model_name, "query": query, "documents": docs},
            timeout=20,
        )
        r.raise_for_status()
        results = r.json().get("data", [])
        return _apply_order(
            chunks, [(x["index"], x.get("relevance_score", 0.0)) for x in results])
    raise RuntimeError(f"unknown reranker provider '{provider}'")


def rerank(cfg, query: str, chunks: list) -> list:
    """Re-rank fused candidates. Returns chunks re-ordered (or unchanged on
    any failure). Only the top cfg.rerank_top_n candidates are scored —
    cross-encoders are accurate but slow."""
    if not cfg.rerank or len(chunks) <= 1:
        return chunks
    provider = (cfg.reranker_provider or "bge").lower()
    model_name = cfg.reranker_model or _DEFAULTS.get(provider, "")
    head = chunks[: int(cfg.rerank_top_n)]
    tail = chunks[int(cfg.rerank_top_n):]
    try:
        if provider in ("cross_encoder", "bge", "jina_local"):
            ranked = _local_cross_encoder(model_name, query, head)
        elif provider == "flashrank":
            ranked = _flashrank(model_name, query, head)
        else:
            ranked = _api_rerank(provider, model_name, query, head)
        # optional relevance floor: drop clearly-irrelevant reranked results
        thr = float(getattr(cfg, "rerank_threshold", 0) or 0)
        if thr > 0:
            kept = [c for c in ranked if c.score >= thr]
            ranked = kept or ranked[:1]      # never return an empty context
        return ranked + tail
    except Exception as e:
        logger.warning(f"[RETRIEVAL/rerank] {provider} failed ({e}) — keeping fusion order")
        return chunks
