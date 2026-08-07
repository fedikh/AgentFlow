"""
Retriever Orchestrator — wires the pipeline.

                        User Query
                             │
               ┌─────────────┴──────────────┐
               ▼                            ▼
        SEMANTIC branch               LEXICAL branch
        1a. embed the raw             1b. Query Transformation
            question                      (LLM: rewrite, expansion,
               │                          multi-query, spell, noise)
               ▼                            ▼
        2a. Vector Search             2b. Keyword Search
            pgvector + HNSW               PostgreSQL FTS
            cosine similarity             tsvector + GIN + ts_rank
               └─────────────┬──────────────┘
                             ▼
               3. Reciprocal Rank Fusion    fusion.py  (hybrid mode)
                             │
               4. Cross-Encoder Re-ranking  rerank.py  (BGE v2-m3 / rerank-2.5)
                             │
               5. Context Construction      context.py (final top-k, dedup,
                             │               merge, document order, budget)
                             ▼
                            LLM

The two BRANCHES run in parallel with their own db sessions, so the
transform LLM call is hidden behind embed+vector instead of adding to it:
wall time = max(branchA, branchB), not their sum. Consequence of the
split: the transform feeds ONLY the keyword branch (the vector branch
embeds the raw question — embeddings are robust to phrasing), so in
"vector" mode the transform is skipped entirely.

Search mode is switchable per space: "hybrid" (both branches + RRF),
"vector" (semantic only) or "keyword" (lexical only). Every stage is timed.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from app.database import SessionLocal

from .config import load_config
from .context import build_context
from .fusion import fuse
from .rerank import rerank, resolve_reranker_key
from .retrievers import KeywordRetriever, VectorRetriever
from .transforms import enhance_query
from .types import Query

logger = logging.getLogger(__name__)


def _semantic_branch(space, cfg, q: Query, k: int, timings: dict) -> list:
    """Embed the raw question (cache first), then vector search (HNSW)."""
    db = SessionLocal()
    try:
        t = time.perf_counter()
        from . import embed_cache
        model_id = (f"{getattr(space, 'embedding_provider', '')}"
                    f":{getattr(space, 'embedding_model', '')}")
        emb = embed_cache.get(model_id, q.raw) if cfg.embed_cache_ttl else None
        if emb is None:
            from app.services.embedding_factory import embed_query
            emb = embed_query(db, space, q.raw)
            if cfg.embed_cache_ttl:
                embed_cache.put(model_id, q.raw, emb, cfg.embed_cache_ttl)
        q.embedding = emb
        timings["embed"] = round((time.perf_counter() - t) * 1000, 1)

        t = time.perf_counter()
        # one pooled connection per branch: the retriever reuses this session
        hits = VectorRetriever(lambda: db, space, cfg).retrieve(q, k)
        timings["vector"] = round((time.perf_counter() - t) * 1000, 1)
        return hits
    finally:
        db.close()


def _lexical_branch(space, cfg, q: Query, k: int, timings: dict) -> list:
    """Transform the query (LLM, optional), then keyword search (FTS)."""
    db = SessionLocal()
    try:
        if cfg.transform_enabled:
            t = time.perf_counter()
            enhance_query(db, space, q)
            timings["transform"] = round((time.perf_counter() - t) * 1000, 1)

        t = time.perf_counter()
        # one pooled connection per branch: the retriever reuses this session
        hits = KeywordRetriever(lambda: db, space, cfg).retrieve(q, k)
        timings["keyword"] = round((time.perf_counter() - t) * 1000, 1)
        return hits
    finally:
        db.close()


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
    k = max(cfg.top_k * 3, 15)

    branches = {}
    if cfg.search_mode in ("hybrid", "vector"):
        branches["vector"] = lambda: _semantic_branch(space, cfg, q, k, timings)
    if cfg.search_mode in ("hybrid", "keyword"):
        branches["keyword"] = lambda: _lexical_branch(space, cfg, q, k, timings)

    # ── 1+2. the branches — parallel when there are two ──
    t = time.perf_counter()
    results = {}
    if len(branches) > 1 and cfg.parallel:
        with ThreadPoolExecutor(max_workers=len(branches)) as pool:
            futs = {name: pool.submit(fn) for name, fn in branches.items()}
            for name, fut in futs.items():
                try:
                    results[name] = fut.result(timeout=cfg.timeout_s + 2)
                except Exception as e:
                    logger.warning(f"[RETRIEVAL/{name}] failed: {e!r}")
                    results[name] = []
    else:
        for name, fn in branches.items():
            try:
                results[name] = fn()
            except Exception as e:
                logger.warning(f"[RETRIEVAL/{name}] failed: {e}")
                results[name] = []
    # vector-only mode must never return nothing because embedding failed
    if cfg.search_mode == "vector" and not results.get("vector"):
        logger.warning("[RETRIEVAL] vector branch empty — keyword rescue")
        try:
            results["keyword"] = _lexical_branch(space, cfg, q, k, timings)
        except Exception as e:
            logger.warning(f"[RETRIEVAL/rescue] failed: {e}")
    timings["retrieve"] = round((time.perf_counter() - t) * 1000, 1)

    # ── 3. fusion (RRF merges ranks — no score normalization needed) ──
    t = time.perf_counter()
    fused = fuse(results, rrf_k=cfg.rrf_k)
    timings["fuse"] = round((time.perf_counter() - t) * 1000, 1)

    # ── 4. cross-encoder re-ranking ──
    # Fast path: the context stage takes the top_k candidates and re-sorts
    # them into DOCUMENT order, so when fusion produced ≤ top_k the reranker
    # cannot change which chunks the LLM sees — skip its full cost.
    if fused and len(fused) > cfg.top_k:
        t = time.perf_counter()
        if cfg.reranker_provider == "voyage" and not cfg.reranker_api_key:
            cfg.reranker_api_key = resolve_reranker_key(db, space, cfg.reranker_key_source)
        fused = rerank(cfg, q.text, fused)
        timings["rerank"] = round((time.perf_counter() - t) * 1000, 1)
    elif fused:
        timings["rerank"] = 0.0

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
