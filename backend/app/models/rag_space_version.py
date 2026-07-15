"""
RAGSpaceVersion — a saved config snapshot of a RAG space.

Versioning model = CONFIG SNAPSHOTS (not per-version indexes). Each version
stores the full pipeline configuration of the space at save time as a JSON blob
(`config`). The IT saves v1, tweaks the config, saves v2, etc., then DEPLOYS the
chosen version — deploying writes that version's config back onto the RAGSpace
columns and flips the space to ACTIVE.

Only ONE live index exists at a time (the chunks currently in pgvector). When a
version is applied/deployed whose chunking/embedding differs from what is
indexed, the space is flagged `reindex_required=True` so the UI prompts the IT
to re-run Process-all. Per-version indexes (true live A/B) can be layered later
by keying chunks on version_id — this schema leaves room for that.

Status: SAVED (a stored snapshot) → DEPLOYED (the live one) → ARCHIVED (a former
deployed version). `metrics` is reserved for the deferred evaluation step.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, Index
from app.database import Base


class RAGSpaceVersion(Base):
    __tablename__ = "rag_space_versions"

    id             = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rag_space_id   = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"), nullable=False)

    # Monotonic per space (1, 2, 3…) — drives ordering and the default "vN" label.
    version_number = Column(Integer, nullable=False, default=1)
    label          = Column(String, nullable=False, default="v1")
    status         = Column(String, nullable=False, default="SAVED")   # SAVED | DEPLOYED | ARCHIVED
    notes          = Column(Text, nullable=True)

    # JSON snapshot of the space's pipeline columns at save time.
    config         = Column(Text, nullable=True)
    # Reserved for the deferred evaluation step (hit-rate, MRR…). Unused for now.
    metrics        = Column(Text, nullable=True)

    created_by     = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("rag_space_id", "version_number", name="uq_space_version_number"),
        Index("ix_rag_space_versions_space", "rag_space_id"),
    )
