"""
Chat layer — persistent, per-user conversations with deployed agents.

Two tables, created by create_all like every other model:

    chat_sessions   one conversation of ONE user with ONE deployed agent.
                    Isolation is structural: every query filters on user_id,
                    so a user can never see another user's sessions. The
                    rolling long-term memory lives here (summary +
                    summary_upto) — one summary per conversation, updated in
                    the background as the conversation grows.
    chat_messages   every user question and assistant answer, in order.
                    Assistant rows keep their sources (JSON) so reloading an
                    old conversation shows the same citations as live chat.

users / departments / deployed chatbots already exist (users,
user_departments, departments, rag_spaces) — sessions reference them by FK
with ON DELETE CASCADE so deleting a user or a space cleans its chats up.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, ForeignKey, Index, Integer, String,
                        Text)
from sqlalchemy.orm import relationship

from app.database import Base


def _now():
    return datetime.now(timezone.utc)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Platform conversations set user_id; Agent-API conversations (external
    # apps calling /v1 with an API key) set api_key_id + external_user_id
    # instead — the caller's own user identifier, e.g. an employee number.
    user_id      = Column(String, ForeignKey("users.id", ondelete="CASCADE"),
                          nullable=True, index=True)
    rag_space_id = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    api_key_id   = Column(String, ForeignKey("agent_api_keys.id", ondelete="CASCADE"),
                          nullable=True, index=True)
    external_user_id = Column(String, nullable=True)

    title  = Column(String, default="New chat")
    status = Column(String, default="ACTIVE")          # ACTIVE | ARCHIVED

    # Long-term memory: rolling summary of everything OLDER than the recent
    # window; summary_upto = how many messages are already folded in.
    summary      = Column(Text, default="")
    summary_upto = Column(Integer, default=0)

    message_count   = Column(Integer, default=0)
    last_message_at = Column(DateTime, default=_now)
    created_at      = Column(DateTime, default=_now)

    messages = relationship("ChatMessage", back_populates="session",
                            cascade="all, delete-orphan",
                            order_by="ChatMessage.created_at")

    # the hot queries: "this user's sessions with this agent, newest first" —
    # for platform users and for API consumers' external users
    __table_args__ = (
        Index("ix_chat_sessions_user_space_last",
              "user_id", "rag_space_id", "last_message_at"),
        Index("ix_chat_sessions_key_ext_last",
              "api_key_id", "external_user_id", "last_message_at"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("chat_sessions.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    role       = Column(String, nullable=False)        # user | assistant
    content    = Column(Text, nullable=False)
    sources    = Column(Text, nullable=True)           # JSON list (assistant rows)
    latency_ms = Column(Integer, nullable=True)        # assistant rows: total ms
    created_at = Column(DateTime, default=_now)

    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )
