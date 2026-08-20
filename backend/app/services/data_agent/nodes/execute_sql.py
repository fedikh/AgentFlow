"""
Node 5 — EXECUTE SQL.

The ONLY place in the platform that runs a statement against a customer
database. Every execution — including anything a Vanna helper might attempt
— comes through `run_validated`, which re-runs the FULL validator chain
even on SQL that was already validated in the graph. Belt and braces: the
function is also the target of the safe `vn.run_sql` override, so there is
no second door.

Order per call:
    validate (5 checks) → read-only session + statement timeout
    → EXPLAIN dry run → execute → fetch row_limit + 1
The extra row is how truncation is detected honestly, then dropped.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import text

from app.services.data_agent.state import AgentState, stamp

logger = logging.getLogger(__name__)


def run_validated(source_id: str, sql: str) -> dict:
    """→ {columns, rows, row_count, truncated, sql}. Raises ValidationFailed
    (rejected) or the driver error (execution problem)."""
    from app.database import SessionLocal
    from app.models.data_agent import DataSource
    from app.services.data_agent.database import adapter_for, connection
    from app.services.data_agent.validators import validate

    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(DataSource.id == source_id).first()
        if not source:
            raise RuntimeError("Data source not found")
        adapter = adapter_for(source.dialect)
        safe_sql, _checks = validate(db, source, sql, adapter)

        cap = int(getattr(source, "row_limit", 1000) or 1000)
        with connection(source) as conn:
            try:
                adapter.explain(conn, safe_sql)
            except Exception as e:
                raise RuntimeError(f"The database rejected the query: "
                                   f"{str(e).splitlines()[0][:200]}")
            cursor = conn.execute(text(safe_sql))
            columns = list(cursor.keys())
            fetched = cursor.fetchmany(cap + 1)

        truncated = len(fetched) > cap
        rows = [[_cell(v) for v in r] for r in fetched[:cap]]
        return {"columns": columns, "rows": rows, "row_count": len(rows),
                "truncated": truncated, "sql": safe_sql}
    finally:
        db.close()


def _cell(v):
    """JSON-safe values (dates, decimals, bytes, UUIDs…)."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    return str(v)


def execute_sql(state: AgentState) -> AgentState:
    t0 = time.perf_counter()
    try:
        state["result"] = run_validated(state["source_id"], state["sql"])
        state["sql"] = state["result"]["sql"]      # the exact string that ran
    except Exception as e:
        state["exec_error"] = str(e)[:300]
        logger.warning(f"[DATA-AGENT/execute] {e!r}")
    stamp(state, "execute", t0)
    return state
