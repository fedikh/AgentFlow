"""
RAGSpace model — FULLY CONFIGURABLE.
Ajout de tous les champs configurables pour le pipeline RAG.

NOUVEAUX CHAMPS:
  Embedding: embedding_provider, embedding_model
  LLM:       llm_provider, llm_model, llm_temperature, llm_max_tokens
  Recherche: search_engine, semantic_weight, reranking_enabled
  Prompt:    system_prompt
  Status:    status (DRAFT → ACTIVE)
"""
import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
import enum


# ══════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════

class ChunkStrategy(str, enum.Enum):
    FIXED        = "FIXED"
    SEMANTIC     = "SEMANTIC"
    HIERARCHICAL = "HIERARCHICAL"


class EmbeddingProvider(str, enum.Enum):
    LOCAL   = "LOCAL"       # sentence-transformers (gratuit)
    OPENAI  = "OPENAI"      # OpenAI API (payant)
    COHERE  = "COHERE"      # Cohere API (payant)


class LLMProvider(str, enum.Enum):
    GROQ    = "GROQ"        # Groq API (gratuit)
    OPENAI  = "OPENAI"      # OpenAI API (payant)
    OLLAMA  = "OLLAMA"      # Ollama (local, gratuit)


class SearchEngine(str, enum.Enum):
    HYBRID        = "HYBRID"          # pgvector + BM25 (défaut)
    ELASTICSEARCH = "ELASTICSEARCH"   # ES fait tout


class SpaceStatus(str, enum.Enum):
    DRAFT   = "DRAFT"       # En construction par l'IT
    ACTIVE  = "ACTIVE"      # Déployé, visible par les End Users
    ERROR   = "ERROR"       # Problème


# ══════════════════════════════════════════════════════
# MODEL
# ══════════════════════════════════════════════════════

class RAGSpace(Base):
    __tablename__ = "rag_spaces"

    # ── Identité ──
    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name            = Column(String, nullable=False)
    description     = Column(String, default="")
    status          = Column(SAEnum(SpaceStatus), default=SpaceStatus.DRAFT)        # NEW
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    department_id   = Column(String, ForeignKey("departments.id"), nullable=True)

    # ── Chunking config ──
    chunk_size      = Column(Integer, default=512)
    chunk_overlap   = Column(Integer, default=50)
    chunk_strategy  = Column(SAEnum(ChunkStrategy), default=ChunkStrategy.FIXED)

    # ── Embedding config ──                                                        # NEW
    embedding_provider = Column(String, default="LOCAL")
    embedding_model    = Column(String, default="BAAI/bge-m3")

    # ── LLM config ──                                                              # NEW
    llm_provider    = Column(String, default="GROQ")
    llm_model       = Column(String, default="llama-3.3-70b-versatile")
    llm_temperature = Column(Float, default=0.2)
    llm_max_tokens  = Column(Integer, default=1024)

    # ── Search config ──                                                           # NEW
    top_k              = Column(Integer, default=5)
    search_engine      = Column(String, default="HYBRID")
    semantic_weight    = Column(Float, default=0.7)
    reranking_enabled  = Column(Boolean, default=False)

    # ── Prompt config ──                                                           # NEW
    system_prompt   = Column(Text, nullable=True)           # null = prompt par défaut

    # ── Timestamps ──
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relations ──
    organization = relationship("Organization")
    department   = relationship("Department")
    documents    = relationship("Document", back_populates="rag_space", cascade="all, delete-orphan")
