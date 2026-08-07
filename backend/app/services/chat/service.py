"""
Chat service — multi-user sessions, history, and conversation memory for
deployed agents.

Isolation model (enterprise security):
  - every session query filters on user_id → a user can never load, rename,
    or delete another user's conversation (404, not 403 — existence is not
    leaked either);
  - every send re-runs the SAME access check as the query endpoint
    (check_space_access): department membership, allowed-users list,
    deployed + published status. Dropping a user from a department instantly
    cuts both the chatbot AND its history behind it.

Memory model (what the LLM sees — never the whole transcript):
  short-term   the last RECENT_WINDOW messages, verbatim (capped chars)
  long-term    a rolling summary of everything OLDER than that window,
               updated by a background thread once enough messages fall out
               of the window (summary + summary_upto on the session row)
  retrieval    follow-up questions ("and for 2023?") are condensed into one
               standalone query with the space's own LLM before retrieval —
               the standard conversational-RAG pattern; on any failure the
               raw question is used.

Prompt construction (see llm_factory.generate):
  system prompt → conversation summary + recent messages → retrieved
  documents → current question.

Caching (chat.cache, Upstash Redis, optional): session lists and transcripts
are read-through cached and invalidated on every mutation. PostgreSQL stays
the source of truth.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.rag import QueryRequest
from app.services.chat import cache
from app.services import rag_service

logger = logging.getLogger(__name__)

RECENT_WINDOW = 8         # messages sent verbatim (short-term memory)
RECENT_CHAR_CAP = 600     # per-message cap inside the memory block
SUMMARIZE_AFTER = 6       # unfolded messages beyond the window → re-summarize
MAX_SESSIONS_LISTED = 50


# ══════════════════════════════════════════════════════════════
#  Serialization
# ══════════════════════════════════════════════════════════════

def _session_dict(s: ChatSession) -> dict:
    return {
        "id": s.id, "rag_space_id": s.rag_space_id, "title": s.title,
        "status": s.status, "message_count": s.message_count,
        "last_message_at": str(s.last_message_at or s.created_at),
        "created_at": str(s.created_at),
    }


def _message_dict(m: ChatMessage) -> dict:
    d = {"id": m.id, "role": m.role, "content": m.content,
         "created_at": str(m.created_at)}
    if m.sources:
        try:
            d["sources"] = json.loads(m.sources)
        except Exception:
            pass
    if m.latency_ms is not None:
        d["latency_ms"] = m.latency_ms
    return d


# ══════════════════════════════════════════════════════════════
#  Ownership + access
# ══════════════════════════════════════════════════════════════

def _owned_session(db: Session, session_id: str, user: User) -> ChatSession:
    """The ONLY way a session is ever fetched — always scoped to the caller."""
    s = (db.query(ChatSession)
         .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
         .first())
    if not s:
        raise HTTPException(404, "Conversation not found")
    return s


def _checked_space(db: Session, space_id: str, user: User):
    """Resolve the agent within the caller's org AND enforce consumption
    access (deployed + published + department member + allowed list)."""
    space = rag_service._find_space(db, space_id, user.organization_id)
    rag_service.check_space_access(db, space, user)
    return space


# ══════════════════════════════════════════════════════════════
#  Sessions CRUD
# ══════════════════════════════════════════════════════════════

def list_sessions(db: Session, user: User, space_id: str,
                  include_archived: bool = False) -> list:
    _checked_space(db, space_id, user)

    if not include_archived:                       # only the default view is cached
        cached = cache.get_json(cache.sessions_key(user.id, space_id))
        if cached is not None:
            return cached

    q = (db.query(ChatSession)
         .filter(ChatSession.user_id == user.id,
                 ChatSession.rag_space_id == space_id))
    if not include_archived:
        q = q.filter(ChatSession.status == "ACTIVE")
    rows = (q.order_by(ChatSession.last_message_at.desc())
            .limit(MAX_SESSIONS_LISTED).all())
    out = [_session_dict(s) for s in rows]

    if not include_archived:
        cache.set_json(cache.sessions_key(user.id, space_id), out,
                       cache.SESSIONS_TTL)
    return out


def create_session(db: Session, user: User, space_id: str,
                   title: str | None = None) -> dict:
    _checked_space(db, space_id, user)
    s = ChatSession(user_id=user.id, rag_space_id=space_id,
                    title=(title or "New chat")[:120])
    db.add(s)
    db.commit()
    db.refresh(s)
    cache.invalidate(cache.sessions_key(user.id, space_id))
    return _session_dict(s)


def get_session(db: Session, user: User, session_id: str) -> dict:
    """Session meta + full transcript (read-through cached)."""
    s = _owned_session(db, session_id, user)

    cached = cache.get_json(cache.messages_key(session_id))
    if cached is not None:
        return {"session": _session_dict(s), "messages": cached}

    msgs = [_message_dict(m) for m in s.messages]
    cache.set_json(cache.messages_key(session_id), msgs, cache.MESSAGES_TTL)
    return {"session": _session_dict(s), "messages": msgs}


def update_session(db: Session, user: User, session_id: str,
                   title: str | None = None,
                   archived: bool | None = None) -> dict:
    s = _owned_session(db, session_id, user)
    if title is not None and title.strip():
        s.title = title.strip()[:120]
    if archived is not None:
        s.status = "ARCHIVED" if archived else "ACTIVE"
    db.commit()
    db.refresh(s)
    cache.invalidate(cache.sessions_key(user.id, s.rag_space_id))
    return _session_dict(s)


def delete_session(db: Session, user: User, session_id: str) -> dict:
    s = _owned_session(db, session_id, user)
    space_id = s.rag_space_id
    db.delete(s)                                  # messages cascade
    db.commit()
    cache.invalidate(cache.sessions_key(user.id, space_id),
                     cache.messages_key(session_id))
    return {"deleted": True}


# ══════════════════════════════════════════════════════════════
#  Conversation memory
# ══════════════════════════════════════════════════════════════

def _recent_messages(db: Session, session_id: str) -> list[ChatMessage]:
    rows = (db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(RECENT_WINDOW).all())
    return list(reversed(rows))


def _memory_block(summary: str, recent: list[ChatMessage]) -> str:
    parts = []
    if summary:
        parts.append(f"Summary of the earlier conversation:\n{summary}")
    if recent:
        lines = [f"{'User' if m.role == 'user' else 'Assistant'}: "
                 f"{m.content[:RECENT_CHAR_CAP]}" for m in recent]
        parts.append("Recent messages:\n" + "\n".join(lines))
    return "\n\n".join(parts)


def _condense_question(db: Session, space, memory: str, question: str) -> str:
    """Follow-ups ('and for 2023?') retrieve badly as-is — rewrite them into
    ONE standalone query with the space's LLM. Raw question on any failure."""
    try:
        from langchain_core.messages import HumanMessage
        from app.services.llm_factory.factory import get_llm
        from app.services.llm_factory.resolver import resolve_llm_config
        llm = get_llm(**resolve_llm_config(db, space))
        out = llm.invoke([HumanMessage(content=(
            "Rewrite the follow-up question as ONE fully standalone question "
            "in the same language, resolving pronouns and references from the "
            "conversation. Reply with ONLY the rewritten question.\n\n"
            f"{memory}\n\nFollow-up question: {question}"))]).content.strip()
        out = out.strip('"').strip()
        if 0 < len(out) <= 400:
            return out
    except Exception as e:
        logger.warning(f"[CHAT] condense failed ({e}) — using raw question")
    return question


def _summarize_worker(session_id: str) -> None:
    """Background long-term memory: fold messages that dropped out of the
    recent window into the rolling summary. Own DB session; failures only
    log — the next send retries naturally."""
    from app.database import SessionLocal
    from app.models.rag_space import RAGSpace
    db = SessionLocal()
    try:
        s = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not s:
            return
        cutoff = (s.message_count or 0) - RECENT_WINDOW
        if cutoff - (s.summary_upto or 0) < SUMMARIZE_AFTER:
            return
        rows = (db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at)
                .offset(s.summary_upto or 0)
                .limit(cutoff - (s.summary_upto or 0)).all())
        if not rows:
            return
        space = db.query(RAGSpace).filter(RAGSpace.id == s.rag_space_id).first()
        if not space:
            return

        from langchain_core.messages import HumanMessage
        from app.services.llm_factory.factory import get_llm
        from app.services.llm_factory.resolver import resolve_llm_config
        lines = "\n".join(f"{'User' if m.role == 'user' else 'Assistant'}: "
                          f"{m.content[:RECENT_CHAR_CAP]}" for m in rows)
        prev = f"CURRENT SUMMARY:\n{s.summary}\n\n" if s.summary else ""
        llm = get_llm(**resolve_llm_config(db, space))
        out = llm.invoke([HumanMessage(content=(
            "Maintain a running summary of a support conversation. "
            f"{prev}NEW MESSAGES:\n{lines}\n\n"
            "Write the updated summary in under 150 words — keep facts, "
            "names, numbers and open questions. Reply with ONLY the "
            "summary."))]).content.strip()
        if out:
            s.summary = out[:4000]
            s.summary_upto = cutoff
            db.commit()
            logger.info(f"[CHAT] session {session_id[:8]} summarized "
                        f"upto={cutoff}")
    except Exception as e:
        logger.warning(f"[CHAT] summarize failed: {e}")
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
#  Send — the RAG + memory integration point
# ══════════════════════════════════════════════════════════════

def send_message(db: Session, user: User, space_id: str, question: str,
                 session_id: str | None = None) -> dict:
    question = (question or "").strip()
    if not question:
        raise HTTPException(400, "Empty question")
    space = _checked_space(db, space_id, user)

    if session_id:
        session = _owned_session(db, session_id, user)
        if session.rag_space_id != space_id:
            raise HTTPException(400, "Session belongs to another agent")
    else:
        session = ChatSession(user_id=user.id, rag_space_id=space_id,
                              title=question[:60])
        db.add(session)
        db.flush()

    # ── memory: summary (long-term) + recent window (short-term) ──
    recent = _recent_messages(db, session.id) if session.message_count else []
    memory = _memory_block(session.summary or "", recent)
    retrieval_q = (_condense_question(db, space, memory, question)
                   if recent else question)

    # ── the existing RAG pipeline, with the memory block for generation ──
    t0 = time.perf_counter()
    result = rag_service.query(db, space_id, user.organization_id,
                               QueryRequest(question=retrieval_q), user,
                               history=memory)
    total_ms = int((time.perf_counter() - t0) * 1000)

    # ── persist both turns (Postgres = source of truth) ──
    now_count = (session.message_count or 0)
    db.add(ChatMessage(session_id=session.id, role="user", content=question))
    db.add(ChatMessage(session_id=session.id, role="assistant",
                       content=result.get("answer") or "",
                       sources=json.dumps(result.get("sources") or [],
                                          default=str),
                       latency_ms=total_ms))
    session.message_count = now_count + 2
    session.last_message_at = datetime.now(timezone.utc)
    if now_count == 0 and (not session.title or session.title == "New chat"):
        session.title = question[:60]
    db.commit()
    db.refresh(session)

    # ── cache: invalidate what changed, mark the user active ──
    cache.invalidate(cache.sessions_key(user.id, space_id),
                     cache.messages_key(session.id))
    cache.touch_activity(user.id)

    # ── long-term memory refresh, off the request path ──
    if (session.message_count - RECENT_WINDOW) - (session.summary_upto or 0) \
            >= SUMMARIZE_AFTER:
        threading.Thread(target=_summarize_worker, args=(session.id,),
                         daemon=True).start()

    return {"session": _session_dict(session),
            "answer": result.get("answer"),
            "sources": result.get("sources") or [],
            "timings": result.get("timings")}
