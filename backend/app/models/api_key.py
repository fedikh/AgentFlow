"""
Agent API keys — machine access to deployed agents from other enterprise
apps (BI dashboards, HR portals, mobile backends…).

Security model:
  - The full key (agf_live_…) is shown ONCE at creation and never stored —
    only its SHA-256 hash. Verification = hash the presented key and look it
    up; a DB leak exposes no usable keys.
  - key_display keeps a recognizable stub (prefix…last4) for the UI.
  - One key is hard-scoped to ONE agent: it can only chat with that agent,
    never read documents or change configuration.
  - Revocation is a timestamp — instant, and the row stays for the audit
    trail. Optional expires_at for time-boxed integrations.

Every call is written to agent_api_logs (metadata only — no message content)
so IT gets per-integration usage, cost visibility, and anomaly evidence.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String

from app.database import Base


def _now():
    return datetime.now(timezone.utc)


class AgentApiKey(Base):
    __tablename__ = "agent_api_keys"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rag_space_id    = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    organization_id = Column(String, nullable=False, index=True)

    name        = Column(String, nullable=False)          # "BI dashboard", "HR portal"…
    key_hash    = Column(String, nullable=False, unique=True, index=True)  # sha256 hex
    key_display = Column(String, nullable=False)          # "agf_live_a8f3…k2Qz"

    rate_per_min = Column(Integer, default=60)            # per-key rate limit
    daily_quota  = Column(Integer, default=5000)          # per-key daily cap

    created_by   = Column(String, nullable=True)          # user id
    created_at   = Column(DateTime, default=_now)
    expires_at   = Column(DateTime, nullable=True)
    revoked_at   = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    request_count = Column(Integer, default=0)            # lifetime counter (UI)


class AgentApiLog(Base):
    __tablename__ = "agent_api_logs"

    id               = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id       = Column(String, ForeignKey("agent_api_keys.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    rag_space_id     = Column(String, nullable=False)
    external_user_id = Column(String, nullable=True)
    status           = Column(Integer, nullable=False)    # HTTP status returned
    latency_ms       = Column(Integer, nullable=True)
    created_at       = Column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_agent_api_logs_key_created", "api_key_id", "created_at"),
    )
