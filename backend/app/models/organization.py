import uuid
from sqlalchemy import Column, String, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
import enum

class OrgType(str, enum.Enum):
    PERSONAL = "PERSONAL"
    BUSINESS = "BUSINESS"

class Organization(Base):
    __tablename__ = "organizations"

    id               = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name             = Column(String, nullable=False)
    type             = Column(SAEnum(OrgType), nullable=False, default=OrgType.PERSONAL)
    subscription_plan = Column(String, default="free")
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    users    = relationship("User",    back_populates="organization")