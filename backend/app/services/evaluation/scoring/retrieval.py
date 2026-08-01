"""
Scoring — retrieval. ranx (deterministic IR evaluation, no AI, free).

For every labeled case, the retrieved ranking is scored against the gold
label (expected_document [+ expected_page]) with the standard IR metrics:

    Recall@K       was a relevant chunk retrieved at all? (single gold label
                   → per-case hit, averaged across cases)
    Precision@K    fraction of the K retrieved chunks that are relevant
    MRR            1 / rank of the first relevant chunk
    NDCG@K         position-discounted gain (gentler than MRR)

K = the number of chunks retrieval returned for the case (the space's Top-K).
Cases without an expected_document can't be scored and return None ("hit"
stays None so the runner can report labeled vs unlabeled counts honestly).
"""
from __future__ import annotations

import threading

from ..common import logger

# ranx runs on numba, whose default (workqueue) threading layer is NOT
# thread-safe — the runner fans cases out over a worker pool, so the actual
# ranx call is serialized. It's microseconds of math; the parallelism win
# lives in the retrieval/LLM calls, not here.
_RANX_LOCK = threading.Lock()


def relevant(item: dict, case) -> bool:
    """Gold check: the item comes from the expected document (and page)."""
    if not case.expected_document:
        return False
    if case.expected_document.lower() not in (item.get("document") or "").lower():
        return False
    if case.expected_page is not None:
        return case.expected_page == item.get("page")
    return True


_UNSCORED = {"hit": None, "recall_at_k": None, "precision_at_k": None,
             "mrr": None, "ndcg": None}


def score_case(items: list, case) -> dict:
    """ranx metrics for ONE case. items = the retrieved ranking (best first)."""
    if not case.expected_document:
        return dict(_UNSCORED)
    if not items:
        return {"hit": False, "recall_at_k": 0.0, "precision_at_k": 0.0,
                "mrr": 0.0, "ndcg": 0.0}

    k = len(items)
    rels = {f"d{i}": 1 for i, it in enumerate(items) if relevant(it, case)}
    if not rels:
        return {"hit": False, "recall_at_k": 0.0, "precision_at_k": 0.0,
                "mrr": 0.0, "ndcg": 0.0}

    try:
        from ranx import Qrels, Run, evaluate
        qid = str(case.id)
        qrels = Qrels({qid: rels})
        # rank-preserving descending scores (ranx only consumes the ORDER)
        run = Run({qid: {f"d{i}": float(k - i) for i in range(k)}})
        with _RANX_LOCK:
            m = evaluate(qrels, run,
                         [f"recall@{k}", f"precision@{k}", "mrr", f"ndcg@{k}"])
        return {
            "hit": True,
            "recall_at_k": round(float(m[f"recall@{k}"]), 3),
            "precision_at_k": round(float(m[f"precision@{k}"]), 3),
            "mrr": round(float(m["mrr"]), 3),
            "ndcg": round(float(m[f"ndcg@{k}"]), 3),
        }
    except Exception as e:                     # pragma: no cover — ranx failure
        logger.warning(f"[EVAL] ranx scoring failed ({e}) — case unscored")
        return dict(_UNSCORED)


def avg(key: str, rows: list):
    """Mean of a numeric per-case field, ignoring None/absent."""
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return round(sum(vals) / len(vals), 3) if vals else None
