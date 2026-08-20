"""
Node 7 — GENERATE ANSWER.

Four honest outcomes, in priority order:
    1. not a data question  → the conversational reply from analyze
    2. INSUFFICIENT_SCHEMA  → the sentinel, VERBATIM (the model refused to
                              invent; hiding that would be dishonest)
    3. retries exhausted /   → what was tried and why it failed. Never a
       execution error         fabricated answer.
    4. success              → row count + observations, and an LLM prose
                              summary ONLY when the agent opts in to sending
                              rows outside the database boundary.

The generated SQL is always returned by the orchestrator, whatever the
outcome — that is not optional in this product.
"""
from __future__ import annotations

import logging
import time

from app.services.data_agent.state import AgentState, stamp

logger = logging.getLogger(__name__)

_PREVIEW_ROWS = 20


def generate_answer(state: AgentState) -> AgentState:
    t0 = time.perf_counter()

    if state.get("answer"):                          # analyze already replied
        stamp(state, "answer", t0)
        return state

    if state.get("insufficient"):
        state["answer"] = state["insufficient"]
    elif state.get("exec_error"):
        state["answer"] = (f"The query was validated but the database rejected "
                           f"it: {state['exec_error']}")
    elif not state.get("valid"):
        errors = state.get("errors") or []
        last = errors[-1].get("message") if errors else "unknown error"
        state["answer"] = (
            f"I couldn't produce a valid query for this after "
            f"{state.get('attempts', 0)} attempt(s). Last problem: {last}")
    else:
        state["answer"] = _summarize(state)

    stamp(state, "answer", t0)
    return state


def _summarize(state: AgentState) -> str:
    result = state["result"]
    n = result["row_count"]
    parts = [f"**{n} row{'s' if n != 1 else ''}** returned."]

    # a single scalar is the answer — say it plainly
    if n == 1 and len(result["columns"]) == 1:
        parts.append(f"Answer: **{result['rows'][0][0]}**")

    parts.extend(state.get("result_notes") or [])
    text = " ".join(parts)

    llm = _llm_summary(state)
    return f"{text}\n\n{llm}" if llm else text


def _llm_summary(state: AgentState) -> str:
    """Prose summary — rows leave the database boundary ONLY when the agent
    explicitly enables it (send_results_to_llm, off by default)."""
    from app.database import SessionLocal
    from app.models.data_agent import DataSource
    from app.services.data_agent.config import generation_config
    from app.services.data_agent.vanna.client import get_client
    from app.services.data_agent.vanna.prompts import build_answer_prompt

    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(
            DataSource.id == state["source_id"]).first()
        if not source or not generation_config(source).send_results_to_llm:
            return ""
        result = state["result"]
        head = [result["columns"]] + result["rows"][:_PREVIEW_ROWS]
        preview = "\n".join(" | ".join(str(v) for v in row) for row in head)
        vn = get_client(db, source)
        prompt = build_answer_prompt(state["question"], state["sql"],
                                     result["row_count"],
                                     bool(result.get("truncated")), preview)
        out = vn.submit_prompt([vn.user_message(prompt)])
        return (out or "").strip()
    except Exception as e:
        logger.warning(f"[DATA-AGENT/answer] LLM summary failed: {e!r}")
        return ""
    finally:
        db.close()
