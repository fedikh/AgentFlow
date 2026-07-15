"""
RAGSpaceCollaborator — IT users the owner grants BUILD permission on a space.

This is the "who can co-build this space" list — distinct from RAGSpaceAccess,
which is "who (end users) can query the deployed space". A space is private to
its creator (owner) by default; adding an IT user here lets them see, edit and
version the space alongside the owner.

Visibility rule (enforced in rag_service):
  - An IT user sees a space if they are the owner OR a collaborator (ADMIN sees all).
  - Legacy spaces with owner_id IS NULL stay visible to every IT (no backfill).
"""
import uuid
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint, Index
from app.database import Base


class RAGSpaceCollaborator(Base):
    __tablename__ = "rag_space_collaborators"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rag_space_id  = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"), nullable=False)
    user_id       = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("rag_space_id", "user_id", name="uq_space_collab"),
        Index("ix_rag_space_collab_space", "rag_space_id"),
        Index("ix_rag_space_collab_user", "user_id"),
    )
