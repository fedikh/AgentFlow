import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
import enum

class ChunkStrategy(str, enum.Enum):
    FIXED       = "FIXED"
    SEMANTIC    = "SEMANTIC"
    HIERARCHICAL = "HIERARCHICAL"

class RAGSpace(Base):
    __tablename__ = "rag_spaces"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name            = Column(String, nullable=False)
    description     = Column(String, default="")
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    chunk_size      = Column(Integer, default=512)
    chunk_overlap   = Column(Integer, default=50)
    top_k           = Column(Integer, default=5)
    chunk_strategy  = Column(SAEnum(ChunkStrategy), default=ChunkStrategy.FIXED)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    organization = relationship("Organization")
    documents    = relationship("Document", back_populates="rag_space", cascade="all, delete-orphan")