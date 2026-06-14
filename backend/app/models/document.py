"""
Document model — Loader/Parser split.

Status flow:
    UPLOADING → LOADED → EXTRACTED → PROCESSING → INDEXED
                                                 ↘ ERROR (any step)
"""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base


class DocStatus(str, enum.Enum):
    UPLOADING  = "UPLOADING"
    LOADED     = "LOADED"       # raw text loaded by LlamaIndex Loader
    EXTRACTED  = "EXTRACTED"    # structured blocks created by Parser
    PROCESSING = "PROCESSING"   # chunking + embedding in progress
    INDEXED    = "INDEXED"      # chunks stored in pgvector
    ERROR      = "ERROR"


class Document(Base):
    __tablename__ = "documents"

    id                = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_name         = Column(String, nullable=False)
    file_type         = Column(String, default="pdf")
    file_size         = Column(Integer, default=0)
    source_type       = Column(String, default="local")       # "local" | "url"
    source_url        = Column(String, nullable=True)
    num_chunks        = Column(Integer, default=0)
    status            = Column(SAEnum(DocStatus), default=DocStatus.UPLOADING)
    error_msg         = Column(String, nullable=True)

    # ── Loader output ──
    loaded_content    = Column(Text, nullable=True)   # JSON: {raw_text, num_pages, file_type, category, metadata, total_chars}

    # ── Parser output ──
    extracted_content = Column(Text, nullable=True)   # JSON: [{type, content, page}]

    rag_space_id      = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"), nullable=False)
    uploaded_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    rag_space = relationship("RAGSpace", back_populates="documents")
    chunks    = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")