"""
RAG schemas — FULLY CONFIGURABLE.

JOUR 1: Ajout de tous les champs configurables dans les requêtes Create et Update.

L'IT choisit chaque paramètre du pipeline au moment de la création.
Tous les champs ont des valeurs par défaut — l'IT peut créer un espace
en ne remplissant que le nom et le département, le reste est auto.
"""
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


# ══════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════

class ChunkStrategy(str, Enum):
    FIXED        = "FIXED"
    SEMANTIC     = "SEMANTIC"
    HIERARCHICAL = "HIERARCHICAL"

class ChunkMode(str, Enum):
    FIXED_ALL    = "FIXED_ALL"
    PER_DOCUMENT = "PER_DOCUMENT"
    ADAPTIVE     = "ADAPTIVE"


class EmbeddingProvider(str, Enum):
    LOCAL   = "LOCAL"
    OPENAI  = "OPENAI"
    COHERE  = "COHERE"


class LLMProvider(str, Enum):
    GROQ    = "GROQ"
    OPENAI  = "OPENAI"
    OLLAMA  = "OLLAMA"


class SearchEngine(str, Enum):
    HYBRID        = "HYBRID"
    ELASTICSEARCH = "ELASTICSEARCH"


# ══════════════════════════════════════════════════════
# CREATE RAG SPACE
# ══════════════════════════════════════════════════════

class CreateRAGSpaceRequest(BaseModel):
    # ── Identité (requis) ──
    name:           str
    description:    str = ""
    department_id:  str                                             # requis

    # ── Chunking ──
    # Free strings validated against the per-format catalog (chunking_factory).
    # chunk_mode: "SINGLE" | "PER_DOCUMENT". chunk_params: strategy parameters.
    chunk_mode:     str = "SINGLE"
    chunk_size:     int = Field(default=512, ge=100, le=6000)
    chunk_overlap:  int = Field(default=50, ge=0, le=1000)
    chunk_strategy: str = "recursive"
    chunk_params:   Optional[dict] = None
    chunk_format_map: Optional[dict] = None   # SINGLE: {file_type: {strategy, params}}


    # ── Embedding ──
    embedding_provider: EmbeddingProvider = EmbeddingProvider.LOCAL
    embedding_model:    str = "BAAI/bge-m3"                         # modèle par défaut

    # ── LLM ──
    llm_provider:    LLMProvider = LLMProvider.GROQ
    llm_model:       str = "llama-3.3-70b-versatile"
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)    # min 0, max 2
    llm_max_tokens:  int = Field(default=1024, ge=100, le=8000)     # min 100, max 8000

    # ── Recherche ──
    top_k:              int = Field(default=5, ge=1, le=20)         # min 1, max 20
    search_engine:      SearchEngine = SearchEngine.HYBRID
    semantic_weight:    float = Field(default=0.7, ge=0.0, le=1.0)  # 0 = keyword only, 1 = semantic only
    reranking_enabled:  bool = False

    # ── Prompt ──
    system_prompt:  Optional[str] = None                            # null = prompt par défaut

    # ── Access control (Batch 1) ──
    # None or empty  → all users of the department can query the space (default)
    # non-empty list → only these users can query it
    allowed_user_ids: Optional[list[str]] = None

    # ── End-user visibility at creation ──
    # True (default) → private: no end user sees it (just the owner + IT team).
    # False          → intended for the department (still hidden until deployed).
    is_private: Optional[bool] = None


# ══════════════════════════════════════════════════════
# UPDATE RAG SPACE
# ══════════════════════════════════════════════════════

class UpdateRAGSpaceRequest(BaseModel):
    """Tous les champs sont optionnels — l'IT ne modifie que ce qu'il veut."""
    name:               Optional[str] = None
    description:        Optional[str] = None
    department_id:      Optional[str] = None

    chunk_mode:         Optional[str] = None
    chunk_size:         Optional[int] = None
    chunk_overlap:      Optional[int] = None
    chunk_strategy:     Optional[str] = None
    chunk_params:       Optional[dict] = None
    chunk_format_map:   Optional[dict] = None

    embedding_provider: Optional[str] = None
    embedding_model:    Optional[str] = None

    # ── Embedding source (Batch 6) ──
    embedding_provider_id: Optional[str] = None   # company provider (api_providers.id)
    embedding_api_key:     Optional[str] = None   # IT's own key, plaintext in — encrypted at rest
    embedding_base_url:    Optional[str] = None

    llm_provider:       Optional[str] = None
    llm_model:          Optional[str] = None
    llm_temperature:    Optional[float] = None
    llm_max_tokens:     Optional[int] = None

    # ── LLM source (NEW) ──
    llm_provider_id:    Optional[str] = None   # company provider (api_providers.id)
    llm_api_key:        Optional[str] = None   # IT's own key, PLAINTEXT in — encrypted at rest
    llm_base_url:       Optional[str] = None

    top_k:              Optional[int] = None
    search_engine:      Optional[str] = None
    semantic_weight:    Optional[float] = None
    reranking_enabled:  Optional[bool] = None

    system_prompt:      Optional[str] = None

    # ── Access control (Batch 1) ──
    # Sync semantics on update:
    #   None        → leave the current access list untouched
    #   []          → clear all restrictions (every department user can query)
    #   [ids...]    → restrict to exactly these users
    allowed_user_ids:   Optional[list[str]] = None


# ══════════════════════════════════════════════════════
# VERSIONING + DEPLOY + COLLABORATORS
# ══════════════════════════════════════════════════════

class SaveVersionRequest(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = None


class DeployVersionRequest(BaseModel):
    # publish=True flips the space to visible for end users (is_private=False)
    publish: bool = False


class DeployCurrentRequest(BaseModel):
    label:   Optional[str] = None
    notes:   Optional[str] = None
    publish: bool = False


class SetPublishRequest(BaseModel):
    is_private: bool


# ══════════════════════════════════════════════════════
# QUERY
# ══════════════════════════════════════════════════════

class QueryRequest(BaseModel):
    question: str


# ══════════════════════════════════════════════════════
# DEPARTMENT USERS (for the "who can use this space" picker)
# ══════════════════════════════════════════════════════

class DepartmentUser(BaseModel):
    id:     str
    name:   Optional[str] = None
    email:  str
    role:   str
    status: str


class SourceChunk(BaseModel):
    content:   str
    document:  str
    page:      int = 0
    score:     float = 0.0


class QueryResponse(BaseModel):
    answer:  str
    sources: list[SourceChunk]

# ══════════════════════════════════════════════════════
# EDIT EXTRACTED CONTENT (ParsedDocument)
# ══════════════════════════════════════════════════════

class SectionEdit(BaseModel):
    heading:   str = ""
    content:   str = ""
    level:     int = 1
    page:      int = 1
    font_size: Optional[float] = None


class TableEdit(BaseModel):
    content:  str = ""
    headers:  list[str] = Field(default_factory=list)
    rows:     list[list] = Field(default_factory=list)
    num_rows: int = 0
    num_cols: int = 0
    page:     int = 1


class ImageEdit(BaseModel):
    caption:    str = ""
    ocr_text:   str = ""
    image_path: str = ""
    page:       int = 1
    bbox:       list[float] = Field(default_factory=list)
    # The description used for retrieval — must round-trip so edited/added
    # images stay indexable (to_content_blocks only emits images that have it).
    text_for_embedding: str = ""


class UpdateExtractedRequest(BaseModel):
    """IT-edited ParsedDocument. Only the editable arrays + title/metadata."""
    title:    Optional[str] = None
    sections: list[SectionEdit] = Field(default_factory=list)
    tables:   list[TableEdit] = Field(default_factory=list)
    images:   list[ImageEdit] = Field(default_factory=list)
    metadata: Optional[dict] = None