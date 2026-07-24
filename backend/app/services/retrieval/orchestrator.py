"""
Retriever Orchestrator — the engine's brain.

    analyze → pick strategy → run retrievers in parallel (own db session each,
    per-retriever timeout) → fuse (RRF/weighted) → optional rerank → build
    context. Timings for every stage are logged and returned for profiling.

Strategy auto-selection (intersected with the config's enabled retrievers):

    exact_id   → exact + bm25 + metadata     (identifiers never rely on vectors)
    filename   → metadata + bm25
    metadata   → metadata + dense
    keyword    → bm25 + dense                (names, companies → hybrid)
    hybrid_id  → exact + bm25 + dense        (identifier inside a real sentence)
    semantic   → dense + bm25                (+ reranker when enabled)

Adding a retriever: implement BaseRetriever, register it in _RETRIEVER_CLASSES
and reference its name in _STRATEGIES — no other code changes (open/closed).
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.database import SessionLocal

from .analyzer import analyze
from .config import load_config
from .context import build_context
from .fusion import fuse
from .rerank import rerank
from .retrievers import (
    BM25Retriever, DenseRetriever, ExactMatchRetriever, MetadataRetriever,
)

logger = logging.getLogger(__name__)

_RETRIEVER_CLASSES = {
    "dense": DenseRetriever,
    "bm25": BM25Retriever,
    "metadata": MetadataRetriever,
    "exact": ExactMatchRetriever,
}

_STRATEGIES = {
    "exact_id":  ["exact", "bm25", "metadata"],
    "filename":  ["metadata", "bm25"],
    "metadata":  ["metadata", "dense"],
    "keyword":   ["bm25", "dense"],
    "hybrid_id": ["exact", "bm25", "dense"],
    "semantic":  ["dense", "bm25"],
}


def _enabled(cfg, name):
    return getattr(cfg, f"enable_{name}", True)


def retrieve(db, space, question: str, cfg=None) -> dict:
    """Public API. Returns:
    {
      "items": [...],            # ordered context items (doc, page, score, method…)
      "strategy": [...],         # retrievers actually run
      "intent": "...",           # analyzer classification
      "timings_ms": {...},       # per-stage profiling
    }
    """
    t0 = time.perf_counter()
    cfg = cfg or load_config(space)
    timings = {}

    # ── 1. analyze ──
    q = analyze(question)
    timings["analyze"] = round((time.perf_counter() - t0) * 1000, 1)

    # ── 1b. optional LLM transforms: rewrite / HyDE / multi-query ──
    if cfg.rewrite_query or cfg.hyde or cfg.multi_query:
        t = time.perf_counter()
        try:
            from .transforms import apply_transforms
            apply_transforms(db, space, cfg, q)
        except Exception as e:
            logger.warning(f"[RETRIEVAL] transforms failed ({e}) — original query kept")
        timings["transform"] = round((time.perf_counter() - t) * 1000, 1)

    # ── 2. strategy ──
    wanted = _STRATEGIES.get(q.intent, _STRATEGIES["semantic"])
    strategy = [n for n in wanted if _enabled(cfg, n)]
    if not strategy:                       # everything disabled → dense fallback
        strategy = ["dense"]

    # ── 3. embed once, only if dense participates. HyDE swaps the embedded
    #      text for the hypothetical answer; rewrite refines it. ──
    if "dense" in strategy:
        t = time.perf_counter()
        embed_text = q.hyde_text or q.rewritten or question
        try:
            from app.services.embedding_factory import embed_query
            q.embedding = embed_query(db, space, embed_text)
        except Exception as e:
            logger.warning(f"[RETRIEVAL] embedding failed ({e}) — dense skipped")
            strategy = [n for n in strategy if n != "dense"] or ["bm25"]
        timings["embed"] = round((time.perf_counter() - t) * 1000, 1)

    # ── 4. build retrievers (DI: session factory + space + config) ──
    retrievers = []
    for name in strategy:
        r = _RETRIEVER_CLASSES[name](SessionLocal, space, cfg)
        if r.applies_to(q):
            retrievers.append(r)
    k = max(cfg.top_k * 3, 15)             # over-fetch; fusion + budget trim later

    # ── 5. run (parallel, per-retriever timeout) ──
    t = time.perf_counter()
    results = {}
    if cfg.parallel and len(retrievers) > 1:
        with ThreadPoolExecutor(max_workers=len(retrievers)) as pool:
            futs = {pool.submit(r.retrieve, q, k): r for r in retrievers}
            for fut in as_completed(futs, timeout=cfg.timeout_s + 2):
                r = futs[fut]
                try:
                    results[r.name] = fut.result(timeout=cfg.timeout_s)
                except Exception as e:
                    logger.warning(f"[RETRIEVAL/{r.name}] failed: {e}")
                    results[r.name] = []
    else:
        for r in retrievers:
            try:
                results[r.name] = r.retrieve(q, k)
            except Exception as e:
                logger.warning(f"[RETRIEVAL/{r.name}] failed: {e}")
                results[r.name] = []
    timings["retrieve"] = round((time.perf_counter() - t) * 1000, 1)

    # ── 6. fuse ──
    t = time.perf_counter()
    weights = {"dense": cfg.w_dense, "bm25": cfg.w_bm25, "metadata": cfg.w_metadata}
    fused = fuse(results, method=cfg.fusion, rrf_k=cfg.rrf_k,
                 semantic_weight=cfg.semantic_weight, weights=weights)
    timings["fuse"] = round((time.perf_counter() - t) * 1000, 1)

    # ── 7. rerank (optional) ──
    if cfg.rerank and fused:
        t = time.perf_counter()
        fused = rerank(cfg, question, fused)
        timings["rerank"] = round((time.perf_counter() - t) * 1000, 1)

    # ── 8. context ──
    t = time.perf_counter()
    ctx = build_context(cfg, SessionLocal, space, fused)
    timings["context"] = round((time.perf_counter() - t) * 1000, 1)
    timings["total"] = round((time.perf_counter() - t0) * 1000, 1)

    if cfg.log_timings:
        counts = {n: len(v) for n, v in results.items()}
        logger.info(
            f"[RETRIEVAL] intent={q.intent} strategy={strategy} hits={counts} "
            f"fused={len(fused)} ctx={len(ctx['items'])} timings={timings}")

    return {
        "items": ctx["items"],
        "strategy": strategy,
        "intent": q.intent,
        "language": q.language,
        "timings_ms": timings,
    }
