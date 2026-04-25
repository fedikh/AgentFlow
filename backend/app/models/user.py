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
    department_id   = Column(String, ForeignKey("departments.id"), nullable=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="users")
    department   = relationship("Department")