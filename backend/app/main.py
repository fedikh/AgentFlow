import os

# All ML models (embeddings, reranker, chunking, parsing) are downloaded and
# cached locally — never contact the Hugging Face Hub at runtime (no version
# checks, no downloads, no "unauthenticated requests" warning). To download a
# NEW model later, start once with the env var HF_HUB_OFFLINE=0.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, test_connection
from app.routes import auth, users
from app.routes.rag import router as rag_router
from app.routes import models as models_routes
from app.routes import api_provider

# Import the ApiProvider model so Base.metadata.create_all creates its table
from app.models.api_provider import ApiProvider  # noqa: F401

# Import RAGSpaceAccess so Base.metadata.create_all creates the rag_space_access table (Batch 1)
from app.models.rag_space_access import RAGSpaceAccess  # noqa: F401

# Versioning + IT-collaborator permissions — new tables created by create_all
from app.models.rag_space_version import RAGSpaceVersion  # noqa: F401
from app.models.rag_space_collaborator import RAGSpaceCollaborator  # noqa: F401

# Evaluation — datasets + experiment runs (tables created by create_all)
from app.models.evaluation import EvalCase, EvalRun  # noqa: F401

# Security evaluation — frozen attack corpus + campaigns + results
from app.models.security import (  # noqa: F401
    SecurityCase, SecurityRun, SecurityResult)

# Vector buckets — one chunk_vectors_<dim> model per catalog dimension,
# created by create_all like every other table (see models/chunk_vector.py)
from app.models import chunk_vector  # noqa: F401

# Chat layer — per-user sessions + messages with deployed agents
from app.models.chat import ChatSession, ChatMessage  # noqa: F401

# Agent API keys — machine access to deployed agents from other apps
from app.models.api_key import AgentApiKey, AgentApiLog  # noqa: F401

# Import rag — show error if it fails
try:
    from app.routes import rag
    has_rag = True
except Exception as e:
    has_rag = False
    print(f"⚠️  RAG module not loaded: {e}")

# Schema comes entirely from the SQLAlchemy models — create_all() creates
# every missing table + index, chunk_vectors_<dim> buckets included.
Base.metadata.create_all(bind=engine)

# Startup self-healing: remove upload folders of spaces that no longer exist
# (a delete may have failed earlier on a locked file — retried here).
try:
    from app.database import SessionLocal as _SL
    from app.services.rag_service import cleanup_orphan_upload_folders as _cof
    _db = _SL()
    _removed = _cof(_db)
    _db.close()
except Exception as _e:
    print(f"[CLEANUP] orphan sweep skipped: {_e}")

# Security evaluation: seed the frozen attack corpus once + warm the PII engine
try:
    from app.database import SessionLocal as _SL2
    from app.services.security.seed import seed_corpus as _seed_sec
    _db2 = _SL2()
    try:
        _r = _seed_sec(_db2)
        if _r.get("seeded"):
            print(f"[SECURITY] seeded {_r['seeded']} attack cases")
    finally:
        _db2.close()
except Exception as _e:
    print(f"[SECURITY] corpus seed skipped: {_e}")

app = FastAPI(
    title="AgentFlow API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(rag_router, prefix="/api")
if has_rag:
    app.include_router(rag.router, prefix="/api")
    print("✅ RAG module loaded")
else:
    print("❌ RAG module NOT loaded — check the error above")

# Chat sessions + history for deployed agents (Upstash Redis cache optional —
# set UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN in .env to enable)
from app.routes.chat import router as chat_router
app.include_router(chat_router, prefix="/api")

# Agent API: public /v1 (API-key auth, for external enterprise apps) +
# key management under /api/rag/spaces/{id}/api-keys (owner/admin)
from app.routes.agent_api import router as agent_api_router, mgmt_router as api_keys_router
app.include_router(agent_api_router)          # /v1/... — no /api prefix
app.include_router(api_keys_router, prefix="/api")

# Role dashboards (read-only aggregates)
from app.routes.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="/api")

app.include_router(models_routes.router)

# API Providers (admin manages company LLM/embedding providers + keys)
app.include_router(api_provider.router, prefix="/api")


def _warmup_docling():
    """
    Pre-load the Docling converter + ML models in a background thread so the
    FIRST document parse doesn't pay the one-time model-load latency.
    """
    try:
        from app.config import settings
        if str(getattr(settings, "PDF_EXTRACTION_MODE", "accurate")).lower() == "fast":
            return  # fast mode uses PyMuPDF, nothing to warm
        if not getattr(settings, "DOCLING_WARMUP", True):
            return
        from app.services.providers.loaders.documents.pdf_loader import _get_converter
        _get_converter()  # builds converter + loads layout/table models
        print("✅ Docling models warmed up")
    except Exception as e:
        print(f"⚠️  Docling warmup skipped: {e}")


def _warmup_embedder():
    """Warm the retrieval cold path in a background thread — otherwise the
    FIRST query after boot pays it and can even time out its branches:
      - local embedding models: load into memory (measured: ~12s)
      - API embeddings (company/own key): one tiny warmup call — imports the
        client library and opens the connection pool (measured: ~5s cold)
      - LLM client imports (query transform uses them): imported once here
    """
    try:
        from app.database import SessionLocal
        from app.models.rag_space import RAGSpace
        from app.services.embedding_factory import embed_query
        from app.services.llm_factory.factory import get_llm  # noqa: F401 — import cost only
        db = SessionLocal()
        seen = set()
        for s in db.query(RAGSpace).filter(RAGSpace.status == "ACTIVE").all():
            key = (str(getattr(s, "embedding_provider", "") or ""), s.embedding_model)
            if key in seen:
                continue
            seen.add(key)
            try:
                embed_query(db, s, "warmup")
                print(f"✅ Embedding warmed up ({s.embedding_model})")
            except Exception as e:
                print(f"⚠️  Embedding warmup failed for {s.embedding_model}: {e}")
        db.close()
    except Exception as e:
        print(f"⚠️  Embedding warmup skipped: {e}")


def _warmup_reranker():
    """Pre-load the always-on BGE cross-encoder in a background thread so the
    FIRST query doesn't pay the one-time model-load latency (~15s)."""
    try:
        import os
        os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
        from sentence_transformers import CrossEncoder
        from app.services.retrieval.rerank import _BGE_DEFAULT, _LOCAL_MODELS
        if _BGE_DEFAULT not in _LOCAL_MODELS:
            _LOCAL_MODELS[_BGE_DEFAULT] = CrossEncoder(_BGE_DEFAULT)
        print("✅ Reranker warmed up (BGE v2-m3)")
    except Exception as e:
        print(f"⚠️  Reranker warmup skipped: {e}")


def _warmup_all():
    """ONE background thread, warmups in sequence. Running them in parallel
    threads raced each other (and early requests) on importing the shared ML
    stack — Python then sees half-initialized modules ('cannot import name …
    from partially initialized module accelerate.big_modeling'). Importing
    the base stack first, once, makes every later import find it finished."""
    try:
        import torch, transformers, accelerate  # noqa: F401  fully init shared ML base
    except Exception as e:
        print(f"⚠️  ML base import warmup: {e}")
    _warmup_docling()
    _warmup_reranker()
    _warmup_embedder()


@app.on_event("startup")
async def startup():
    test_connection()
    import threading
    threading.Thread(target=_warmup_all, daemon=True).start()


@app.get("/")
def root():
    return {"message": "AgentFlow API is running"}