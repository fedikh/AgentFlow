import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Enum as SAEnum, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
import enum

class DocStatus(str, enum.Enum):
    PENDING  = "PENDING"
    INDEXING = "INDEXING"
    INDEXED  = "INDEXED"
    ERROR    = "ERROR"

class Document(Base):
    __tablename__ = "documents"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_name    = Column(String, nullable=False)
    file_type    = Column(String, nullable=False)       # pdf, docx, csv, txt
    file_size    = Column(Integer, default=0)            # bytes
    num_chunks   = Column(Integer, default=0)
    status       = Column(SAEnum(DocStatus), default=DocStatus.PENDING)
    error_msg    = Column(Text, default=None)
    rag_space_id = Column(String, ForeignKey("rag_spaces.id"), nullable=False)
    uploaded_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    rag_space = relationship("RAGSpace", back_populates="documents")