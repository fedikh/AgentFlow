import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class Department(Base):
    __tablename__ = "departments"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name            = Column(String, nullable=False)           # Commerce, RH, Finance...
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization")