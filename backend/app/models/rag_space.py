"""
RAGSpace model — FULLY CONFIGURABLE.
Ajout de tous les champs configurables pour le pipeline RAG.

NOUVEAUX CHAMPS:
  Embedding: embedding_provider, embedding_model
  LLM:       llm_provider, llm_model, llm_temperature, llm_max_tokens
  LLM source: llm_provider_id (company provider), llm_api_key_enc (own key), llm_base_url
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

class ChunkMode(str, enum.Enum):
    FIXED_ALL    = "FIXED_ALL"
    PER_DOCUMENT = "PER_DOCUMENT"
    ADAPTIVE     = "ADAPTIVE"

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
    EDITING = "EDITING"     # Déployé mais mis en pause pour édition (end users voient "en mise à jour")
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
    # Plain string (not a native PG enum) so new statuses like EDITING can be
    # added without an enum migration. Values come from SpaceStatus.
    status          = Column(String, default="DRAFT")
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    department_id   = Column(String, ForeignKey("departments.id"), nullable=True)

    # ── Ownership & lifecycle (versioning + permissions) ──
    # owner_id: the IT who created the space. Private to the owner by default;
    #   other IT need a RAGSpaceCollaborator row to see/build it. Legacy rows
    #   (owner_id NULL) stay visible to every IT.
    owner_id            = Column(String, ForeignKey("users.id"), nullable=True)
    # is_private: end-user exposure master switch. True → no end user sees it,
    #   even if ACTIVE. Flipped to False when the IT "publishes" on deploy.
    #   NOTE: the DB default is FALSE (see main.py migration) so pre-existing
    #   spaces stay published; new spaces are set True explicitly in create_space.
    is_private          = Column(Boolean, default=True)
    # deployed_version_id: the RAGSpaceVersion currently live. Plain string (no
    #   DB FK) to avoid a circular create-order between the two tables.
    deployed_version_id = Column(String, nullable=True)
    # reindex_required: set when chunk_*/embedding_* change (config drift from
    #   the live index); cleared by process_document/process_all_documents.
    reindex_required    = Column(Boolean, default=False)

    # ── Chunking config ──
    # Plain strings (not enums) so the per-format strategy catalog can grow
    # without a DB migration. chunk_mode: "SINGLE" | "PER_DOCUMENT".
    # chunk_strategy: a catalog strategy name (e.g. "recursive", "row", "node").
    # chunk_params: JSON of the space-level strategy's tuned parameters.
    chunk_mode      = Column(String, default="SINGLE")
    chunk_size      = Column(Integer, default=512)
    chunk_overlap   = Column(Integer, default=50)
    chunk_strategy  = Column(String, default="recursive")
    chunk_params    = Column(Text, nullable=True)
    # SINGLE mode is per-FORMAT: {"pdf": {"strategy": "...", "params": {...}},
    # "pptx": {...}, "csv": {...}} — each format gets the strategy that fits it.
    chunk_format_map = Column(Text, nullable=True)

    # ── Embedding config ──                                                        # NEW
    embedding_provider = Column(String, default="LOCAL")
    embedding_model    = Column(String, default="BAAI/bge-m3")

    # ── Embedding source (Batch 6) — mirrors the LLM source ──
    # Option A: company provider (api_providers.id, EMBEDDING kind)
    embedding_provider_id = Column(String, ForeignKey("api_providers.id"), nullable=True)
    # Option B: IT's own key for this space (encrypted at rest)
    embedding_api_key_enc = Column(Text, nullable=True)
    embedding_base_url    = Column(String, nullable=True)

    # ── LLM config ──                                                              # NEW
    llm_provider    = Column(String, default="GROQ")
    llm_model       = Column(String, default="llama-3.3-70b-versatile")
    llm_temperature = Column(Float, default=0.2)
    llm_max_tokens  = Column(Integer, default=1024)

    # ── LLM source (NEW) ──
    # Option A: point to a company provider (api_providers table)
    llm_provider_id = Column(String, ForeignKey("api_providers.id"), nullable=True)
    # Option B: IT's own key for this space (encrypted at rest)
    llm_api_key_enc = Column(Text, nullable=True)
    llm_base_url    = Column(String, nullable=True)

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
    owner        = relationship("User", foreign_keys=[owner_id])
    documents    = relationship("Document", back_populates="rag_space", cascade="all, delete-orphan")
    # Config-snapshot versions of this space (deleting a space removes them).
    # FK rag_space_versions.rag_space_id → rag_spaces.id is unambiguous, so the
    # join is inferred; the target class is registered via main.py / rag_service.
    versions     = relationship("RAGSpaceVersion", cascade="all, delete-orphan")