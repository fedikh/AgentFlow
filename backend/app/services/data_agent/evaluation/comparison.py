"""
Result-set comparison — the heart of execution accuracy.

Two SQL queries are "the same answer" when their RESULT SETS agree, not when
their text matches: `SELECT count(*) …` and `SELECT COUNT(id) …` must score
identically. Both inputs are `run_validated` payloads:

    {columns: [str], rows: [[cell]], row_count: int, truncated: bool}

Design decisions, in match order:
  · truncation      → indeterminate (None): a capped result set can't be
                      compared honestly, so it leaves the denominator
  · row counts      → extra COLUMNS are tolerated (SELECT *-ish habits);
                      extra ROWS never are
  · scalars         → numeric tolerance ("3" == 3 == 3.000)
  · column alignment→ names and order don't matter; a gen column maps to a
                      gold column only if the FULL projected row multiset
                      matches (per-column multisets alone would accept
                      coincidences on duplicate-valued columns)
  · ordered mode    → for ranking questions ORDER matters: sequences, not
                      multisets

Pure functions, no DB, no LLM — deterministic and unit-testable.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime

_REL_TOL = 1e-6
_DIFF_SAMPLE = 3          # rows shown per side in a mismatch detail
_MAX_ALIGN_COLS = 8       # backtracking guard — beyond this, exact-order only


def _norm_cell(v):
    """Canonical form of one cell so representation differences vanish."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 6)
    s = str(v).strip()
    if s == "":
        return ""
    try:
        return round(float(s), 6)
    except ValueError:
        pass
    # ISO dates: "2024-01-31T00:00:00" and "2024-01-31 00:00:00" == "2024-01-31"
    try:
        d = datetime.fromisoformat(s.replace(" ", "T"))
        if (d.hour, d.minute, d.second, d.microsecond) == (0, 0, 0, 0):
            return d.date().isoformat()
        return d.isoformat()
    except ValueError:
        pass
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        pass
    return s.casefold()


def _num_eq(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        if a == b:
            return True
        scale = max(abs(a), abs(b), 1.0)
        return abs(a - b) <= _REL_TOL * scale
    return a == b


def _norm_rows(result) -> list[tuple]:
    return [tuple(_norm_cell(c) for c in r) for r in (result.get("rows") or [])]


def _sample_diff(gold_rows, gen_rows) -> str:
    g, n = Counter(gold_rows), Counter(gen_rows)
    only_gold = list((g - n).elements())[:_DIFF_SAMPLE]
    only_gen = list((n - g).elements())[:_DIFF_SAMPLE]
    parts = []
    if only_gold:
        parts.append("missing: " + "; ".join(str(r)[:120] for r in only_gold))
    if only_gen:
        parts.append("unexpected: " + "; ".join(str(r)[:120] for r in only_gen))
    return " · ".join(parts) or "rows differ"


def _project(rows: list[tuple], idxs: tuple) -> list[tuple]:
    return [tuple(r[i] for i in idxs) for r in rows]


def _align_columns(gold_rows, gen_rows, n_gold, n_gen, ordered):
    """Find an assignment of DISTINCT generated columns onto the gold columns
    such that the projected generated rows equal the gold rows. Candidates are
    pre-filtered by per-column value multisets; the row-level check is what
    actually decides. → the winning index tuple, or None."""
    gold_cols = [Counter(r[i] for r in gold_rows) for i in range(n_gold)]
    gen_cols = [Counter(r[i] for r in gen_rows) for i in range(n_gen)]
    candidates = [[j for j in range(n_gen) if gen_cols[j] == gold_cols[i]]
                  for i in range(n_gold)]
    if any(not c for c in candidates):
        return None

    gold_key = gold_rows if ordered else Counter(gold_rows)

    def matches(idxs):
        proj = _project(gen_rows, idxs)
        return proj == gold_key if ordered else Counter(proj) == gold_key

    # cheap path: unique candidate per column
    if all(len(c) == 1 for c in candidates):
        idxs = tuple(c[0] for c in candidates)
        return idxs if len(set(idxs)) == n_gold and matches(idxs) else None

    if n_gold > _MAX_ALIGN_COLS:
        return None                     # combinatorial guard

    def backtrack(i, used, acc):
        if i == n_gold:
            return acc if matches(tuple(acc)) else None
        for j in candidates[i]:
            if j in used:
                continue
            out = backtrack(i + 1, used | {j}, acc + [j])
            if out:
                return out
        return None

    out = backtrack(0, set(), [])
    return tuple(out) if out else None


def compare_results(gold: dict, gen: dict, ordered: bool = False) -> dict:
    """→ {"match": 1|0|None, "mode": str, "detail": str}."""
    if gold.get("truncated") or gen.get("truncated"):
        return {"match": None, "mode": "indeterminate",
                "detail": "row cap reached — give the gold SQL an aggregate "
                          "or a LIMIT so the comparison is complete"}

    gold_rows, gen_rows = _norm_rows(gold), _norm_rows(gen)
    if not gold_rows and not gen_rows:
        return {"match": 1, "mode": "both-empty", "detail": "0 rows on both sides"}
    if len(gold_rows) != len(gen_rows):
        return {"match": 0, "mode": "row-count",
                "detail": f"expected {len(gold_rows)} row(s), got {len(gen_rows)}"}

    n_gold = len(gold.get("columns") or [])
    n_gen = len(gen.get("columns") or [])

    # scalar answer — the most common shape ("how many …")
    if len(gold_rows) == 1 and n_gold == 1 and n_gen == 1:
        a, b = gold_rows[0][0], gen_rows[0][0]
        ok = _num_eq(a, b)
        return {"match": 1 if ok else 0, "mode": "scalar",
                "detail": f"{a!r} vs {b!r}"}

    # exact: same width, same order of columns
    if n_gold == n_gen:
        if ordered:
            if gold_rows == gen_rows:
                return {"match": 1, "mode": "exact", "detail": "ordered rows equal"}
        elif Counter(gold_rows) == Counter(gen_rows):
            return {"match": 1, "mode": "exact", "detail": "row sets equal"}

    # column alignment (names/order ignored, extra gen columns tolerated)
    if n_gen >= n_gold >= 1:
        idxs = _align_columns(gold_rows, gen_rows, n_gold, n_gen, ordered)
        if idxs is not None:
            mode = "aligned" if n_gen == n_gold else "with-extras"
            return {"match": 1, "mode": mode,
                    "detail": f"columns matched as {list(idxs)}"
                              + (f" (+{n_gen - n_gold} extra)" if n_gen > n_gold else "")}

    if n_gold == n_gen and not ordered:
        return {"match": 0, "mode": "rows", "detail": _sample_diff(gold_rows, gen_rows)}
    if n_gold == n_gen and ordered:
        detail = ("same rows, wrong order"
                  if Counter(gold_rows) == Counter(gen_rows)
                  else _sample_diff(gold_rows, gen_rows))
        return {"match": 0, "mode": "order", "detail": detail}
    return {"match": 0, "mode": "columns",
            "detail": f"expected {n_gold} column(s), got {n_gen} — values differ"}
