"""
Chat routes — persistent conversations of end users with deployed agents.

    GET    /chat/agents/{space_id}/sessions          my sessions with this agent
    POST   /chat/agents/{space_id}/sessions          new empty conversation
    POST   /chat/agents/{space_id}/messages          send (auto-creates a
                                                     session when session_id
                                                     is absent) → answer +
                                                     sources + session
    GET    /chat/sessions/{session_id}               meta + full transcript
    PATCH  /chat/sessions/{session_id}               rename / archive / restore
    DELETE /chat/sessions/{session_id}               delete (messages cascade)

Auth = the platform JWT (cookie or Bearer), same as every other route.
Isolation lives in the service: sessions are always fetched scoped to the
caller, and every send re-runs the agent's consumption access check.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.routes.rag import _get_current_user
from app.services.chat import service as chat_service

router = APIRouter(prefix="/chat", tags=["Chat"])


class SendMessageRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    archived: Optional[bool] = None


@router.get("/agents/{space_id}/sessions")
def list_sessions(space_id: str, request: Request, archived: bool = False,
                  db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return chat_service.list_sessions(db, user, space_id,
                                      include_archived=archived)


@router.post("/agents/{space_id}/sessions", status_code=201)
def create_session(space_id: str, data: CreateSessionRequest, request: Request,
                   db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return chat_service.create_session(db, user, space_id, data.title)


@router.post("/agents/{space_id}/messages")
def send_message(space_id: str, data: SendMessageRequest, request: Request,
                 db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return chat_service.send_message(db, user, space_id, data.question,
                                     data.session_id)


@router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request,
                db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return chat_service.get_session(db, user, session_id)


@router.patch("/sessions/{session_id}")
def update_session(session_id: str, data: UpdateSessionRequest,
                   request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return chat_service.update_session(db, user, session_id,
                                       title=data.title,
                                       archived=data.archived)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, request: Request,
                   db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return chat_service.delete_session(db, user, session_id)
