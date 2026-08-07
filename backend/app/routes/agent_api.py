"""
Public Agent API (/v1) — consumed by other enterprise apps with an API key.

    POST /v1/agents/{agent_id}/chat                     ask a question
    GET  /v1/agents/{agent_id}/sessions                 sessions of one external user
    GET  /v1/agents/{agent_id}/sessions/{session_id}    one transcript

Auth: Authorization: Bearer agf_live_…   (created in the workspace →
Deploy → API Access). This surface is versioned and consumption-only —
no configuration, no documents, no platform endpoints.

Also here (platform side, JWT auth): key management under
/api/rag/spaces/{space_id}/api-keys — owner/admin only.
"""
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import agent_api

# ── public, key-authenticated ─────────────────────────────────

router = APIRouter(prefix="/v1", tags=["Agent API (public)"])


class ApiChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    external_user_id: Optional[str] = None


@router.post("/agents/{agent_id}/chat")
def api_chat(agent_id: str, data: ApiChatRequest,
             authorization: Optional[str] = Header(None),
             db: Session = Depends(get_db)):
    key, space = agent_api.authenticate(db, agent_id, authorization)
    t0 = time.perf_counter()
    try:
        agent_api.rate_limit(key)
        out = agent_api.chat(db, key, space, data.question,
                             data.session_id, data.external_user_id)
        agent_api.audit(db, key, 200,
                        int((time.perf_counter() - t0) * 1000),
                        data.external_user_id)
        return out
    except HTTPException as e:
        agent_api.audit(db, key, e.status_code,
                        int((time.perf_counter() - t0) * 1000),
                        data.external_user_id)
        raise
    except Exception:
        agent_api.audit(db, key, 500,
                        int((time.perf_counter() - t0) * 1000),
                        data.external_user_id)
        raise HTTPException(500, "Internal error")


@router.get("/agents/{agent_id}/sessions")
def api_sessions(agent_id: str, external_user_id: Optional[str] = None,
                 authorization: Optional[str] = Header(None),
                 db: Session = Depends(get_db)):
    key, _ = agent_api.authenticate(db, agent_id, authorization)
    return agent_api.list_sessions(db, key, external_user_id)


@router.get("/agents/{agent_id}/sessions/{session_id}")
def api_session(agent_id: str, session_id: str,
                external_user_id: Optional[str] = None,
                authorization: Optional[str] = Header(None),
                db: Session = Depends(get_db)):
    key, _ = agent_api.authenticate(db, agent_id, authorization)
    return agent_api.get_session(db, key, session_id, external_user_id)


# ── workspace side: key management (JWT, owner/admin only) ────

mgmt_router = APIRouter(prefix="/rag", tags=["Agent API keys"])


class CreateKeyRequest(BaseModel):
    name: str
    expires_days: Optional[int] = None


def _owner_space(space_id: str, request: Request, db: Session):
    from app.routes.rag import _get_current_user
    from app.services.rag_service import require_owner
    user = _get_current_user(request, db)
    return require_owner(db, space_id, user.organization_id, user), user


@mgmt_router.get("/spaces/{space_id}/api-keys")
def list_api_keys(space_id: str, request: Request, db: Session = Depends(get_db)):
    space, _ = _owner_space(space_id, request, db)
    return agent_api.list_keys(db, space)


@mgmt_router.post("/spaces/{space_id}/api-keys", status_code=201)
def create_api_key(space_id: str, data: CreateKeyRequest, request: Request,
                   db: Session = Depends(get_db)):
    space, user = _owner_space(space_id, request, db)
    return agent_api.create_key(db, space, user, data.name, data.expires_days)


@mgmt_router.delete("/spaces/{space_id}/api-keys/{key_id}")
def revoke_api_key(space_id: str, key_id: str, request: Request,
                   db: Session = Depends(get_db)):
    space, _ = _owner_space(space_id, request, db)
    return agent_api.revoke_key(db, space, key_id)
