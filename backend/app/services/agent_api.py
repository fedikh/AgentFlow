"""
Agent API — the machine door to deployed agents. Enterprise apps (BI
dashboard, HR portal, mobile backend…) call /v1 with an API key created in
the workspace; the platform web app keeps its own JWT door.

Security model, layer by layer:
  1  authentication   Bearer agf_live_… → SHA-256 → indexed hash lookup.
                      The plaintext key exists only in the caller's vault.
  2  authorization    a key is hard-scoped to ONE agent; the agent must be
                      DEPLOYED and published. Keys can chat — nothing else.
  3  rate limiting    per-key per-minute limit + daily quota (Upstash Redis
                      counters; in-process fallback when Redis is off) → 429.
  4  audit            every authenticated call logged (metadata only, never
                      message content) + last_used/request_count on the key.
  5  identity         the consuming app sends external_user_id (its own
                      authenticated user, e.g. employee id); sessions are
                      isolated per (api key, external_user_id) — workers
                      never see each other's history.

The chat flow reuses the SAME session + memory machinery as the platform
chat (services/chat) — one implementation, two doors.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.api_key import AgentApiKey, AgentApiLog
from app.models.chat import ChatMessage, ChatSession
from app.models.rag_space import RAGSpace

logger = logging.getLogger(__name__)

KEY_PREFIX = "agf_live_"
MAX_QUESTION_CHARS = 4000
MAX_EXTERNAL_ID_CHARS = 128


def _now():
    return datetime.now(timezone.utc)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ══════════════════════════════════════════════════════════════
#  Key management (workspace side — owner/admin only, see routes)
# ══════════════════════════════════════════════════════════════

def _key_dict(k: AgentApiKey) -> dict:
    revoked = k.revoked_at is not None
    expired = k.expires_at is not None and k.expires_at <= _now().replace(tzinfo=None)
    return {
        "id": k.id, "name": k.name, "key_display": k.key_display,
        "status": "revoked" if revoked else "expired" if expired else "active",
        "rate_per_min": k.rate_per_min, "daily_quota": k.daily_quota,
        "created_at": str(k.created_at), "expires_at": str(k.expires_at or "") or None,
        "last_used_at": str(k.last_used_at or "") or None,
        "request_count": k.request_count or 0,
    }


def create_key(db: Session, space, user, name: str,
               expires_days: int | None = None) -> dict:
    """Mint a key. The FULL key appears in this response ONCE — only its
    hash is stored, so it can never be shown again."""
    name = (name or "").strip()[:80] or "Unnamed integration"
    full = KEY_PREFIX + secrets.token_urlsafe(24)
    k = AgentApiKey(
        rag_space_id=space.id,
        organization_id=space.organization_id,
        name=name,
        key_hash=_hash(full),
        key_display=f"{full[:12]}…{full[-4:]}",
        created_by=getattr(user, "id", None),
        expires_at=(_now() + timedelta(days=int(expires_days))
                    if expires_days else None),
    )
    db.add(k)
    db.commit()
    db.refresh(k)
    out = _key_dict(k)
    out["api_key"] = full          # shown once, never stored
    return out


def list_keys(db: Session, space) -> list:
    rows = (db.query(AgentApiKey)
            .filter(AgentApiKey.rag_space_id == space.id)
            .order_by(AgentApiKey.created_at.desc()).all())
    return [_key_dict(k) for k in rows]


def revoke_key(db: Session, space, key_id: str) -> dict:
    k = (db.query(AgentApiKey)
         .filter(AgentApiKey.id == key_id,
                 AgentApiKey.rag_space_id == space.id).first())
    if not k:
        raise HTTPException(404, "API key not found")
    if k.revoked_at is None:
        k.revoked_at = _now()
        db.commit()
    return _key_dict(k)


# ══════════════════════════════════════════════════════════════
#  Public-side: authentication + rate limit + audit
# ══════════════════════════════════════════════════════════════

def authenticate(db: Session, agent_id: str, authorization: str | None):
    """Bearer key → (key row, deployed space). Raises 401/403."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing API key (Authorization: Bearer …)")
    token = authorization[7:].strip()
    if not token.startswith(KEY_PREFIX):
        raise HTTPException(401, "Invalid API key")

    k = db.query(AgentApiKey).filter(AgentApiKey.key_hash == _hash(token)).first()
    if not k or k.revoked_at is not None:
        raise HTTPException(401, "Invalid API key")
    if k.expires_at is not None and k.expires_at <= _now().replace(tzinfo=None):
        raise HTTPException(401, "API key expired")
    if k.rag_space_id != agent_id:
        # scope violation — the key is real but not for this agent
        raise HTTPException(403, "This API key does not grant access to this agent")

    space = db.query(RAGSpace).filter(RAGSpace.id == agent_id).first()
    if not space:
        raise HTTPException(404, "Agent not found")
    status = str(getattr(space, "status", "") or "")
    status = status.split(".")[-1] if "." in status else status
    if status == "EDITING":
        raise HTTPException(409, "Agent is being updated — retry shortly")
    if status != "ACTIVE" or getattr(space, "is_private", False):
        raise HTTPException(403, "Agent is not available")
    return k, space


# Per-minute + per-day counters. Redis (shared across workers) when
# configured; a per-process fallback otherwise so limits always exist.
_local_counts: dict = {}
_local_lock = threading.Lock()


def _bump(counter_key: str, ttl: int) -> int:
    from app.services.chat import cache
    if cache.enabled():
        n = cache.incr(counter_key, ttl)
        if n is not None:
            return n
    with _local_lock:                       # fallback: per-process window
        n = _local_counts.get(counter_key, 0) + 1
        _local_counts[counter_key] = n
        if len(_local_counts) > 10000:      # bound memory; windows rotate keys
            _local_counts.clear()
        return n


def rate_limit(key: AgentApiKey) -> None:
    now = _now()
    minute = now.strftime("%Y%m%d%H%M")
    day = now.strftime("%Y%m%d")
    if _bump(f"api:rl:m:{key.id}:{minute}", 60) > (key.rate_per_min or 60):
        raise HTTPException(429, "Rate limit exceeded — slow down")
    if _bump(f"api:rl:d:{key.id}:{day}", 90000) > (key.daily_quota or 5000):
        raise HTTPException(429, "Daily quota exceeded for this API key")


def audit(db: Session, key: AgentApiKey, status: int, latency_ms: int | None,
          external_user_id: str | None) -> None:
    """Metadata-only usage trail (+ counters the UI shows). Never raises."""
    try:
        db.add(AgentApiLog(api_key_id=key.id, rag_space_id=key.rag_space_id,
                           external_user_id=external_user_id, status=status,
                           latency_ms=latency_ms))
        key.last_used_at = _now()
        key.request_count = (key.request_count or 0) + 1
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"[AGENT-API] audit write failed: {e}")


# ══════════════════════════════════════════════════════════════
#  Chat — same sessions + memory machinery as the platform chat
# ══════════════════════════════════════════════════════════════

def _ext(external_user_id: str | None) -> str:
    """Normalized caller identity; '' groups all traffic of a key that
    doesn't send per-user ids (single shared conversation space)."""
    return (external_user_id or "").strip()[:MAX_EXTERNAL_ID_CHARS]


def _owned_api_session(db: Session, key: AgentApiKey, session_id: str,
                       ext: str) -> ChatSession:
    s = (db.query(ChatSession)
         .filter(ChatSession.id == session_id,
                 ChatSession.api_key_id == key.id,
                 ChatSession.external_user_id == ext).first())
    if not s:
        raise HTTPException(404, "Session not found")
    return s


def _session_dict(s: ChatSession) -> dict:
    return {"id": s.id, "title": s.title, "message_count": s.message_count,
            "external_user_id": s.external_user_id,
            "last_message_at": str(s.last_message_at or s.created_at),
            "created_at": str(s.created_at)}


def chat(db: Session, key: AgentApiKey, space, question: str,
         session_id: str | None, external_user_id: str | None) -> dict:
    from app.schemas.rag import QueryRequest
    from app.services import rag_service
    from app.services.chat.service import (RECENT_WINDOW, SUMMARIZE_AFTER,
                                           _condense_question, _memory_block,
                                           _recent_messages, _summarize_worker)

    question = (question or "").strip()
    if not question:
        raise HTTPException(400, "Empty question")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(400, f"Question too long (max {MAX_QUESTION_CHARS} chars)")
    ext = _ext(external_user_id)

    if session_id:
        session = _owned_api_session(db, key, session_id, ext)
    else:
        session = ChatSession(user_id=None, api_key_id=key.id,
                              external_user_id=ext, rag_space_id=space.id,
                              title=question[:60])
        db.add(session)
        db.flush()

    recent = _recent_messages(db, session.id) if session.message_count else []
    memory = _memory_block(session.summary or "", recent)
    retrieval_q = (_condense_question(db, space, memory, question)
                   if recent else question)

    result = rag_service.query(db, space.id, space.organization_id,
                               QueryRequest(question=retrieval_q), user=None,
                               history=memory)

    now_count = (session.message_count or 0)
    db.add(ChatMessage(session_id=session.id, role="user", content=question))
    db.add(ChatMessage(session_id=session.id, role="assistant",
                       content=result.get("answer") or "",
                       sources=None))          # API replies carry sources inline
    session.message_count = now_count + 2
    session.last_message_at = _now()
    db.commit()
    db.refresh(session)

    if (session.message_count - RECENT_WINDOW) - (session.summary_upto or 0) \
            >= SUMMARIZE_AFTER:
        threading.Thread(target=_summarize_worker, args=(session.id,),
                         daemon=True).start()

    # public payload: no scores/methods internals — document + page + excerpt
    sources = [{"document": s.get("document"), "page": s.get("page"),
                "excerpt": s.get("content")} for s in result.get("sources") or []]
    return {"answer": result.get("answer"), "sources": sources,
            "session_id": session.id,
            "external_user_id": ext or None}


def list_sessions(db: Session, key: AgentApiKey,
                  external_user_id: str | None) -> list:
    ext = _ext(external_user_id)
    rows = (db.query(ChatSession)
            .filter(ChatSession.api_key_id == key.id,
                    ChatSession.external_user_id == ext)
            .order_by(ChatSession.last_message_at.desc()).limit(50).all())
    return [_session_dict(s) for s in rows]


def get_session(db: Session, key: AgentApiKey, session_id: str,
                external_user_id: str | None) -> dict:
    ext = _ext(external_user_id)
    s = _owned_api_session(db, key, session_id, ext)
    msgs = [{"role": m.role, "content": m.content, "created_at": str(m.created_at)}
            for m in s.messages]
    return {"session": _session_dict(s), "messages": msgs}
