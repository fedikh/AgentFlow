from pydantic import BaseModel
from enum import Enum
from typing import Optional

class ChunkStrategy(str, Enum):
    FIXED        = "FIXED"
    SEMANTIC     = "SEMANTIC"
    HIERARCHICAL = "HIERARCHICAL"

# ── Create RAG Space ──────────────────────────────────
class CreateRAGSpaceRequest(BaseModel):
    name:           str
    description:    str = ""
    chunk_size:     int = 512
    chunk_overlap:  int = 50
    top_k:          int = 5
    chunk_strategy: ChunkStrategy = ChunkStrategy.FIXED

class UpdateRAGSpaceRequest(BaseModel):
    name:           Optional[str] = None
    description:    Optional[str] = None
    chunk_size:     Optional[int] = None
    chunk_overlap:  Optional[int] = None
    top_k:          Optional[int] = None
    chunk_strategy: Optional[ChunkStrategy] = None

# ── Query ─────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str

class SourceChunk(BaseModel):
    content:   str
    document:  str
    page:      int = 0
    score:     float = 0.0

class QueryResponse(BaseModel):
    answer:  str
    sources: list[SourceChunk]