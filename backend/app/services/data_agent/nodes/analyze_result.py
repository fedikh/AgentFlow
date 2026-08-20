"""
Node 6 — ANALYZE RESULT.

A query can be valid, execute fine, and still be useless: zero rows because
a filter value was misspelled, or a single NULL because the aggregate hit no
matching rows. This node produces short, honest observations that the answer
node passes to the user — no silent "0 results, here you go".

Purely deterministic: no LLM call, no data leaving the boundary.
"""
from __future__ import annotations

import time

from app.services.data_agent.state import AgentState, stamp


def analyze_result(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    notes: list[str] = []
    result = state.get("result") or {}
    rows, columns = result.get("rows") or [], result.get("columns") or []

    if state.get("exec_error"):
        notes.append("The query failed to execute.")
    elif not rows:
        notes.append("The query ran successfully but matched no rows — the "
                     "filter values may not exist in the data (check spelling "
                     "and casing) or the period may be empty.")
    else:
        if result.get("truncated"):
            notes.append(f"Results were truncated at the row limit "
                         f"({len(rows)} rows shown).")
        if len(rows) == 1 and len(columns) == 1 and rows[0][0] is None:
            notes.append("The aggregate returned NULL — no rows matched the "
                         "filters.")
        empty_cols = [c for i, c in enumerate(columns)
                      if all(r[i] in (None, "") for r in rows)]
        if empty_cols and len(empty_cols) < len(columns):
            notes.append(f"Column(s) {', '.join(empty_cols[:4])} are empty in "
                         "every returned row.")

    state["result_notes"] = notes
    stamp(state, "analyze_result", t0)
    return state
