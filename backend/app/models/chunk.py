import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Index
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone
from app.database import Base

# Embedding dimension — depends on the model:
# all-MiniLM-L6-v2  = 384
# bge-base-en-v1.5  = 768
# bge-m3            = 1024
# Set this to match your model. We use 384 as safe default.
EMBEDDING_DIM = 1024

class Chunk(Base):
    """
    Table 'chunks' with pgvector.
    
    The 'embedding' column uses pgvector's Vector type
    instead of ARRAY(Float). This enables:
    - <=> operator for cosine distance in SQL
    - IVFFlat / HNSW indexes for fast search
    - No need to load all chunks in Python
    """
    __tablename__ = "chunks"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    content      = Column(Text, nullable=False)
    embedding    = Column(Vector(EMBEDDING_DIM), nullable=True)   # pgvector column
    page         = Column(Integer, default=0)
    chunk_index  = Column(Integer, default=0)
    document_id  = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    rag_space_id = Column(String, ForeignKey("rag_spaces.id", ondelete="CASCADE"), nullable=False)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# Index for fast vector search (created after table exists)
# IVFFlat: good for < 1M vectors, fast to build
# HNSW: better quality, slower to build
chunk_embedding_index = Index(
    "idx_chunk_embedding",
    Chunk.embedding,
    postgresql_using="ivfflat",
    postgresql_with={"lists": 100},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)