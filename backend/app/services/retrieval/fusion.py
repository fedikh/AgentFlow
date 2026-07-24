"""
Fusion layer — merge the parallel retrievers' result lists into one ranking.

    RRF       : Reciprocal Rank Fusion — robust default, score-scale-free.
    weighted  : min-max-normalized scores blended by per-method weights
                (semantic_weight for dense, the rest sharing 1 - w).

Both dedupe by chunk id (keeping every agreeing method on the merged chunk —
a chunk found by dense AND bm25 AND exact ranks above single-method hits).
"""
from __future__ import annotations

from .types import RetrievedChunk


def _normalize(chunks: list) -> dict:
    """chunk_id -> 0..1 min-max normalized score within ONE result list.
    A constant list (single result / all-equal scores) normalizes to 1.0 —
    the retriever DID rank it best; scoring it 0 would erase its vote."""
    if not chunks:
        return {}
    scores = [c.score for c in chunks]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return {c.chunk_id: 1.0 for c in chunks}
    return {c.chunk_id: (c.score - lo) / (hi - lo) for c in chunks}


def fuse(result_lists: dict, method: str = "rrf", rrf_k: int = 60,
         semantic_weight: float = 0.7, weights: dict = None) -> list[RetrievedChunk]:
    """result_lists: {retriever_name: [RetrievedChunk, ...]} → fused ranking.

    weights: optional explicit per-retriever weights {"dense": .6, "bm25": .3,
    "metadata": .1} for the weighted mode; falls back to semantic_weight split.
    """
    by_id: dict = {}

    def keep(c: RetrievedChunk):
        cur = by_id.get(c.chunk_id)
        if cur is None:
            # copy-ish: keep the instance, start its methods set
            c.methods = {c.method}
            by_id[c.chunk_id] = c
        else:
            cur.methods.add(c.method)

    for name, lst in result_lists.items():
        for c in lst:
            keep(c)

    fused_scores: dict = {cid: 0.0 for cid in by_id}

    if method == "weighted":
        # explicit weights win; otherwise dense gets semantic_weight and every
        # other participating method shares the remainder equally. Exact hits
        # keep a floor so literal identifier matches can't be washed out.
        explicit = {k: float(v) for k, v in (weights or {}).items() if v}
        others = [n for n in result_lists if n != "dense" and result_lists[n]]
        w_other = (1.0 - semantic_weight) / len(others) if others else 0.0
        for name, lst in result_lists.items():
            w = explicit.get(name, semantic_weight if name == "dense" else w_other)
            for cid, s in _normalize(lst).items():
                fused_scores[cid] += w * s
    else:  # RRF
        for name, lst in result_lists.items():
            for rank, c in enumerate(lst):
                fused_scores[c.chunk_id] += 1.0 / (rrf_k + rank + 1)
        # normalize RRF to 0..1 for readable downstream scores
        if fused_scores:
            hi = max(fused_scores.values()) or 1.0
            fused_scores = {cid: s / hi for cid, s in fused_scores.items()}

    # exact-match floor: a literal identifier hit is always near the top
    for cid, c in by_id.items():
        if "exact" in c.methods:
            fused_scores[cid] = max(fused_scores[cid], 0.95)

    out = list(by_id.values())
    for c in out:
        c.score = round(float(fused_scores[c.chunk_id]), 4)
        c.method = "+".join(sorted(c.methods))
    out.sort(key=lambda c: c.score, reverse=True)
    return out
