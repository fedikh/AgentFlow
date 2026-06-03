import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone
from app.database import Base

EMBEDDING_DIM = 1024

class Chunk(Base):
    __tablename__ = "chunks"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    content      = Column(Text, nullable=False)
    embedding    = Column(Vector(EMBEDDING_DIM), nullable=True)
    page         = Column(Integer, default=0)
    chunk_index  = Column(Integer, default=0)
    document_id  = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    rag_space_id = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"), nullable=False)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relations
    document = relationship("Document", back_populates="chunks")

chunk_embedding_index = Index(
    "idx_chunk_embedding",
    Chunk.embedding,
    postgresql_using="ivfflat",
    postgresql_with={"lists": 100},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)