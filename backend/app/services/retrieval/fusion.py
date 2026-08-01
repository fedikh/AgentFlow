"""
Reciprocal Rank Fusion — merge the vector and keyword rankings into one.

    score(chunk) = Σ over lists   1 / (rrf_k + rank)

RRF merges ranked lists WITHOUT normalizing their scores — which matters
here because cosine similarity (vector) and ts_rank (keyword) are on
completely different scales. Only the RANK in each list counts; a chunk
that both searches agree on rises to the top.
"""
from __future__ import annotations

from .types import RetrievedChunk


def fuse(result_lists: dict, rrf_k: int = 60) -> list[RetrievedChunk]:
    """result_lists: {retriever_name: [RetrievedChunk, ...]} → fused ranking,
    deduped by chunk id, scores normalized to 0..1 for readability."""
    by_id: dict = {}
    for lst in result_lists.values():
        for c in lst:
            cur = by_id.get(c.chunk_id)
            if cur is None:
                c.methods = {c.method}
                by_id[c.chunk_id] = c
            else:
                cur.methods.add(c.method)

    scores = {cid: 0.0 for cid in by_id}
    for lst in result_lists.values():
        for rank, c in enumerate(lst):
            scores[c.chunk_id] += 1.0 / (rrf_k + rank + 1)

    if scores:
        hi = max(scores.values()) or 1.0
        scores = {cid: s / hi for cid, s in scores.items()}

    out = list(by_id.values())
    for c in out:
        c.score = round(float(scores[c.chunk_id]), 4)
        c.method = "+".join(sorted(c.methods))
    out.sort(key=lambda c: c.score, reverse=True)
    return out
