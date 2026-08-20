"""
Node 4 — CORRECT SQL (the repair step of the loop).

Instead of failing on the first rejection, the exact validator message is
fed back to the model with the rejected SQL. This is the difference between
an agent that fails 30% of the time and one that fails 5%: the schema
check's message literally lists the columns that DO exist, so the second
attempt is informed rather than another guess.

The loop is bounded by the caller (graph routing, MAX_RETRIES from config).
This node only produces the next candidate.
"""
from __future__ import annotations

import logging
import time

from app.services.data_agent.state import AgentState, stamp

logger = logging.getLogger(__name__)


def correct_sql(state: AgentState) -> AgentState:
    from app.database import SessionLocal
    from app.models.data_agent import DataSource
    from app.services.data_agent.nodes.generate_sql import SENTINEL
    from app.services.data_agent.vanna.client import get_client
    from app.services.data_agent.vanna.prompts import build_correction_prompt

    t0 = time.perf_counter()
    last = (state.get("errors") or [{}])[-1]
    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(
            DataSource.id == state["source_id"]).first()
        vn = get_client(db, source)
        prompt = build_correction_prompt(
            question=state["question"], sql=state.get("sql") or "",
            check=last.get("check", "validation"),
            error=last.get("message", "unknown error"),
            dialect=source.dialect)
        sql = (vn.generate_sql(question=prompt,
                               allow_llm_to_see_data=False) or "").strip()
        state["sql"] = sql
        state["attempts"] = int(state.get("attempts", 0)) + 1
        if SENTINEL in sql:
            state["insufficient"] = sql
    except Exception as e:
        logger.warning(f"[DATA-AGENT/correct] {e!r}")
        state.setdefault("errors", []).append({"check": "correction",
                                               "message": f"{e!r}"})
        state["attempts"] = int(state.get("attempts", 0)) + 1
    finally:
        db.close()
    stamp(state, f"correct_{state.get('attempts', 1)}", t0)
    return state
