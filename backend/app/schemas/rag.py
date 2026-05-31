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
    chunk_size:     int = Field(default=512, ge=100, le=3000)       # min 100, max 3000
    chunk_overlap:  int = Field(default=50, ge=0, le=500)           # min 0, max 500
    chunk_strategy: ChunkStrategy = ChunkStrategy.FIXED

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


# ══════════════════════════════════════════════════════
# UPDATE RAG SPACE
# ══════════════════════════════════════════════════════

class UpdateRAGSpaceRequest(BaseModel):
    """Tous les champs sont optionnels — l'IT ne modifie que ce qu'il veut."""
    name:               Optional[str] = None
    description:        Optional[str] = None
    department_id:      Optional[str] = None

    chunk_size:         Optional[int] = None
    chunk_overlap:      Optional[int] = None
    chunk_strategy:     Optional[ChunkStrategy] = None

    embedding_provider: Optional[str] = None
    embedding_model:    Optional[str] = None

    llm_provider:       Optional[str] = None
    llm_model:          Optional[str] = None
    llm_temperature:    Optional[float] = None
    llm_max_tokens:     Optional[int] = None

    top_k:              Optional[int] = None
    search_engine:      Optional[str] = None
    semantic_weight:    Optional[float] = None
    reranking_enabled:  Optional[bool] = None

    system_prompt:      Optional[str] = None


# ══════════════════════════════════════════════════════
# QUERY
# ══════════════════════════════════════════════════════

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
