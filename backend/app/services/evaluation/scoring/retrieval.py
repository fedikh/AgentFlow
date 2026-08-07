"""
Scoring — retrieval. ranx (deterministic IR evaluation, no AI, free).

Gold labels are DOCUMENT-level (expected_document [+ expected_page]) — nobody
annotates which CHUNKS of that document answer the question. At that label
granularity the honest headline metric is the HIT RATE — was the expected
document retrieved in the top-K at all? True recall is unmeasurable here: its
denominator (the number of truly relevant chunks) is unknown, and counting
every chunk of the gold document as relevant would be wrong in the other
direction (a 40-chunk document with 2 answering chunks would cap perfect
retrieval at 5/40). The other metrics qualify each hit:

    Hit rate@K     expected document in the top K? (per-case 0/1, averaged
                   across labeled cases)
    Precision@K    fraction of the K slots occupied by the expected document.
                   Ceiling caveat: a gold document that only yields G < K
                   matching chunks caps the case at G/K by construction.
    MRR            1 / rank of the first matching chunk
    NDCG@K         position-discounted gain over the matching chunks FOUND.
                   IDCG is normalized against found gold chunks only (the
                   full gold set is unknown) — it rewards packing what was
                   found at the top; it cannot penalize gold chunks that were
                   never retrieved.

K = the space's configured Top-K, FIXED across the run so per-case numbers
average into one comparable figure (precision@6 and precision@10 are not the
same metric); the actual retrieved count is stored per case as n_retrieved.
Cases without an expected_document return None everywhere so the runner can
report labeled vs unlabeled counts honestly.

Pages: ingestion stores 1-indexed page numbers (page 1 = first page), and
expected_page labels are compared against them after int coercion.
"""
from __future__ import annotations

import threading
from pathlib import Path

from ..common import logger

# ranx runs on numba, whose default (workqueue) threading layer is NOT
# thread-safe — the runner fans cases out over a worker pool, so the actual
# ranx call is serialized. Per-case calls (instead of one batched evaluate at
# the end of the run) are deliberate: the math is microseconds, and per-case
# scoring is what feeds the live case-by-case progress the UI polls for.
_RANX_LOCK = threading.Lock()

# ranx is imported lazily (numba costs seconds at import — not worth paying
# on server startup) but the result is cached: a missing/broken dependency is
# logged loudly ONCE, not once per case.
_ranx_mod = None
_ranx_err = None


def _ranx():
    global _ranx_mod, _ranx_err
    if _ranx_mod is None and _ranx_err is None:
        try:
            import ranx as _m
            _ranx_mod = _m
        except Exception as e:      # pragma: no cover — broken dependency
            _ranx_err = str(e)
            logger.error(f"[EVAL] ranx unavailable — retrieval metrics off: {e}")
    if _ranx_err is not None:
        raise RuntimeError(f"ranx unavailable: {_ranx_err}")
    return _ranx_mod


def _norm(name) -> str:
    """Document identity for matching: basename without extension, casefolded."""
    return Path(str(name or "").strip()).stem.casefold()


def relevant(item: dict, case) -> bool:
    """Gold check — EXACT normalized-name match. Substring matching would let
    'rapport.pdf' claim 'vieux_rapport.pdf' and silently inflate every metric,
    so a label must name the document (extension optional, case-insensitive).
    Pages are int-coerced: a page stored as "12" in JSONB must equal 12."""
    if not case.expected_document:
        return False
    if _norm(case.expected_document) != _norm(item.get("document")):
        return False
    if case.expected_page is None:
        return True
    try:
        return int(case.expected_page) == int(item.get("page"))
    except (TypeError, ValueError):
        return False


_UNSCORED = {"hit": None, "precision_at_k": None, "mrr": None, "ndcg": None}
_MISS = {"hit": False, "hit_rate": 0.0, "precision_at_k": 0.0,
         "mrr": 0.0, "ndcg": 0.0}


def score_case(items: list, case, k: int = 0) -> dict:
    """ranx metrics for ONE case. items = the retrieved ranking (best first),
    k = the space's Top-K cutoff (falls back to len(items))."""
    if not case.expected_document:
        return dict(_UNSCORED)
    k = int(k) if k else len(items)
    items = items[:k]
    n = len(items)
    out = {"n_retrieved": n}
    if not n:
        out.update(_MISS)
        return out

    rels = {f"d{i}": 1 for i, it in enumerate(items) if relevant(it, case)}
    if not rels:
        out.update(_MISS)
        return out

    try:
        rx = _ranx()
        qid = str(case.id)
        qrels = rx.Qrels({qid: rels})
        # rank-preserving descending scores (ranx only consumes the ORDER)
        run = rx.Run({qid: {f"d{i}": float(n - i) for i in range(n)}})
        with _RANX_LOCK:
            m = rx.evaluate(qrels, run, [f"precision@{k}", "mrr", f"ndcg@{k}"])
        out.update({
            "hit": True, "hit_rate": 1.0,
            "precision_at_k": round(float(m[f"precision@{k}"]), 3),
            "mrr": round(float(m["mrr"]), 3),
            "ndcg": round(float(m[f"ndcg@{k}"]), 3),
        })
    except Exception as e:
        # LABELED case whose ranked scoring crashed — the hit is already known
        # from rels, so keep it instead of collapsing into the "no label"
        # None state the runner uses for unlabeled cases.
        logger.warning(f"[EVAL] ranx scoring failed for case {case.id} ({e})")
        out.update(_UNSCORED)
        out.update({"hit": True, "hit_rate": 1.0,
                    "scoring_error": str(e)[:200]})
    return out


def hit_rate(rows: list):
    """Share of labeled cases whose expected document was retrieved.
    Deliberately explicit — avg('hit', rows) would 'work' only because bool
    subclasses int in Python, which is too load-bearing to leave implicit."""
    vals = [1.0 if r["hit"] else 0.0 for r in rows
            if isinstance(r.get("hit"), bool)]
    return round(sum(vals) / len(vals), 3) if vals else None


def avg(key: str, rows: list):
    """Mean of a numeric per-case field, ignoring None/absent. Bools are
    excluded on purpose — booleans have dedicated aggregators (hit_rate)."""
    vals = [r[key] for r in rows
            if isinstance(r.get(key), (int, float))
            and not isinstance(r.get(key), bool)]
    return round(sum(vals) / len(vals), 3) if vals else None
