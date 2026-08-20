"""
Node 3 — VALIDATE SQL.

Runs the five-check chain (validators/). On success the state carries the
SAFE SQL — the row-limited, dialect-rendered string that the executor will
run. The model's raw string is never executed.

On failure the exact check name and message are stored: that message is
what the correction node feeds back to the LLM, and it is why the loop
converges instead of guessing again.
"""
from __future__ import annotations

import logging
import time

from app.services.data_agent.state import AgentState, stamp
from app.services.data_agent.validators import ValidationFailed, validate

logger = logging.getLogger(__name__)


def validate_sql(state: AgentState) -> AgentState:
    from app.database import SessionLocal
    from app.models.data_agent import DataSource

    if state.get("insufficient"):
        state["valid"] = False
        return state

    t0 = time.perf_counter()
    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(
            DataSource.id == state["source_id"]).first()
        safe_sql, checks = validate(db, source, state.get("sql") or "")
        state["sql"] = safe_sql                     # execute ONLY this
        state["checks"] = [c.as_dict() for c in checks]
        state["valid"] = True
    except ValidationFailed as e:
        state["valid"] = False
        state.setdefault("errors", []).append({"check": e.check,
                                               "message": e.message})
        state["checks"] = (state.get("checks") or []) + [e.as_check().as_dict()]
        logger.info(f"[DATA-AGENT/validate] rejected ({e.check}): {e.message}")
    except Exception as e:
        state["valid"] = False
        state.setdefault("errors", []).append({"check": "validator",
                                               "message": f"{e!r}"})
    finally:
        db.close()
    stamp(state, f"validate_{state.get('attempts', 1)}", t0)
    return state
