"""
RAGSpaceAccess — per-user access control WITHIN a department.

Many-to-many between a RAG space and the users allowed to query it.

Access rule (enforced in rag_service.check_space_access):
  - If a space has NO rows here  → every USER of the space's department can query it (default).
  - If a space HAS rows here      → only the listed users can query it.
  ADMIN and IT are never restricted (they build/test the space).
"""
import uuid
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint, Index
from app.database import Base


class RAGSpaceAccess(Base):
    __tablename__ = "rag_space_access"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rag_space_id  = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"), nullable=False)
    user_id       = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("rag_space_id", "user_id", name="uq_space_user"),
        Index("ix_rag_space_access_space", "rag_space_id"),
        Index("ix_rag_space_access_user", "user_id"),
    )
