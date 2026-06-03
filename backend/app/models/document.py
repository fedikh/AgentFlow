"""
Document model — updated with extracted_content for the review flow.

Status flow:
    UPLOADING → EXTRACTED → PROCESSING → INDEXED → ERROR

UPLOADING:   fichier en cours d'upload
EXTRACTED:   texte extrait, en attente de review par l'IT
PROCESSING:  chunking + embedding en cours
INDEXED:     chunks créés et embeddés dans pgvector
ERROR:       erreur à n'importe quelle étape
"""
import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
import enum


class DocStatus(str, enum.Enum):
    UPLOADING  = "UPLOADING"
    EXTRACTED  = "EXTRACTED"
    PROCESSING = "PROCESSING"
    INDEXED    = "INDEXED"
    ERROR      = "ERROR"


class Document(Base):
    __tablename__ = "documents"

    id                = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_name         = Column(String, nullable=False)
    file_type         = Column(String, default="pdf")
    file_size         = Column(Integer, default=0)
    source_type       = Column(String, default="local")       # local / url / gdrive / onedrive
    source_url        = Column(String, nullable=True)          # URL si source web/drive
    num_chunks        = Column(Integer, default=0)
    status            = Column(SAEnum(DocStatus), default=DocStatus.UPLOADING)
    error_msg         = Column(String, nullable=True)
    extracted_content = Column(Text, nullable=True)            # texte brut extrait (JSON)
    rag_space_id      = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"), nullable=False)
    uploaded_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    rag_space = relationship("RAGSpace", back_populates="documents")
    chunks    = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
