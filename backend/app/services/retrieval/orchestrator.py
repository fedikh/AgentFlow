"""
Retriever Orchestrator — wires the pipeline.

                     User Query
                          │
              1. Query Transformation      transforms.py  (LLM: rewrite,
                          │                 expansion, multi-query, spell,
                          │                 noise — enabled by default)
            ┌─────────────┴─────────────┐
            ▼                           ▼
     2a. Vector Search           2b. Keyword Search
     pgvector + HNSW             PostgreSQL FTS
     cosine similarity           tsvector + GIN + ts_rank
            └─────────────┬─────────────┘
                          ▼
              3. Reciprocal Rank Fusion    fusion.py  (hybrid mode)
                          │
              4. Cross-Encoder Re-ranking  rerank.py  (BGE v2-m3 / rerank-2.5)
                          │
              5. Context Construction      context.py (final top-k, dedup,
                          │                 merge, document order, budget)
                          ▼
                         LLM

The search mode is switchable per space: "hybrid" (both branches + RRF),
"vector" (semantic only) or "keyword" (lexical only). Branches run in
parallel with their own db sessions; every stage is timed.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.database import SessionLocal

from .config import load_config
from .context import build_context
from .fusion import fuse
from .rerank import rerank, resolve_reranker_key
from .retrievers import KeywordRetriever, VectorRetriever
from .transforms import enhance_query
from .types import Query

logger = logging.getLogger(__name__)

_MODE_BRANCHES = {
    "hybrid": ["vector", "keyword"],
    "vector": ["vector"],
    "keyword": ["keyword"],
}
_RETRIEVER_CLASSES = {"vector": VectorRetriever, "keyword": KeywordRetriever}


def retrieve(db, space, question: str, cfg=None) -> dict:
    """Public API. Returns:
    {
      "items": [...],        # final context items (doc, page, score, method…)
      "search_mode": "...",  # mode actually used
      "timings_ms": {...},   # per-stage profiling
    }
    """
    t0 = time.perf_counter()
    cfg = cfg or load_config(space)
    timings = {}
    q = Query(raw=question or "")

    # ── 1. query transformation (LLM) ──
    if cfg.transform_enabled:
        t = time.perf_counter()
        enhance_query(db, space, q)
        timings["transform"] = round((time.perf_counter() - t) * 1000, 1)

    # ── 2. the search branches ──
    branches = list(_MODE_BRANCHES.get(cfg.search_mode, _MODE_BRANCHES["hybrid"]))

    if "vector" in branches:
        t = time.perf_counter()
        try:
            from app.services.embedding_factory import embed_query
            q.embedding = embed_query(db, space, q.text)
        except Exception as e:
            logger.warning(f"[RETRIEVAL] embedding failed ({e}) — vector skipped")
            branches = [b for b in branches if b != "vector"] or ["keyword"]
        timings["embed"] = round((time.perf_counter() - t) * 1000, 1)

    retrievers = [_RETRIEVER_CLASSES[b](SessionLocal, space, cfg) for b in branches]
    k = max(cfg.top_k * 3, 15)

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

    # ── 3. fusion (RRF merges ranks — no score normalization needed) ──
    t = time.perf_counter()
    fused = fuse(results, rrf_k=cfg.rrf_k)
    timings["fuse"] = round((time.perf_counter() - t) * 1000, 1)

    # ── 4. cross-encoder re-ranking ──
    if fused:
        t = time.perf_counter()
        if cfg.reranker_provider == "voyage" and not cfg.reranker_api_key:
            cfg.reranker_api_key = resolve_reranker_key(db, space, cfg.reranker_key_source)
        fused = rerank(cfg, q.text, fused)
        timings["rerank"] = round((time.perf_counter() - t) * 1000, 1)

    # ── 5. context construction ──
    t = time.perf_counter()
    ctx = build_context(cfg, SessionLocal, space, fused)
    timings["context"] = round((time.perf_counter() - t) * 1000, 1)
    timings["total"] = round((time.perf_counter() - t0) * 1000, 1)

    if cfg.log_timings:
        counts = {n: len(v) for n, v in results.items()}
        logger.info(f"[RETRIEVAL] mode={cfg.search_mode} hits={counts} "
                    f"fused={len(fused)} ctx={len(ctx['items'])} timings={timings}")

    return {
        "items": ctx["items"],
        "search_mode": cfg.search_mode,
        "timings_ms": timings,
    }
