"""
Orchestrator — the public entry point of the Data Agent.

Owns what the graph deliberately does not: access control, conversation
sessions (the chat.py pattern — user-scoped SQL, 404 rather than 403),
timing assembly and message persistence with the full decision trace.

The generated SQL is ALWAYS in the response. Every mode. No exception.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.data_agent import (DataAgentMessage, DataAgentSession,
                                   DataSource, DataSourceAccess)
from app.services.data_agent.state import trace

logger = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 2000


def _role(user) -> str:
    r = str(getattr(user, "role", "") or "")
    return r.split(".")[-1] if "." in r else r


def check_source_access(db: Session, source: DataSource, user) -> None:
    """Mirror of check_space_access: admin/owner always; everyone else needs
    a DEPLOYED, published agent of a department they belong to — and to be
    on the allowed list when one is set."""
    if _role(user) == "ADMIN" or source.owner_id == user.id:
        return
    if source.status != "deployed" or source.is_private:
        raise HTTPException(403, "This data agent is not available")
    dept_ids = {d.id for d in getattr(user, "departments", [])}
    if source.department_id and source.department_id not in dept_ids:
        raise HTTPException(403, "You are not a member of this agent's department")
    allowed = [a.user_id for a in db.query(DataSourceAccess)
               .filter(DataSourceAccess.data_source_id == source.id).all()]
    if allowed and user.id not in allowed:
        raise HTTPException(403, "You are not allowed to use this data agent")


def _source_for(db: Session, user, source_id: str) -> DataSource:
    source = (db.query(DataSource)
              .filter(DataSource.id == source_id,
                      DataSource.organization_id == user.organization_id).first())
    if not source:
        raise HTTPException(404, "Data agent not found")
    check_source_access(db, source, user)
    return source


def _owned_session(db: Session, session_id: str, user) -> DataAgentSession:
    s = (db.query(DataAgentSession)
         .filter(DataAgentSession.id == session_id,
                 DataAgentSession.user_id == user.id).first())
    if not s:
        raise HTTPException(404, "Conversation not found")
    return s


def _session_dict(s: DataAgentSession) -> dict:
    return {"id": s.id, "title": s.title, "data_source_id": s.data_source_id,
            "message_count": s.message_count,
            "last_message_at": str(s.last_message_at or s.created_at)}


def ask(db: Session, user, source_id: str, question: str,
        session_id: str | None = None) -> dict:
    from app.services.data_agent.config import generation_config
    from app.services.data_agent.graph import run as run_graph

    question = (question or "").strip()
    if not question:
        raise HTTPException(400, "Empty question")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(400, f"Question too long (max {MAX_QUESTION_CHARS})")

    source = _source_for(db, user, source_id)
    if source.status not in ("trained", "stale", "deployed"):
        raise HTTPException(409, "Train this agent first (Schema & Training → Train)")

    session = (_owned_session(db, session_id, user) if session_id else
               DataAgentSession(user_id=user.id, data_source_id=source_id,
                                title=question[:60]))
    if not session_id:
        db.add(session)
        db.flush()

    t0 = time.perf_counter()
    state = run_graph(source_id, question,
                      max_attempts=generation_config(source).max_retries)
    timings = dict(state.get("timings") or {})
    timings["total"] = round((time.perf_counter() - t0) * 1000, 1)

    result = state.get("result") or {}
    errors = state.get("errors") or []
    db.add(DataAgentMessage(session_id=session.id, role="user", content=question))
    db.add(DataAgentMessage(
        session_id=session.id, role="assistant",
        content=state.get("answer") or "",
        generated_sql=state.get("sql"), dialect=source.dialect,
        attempts=state.get("attempts"),
        validation_errors=json.dumps(errors, default=str),
        row_count=result.get("row_count"),
        truncated=bool(result.get("truncated")),
        timings_ms=json.dumps(timings),
        decision_trace=json.dumps(trace(state), default=str)))
    session.message_count = (session.message_count or 0) + 2
    session.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)

    return {
        "session": _session_dict(session),
        "answer": state.get("answer"),
        "sql": state.get("sql"),                       # always present
        "columns": result.get("columns") or [],
        "rows": result.get("rows") or [],
        "row_count": result.get("row_count"),
        "truncated": bool(result.get("truncated")),
        "attempts": state.get("attempts"),
        "answered_from": state.get("answered_from") or "sql",
        "doc_sources": state.get("doc_sources") or [],
        "checks": state.get("checks") or [],
        "validation_errors": errors,
        "result_notes": state.get("result_notes") or [],
        "retrieval": state.get("retrieval") or {},
        "timings_ms": timings,
    }


def execute_edited(db: Session, user, source_id: str, sql: str) -> dict:
    """Re-run a human-edited query — the FULL validator chain runs again."""
    from app.services.data_agent.nodes import run_validated
    from app.services.data_agent.validators import ValidationFailed

    _source_for(db, user, source_id)
    try:
        return run_validated(source_id, sql)
    except ValidationFailed as e:
        raise HTTPException(400, f"Rejected ({e.check}): {e.message}")
    except Exception as e:
        raise HTTPException(400, f"Execution failed: {str(e)[:300]}")


def list_sessions(db: Session, user, limit: int = 50) -> list:
    rows = (db.query(DataAgentSession)
            .filter(DataAgentSession.user_id == user.id,
                    DataAgentSession.status == "ACTIVE")
            .order_by(DataAgentSession.last_message_at.desc())
            .limit(limit).all())
    return [_session_dict(s) for s in rows]


def get_session(db: Session, user, session_id: str) -> dict:
    s = _owned_session(db, session_id, user)
    msgs = []
    for m in s.messages:
        d = {"role": m.role, "content": m.content, "created_at": str(m.created_at)}
        if m.role == "assistant":
            d.update({"sql": m.generated_sql, "attempts": m.attempts,
                      "row_count": m.row_count, "truncated": bool(m.truncated),
                      "timings_ms": json.loads(m.timings_ms or "{}"),
                      "validation_errors": json.loads(m.validation_errors or "[]"),
                      "decision_trace": json.loads(m.decision_trace or "{}")})
        msgs.append(d)
    return {"session": _session_dict(s), "messages": msgs}


def delete_session(db: Session, user, session_id: str) -> dict:
    s = _owned_session(db, session_id, user)
    db.delete(s)
    db.commit()
    return {"deleted": True}
