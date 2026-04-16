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

class User(Base):
    __tablename__ = "users"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name            = Column(String, nullable=False)
    email           = Column(String, unique=True, nullable=False, index=True)
    password_hash   = Column(String, nullable=False)
    role            = Column(SAEnum(RoleType), nullable=False, default=RoleType.ADMIN)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    organization = relationship("Organization", back_populates="users")