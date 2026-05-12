"""
User model — updated with many-to-many department relationship.

CHANGES:
- REMOVED: department_id column (FK simple)
- REMOVED: department relationship (one-to-one)
- ADDED: departments relationship (many-to-many via user_departments)
"""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
import enum


class RoleType(str, enum.Enum):
    ADMIN = "ADMIN"
    IT    = "IT"
    USER  = "USER"


class UserStatus(str, enum.Enum):
    ACTIVE  = "ACTIVE"
    PENDING = "PENDING"


class User(Base):
    __tablename__ = "users"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name            = Column(String, nullable=True)
    email           = Column(String, unique=True, nullable=False, index=True)
    password_hash   = Column(String, nullable=True)
    role            = Column(SAEnum(RoleType), nullable=False, default=RoleType.ADMIN)
    status          = Column(SAEnum(UserStatus), nullable=False, default=UserStatus.ACTIVE)
    invite_token    = Column(String, nullable=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relationships ──
    organization = relationship("Organization", back_populates="users")

    # Many-to-many: user can belong to multiple departments
    # IT → builds RAG for these departments
    # USER → accesses RAG agents in these departments
    # ADMIN → doesn't use this, sees everything
    departments = relationship(
        "Department",
        secondary="user_departments",
        backref="users",
        lazy="joined",
    )
