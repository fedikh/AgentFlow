"""
Data Agent — the LangGraph state.

ONE dict flows through every node; each node adds its own keys and never
mutates another's. That is what makes the run inspectable: the final state
IS the decision trace persisted on the message.
"""
from __future__ import annotations

import time
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # ── inputs ──
    source_id: str
    question: str

    # ── analyze ──
    is_data_question: bool
    intent: str                    # smalltalk | documents | data
    analysis: dict                 # {reason, normalized_question}

    # ── document answering (the RAG path) ──
    answered_from: str             # "documents" when grounded in uploads
    doc_sources: list              # [{document, page, score, method}]

    # ── retrieval (what the RAG index returned, per kind) ──
    retrieval: dict                # {ddl: [...], sql: [...], business: [...]}

    # ── generate / correct ──
    sql: str
    attempts: int
    errors: list                   # validation errors, oldest → newest
    insufficient: str              # the INSUFFICIENT_SCHEMA sentinel, verbatim

    # ── validate ──
    valid: bool
    checks: list                   # [{check, ok, detail}] — the 5 checks

    # ── execute ──
    result: dict                   # {columns, rows, row_count, truncated, sql}
    exec_error: str

    # ── analyze_result / answer ──
    result_notes: list             # human-readable observations about the rows
    answer: str

    # ── profiling ──
    timings: dict


def new_state(source_id: str, question: str) -> AgentState:
    return {"source_id": source_id, "question": question,
            "attempts": 0, "errors": [], "checks": [], "timings": {}}


def stamp(state: AgentState, key: str, t0: float) -> None:
    """Record a stage duration in ms (the retrieval-engine timings pattern)."""
    state.setdefault("timings", {})[key] = round((time.perf_counter() - t0) * 1000, 1)


def trace(state: AgentState) -> dict[str, Any]:
    """The persisted decision trace — everything but the data rows."""
    return {
        "is_data_question": state.get("is_data_question", True),
        "intent": state.get("intent"),
        "answered_from": state.get("answered_from") or "sql",
        "doc_sources": state.get("doc_sources"),
        "analysis": state.get("analysis"),
        "attempts": state.get("attempts"),
        "checks": state.get("checks"),
        "errors": state.get("errors"),
        "insufficient": bool(state.get("insufficient")),
        "retrieved": {k: len(v) for k, v in (state.get("retrieval") or {}).items()},
        "result_notes": state.get("result_notes"),
    }
