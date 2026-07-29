from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, test_connection
from app.routes import auth, users
from app.routes.rag import router as rag_router
from app.routes.data_agent import router as data_agent_router
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

# Vector buckets — one chunk_vectors_<dim> model per catalog dimension,
# created by create_all like every other table (see models/chunk_vector.py)
from app.models import chunk_vector  # noqa: F401

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

app.include_router(data_agent_router, prefix="/api")
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


@app.on_event("startup")
async def startup():
    test_connection()
    import threading
    threading.Thread(target=_warmup_docling, daemon=True).start()


@app.get("/")
def root():
    return {"message": "AgentFlow API is running"}