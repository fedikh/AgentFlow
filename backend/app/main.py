from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text as _sql_text

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

# Import rag — show error if it fails
try:
    from app.routes import rag
    has_rag = True
except Exception as e:
    has_rag = False
    print(f"⚠️  RAG module not loaded: {e}")

Base.metadata.create_all(bind=engine)


# ── Lightweight idempotent migrations ──
# create_all() creates missing TABLES but never ALTERs existing ones, so new
# columns on already-created tables must be added here. All statements use
# "IF NOT EXISTS", so this is safe to run on every startup.
def _run_light_migrations():
    stmts = [
        # Batch 5 — image chunks
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_type VARCHAR DEFAULT 'text'",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS image_path VARCHAR",
        # Batch 6 — embedding source on a space (mirrors the LLM source)
        "ALTER TABLE rag_spaces ADD COLUMN IF NOT EXISTS embedding_provider_id VARCHAR",
        "ALTER TABLE rag_spaces ADD COLUMN IF NOT EXISTS embedding_api_key_enc TEXT",
        "ALTER TABLE rag_spaces ADD COLUMN IF NOT EXISTS embedding_base_url VARCHAR",
        # Per-document image extraction toggle
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS extract_images BOOLEAN DEFAULT TRUE",
        # ── Manual per-format chunking ──
        # New per-strategy params + chunk traceability
        "ALTER TABLE rag_spaces ADD COLUMN IF NOT EXISTS chunk_params TEXT",
        "ALTER TABLE rag_spaces ADD COLUMN IF NOT EXISTS chunk_format_map TEXT",
        # ── Retrieval Engine: per-space pipeline overrides (visual pipeline UI) ──
        "ALTER TABLE rag_spaces ADD COLUMN IF NOT EXISTS retrieval_params TEXT",
        # ── Evaluation: independent judge settings ──
        "ALTER TABLE rag_spaces ADD COLUMN IF NOT EXISTS eval_params TEXT",
        "ALTER TABLE documents  ADD COLUMN IF NOT EXISTS chunk_params TEXT",
        "ALTER TABLE chunks     ADD COLUMN IF NOT EXISTS strategy VARCHAR",
        "ALTER TABLE chunks     ADD COLUMN IF NOT EXISTS parent_index INTEGER",
        # Widen the old enum columns → VARCHAR so the catalog can grow + use
        # SINGLE / PER_DOCUMENT. Safe no-ops if the columns are already VARCHAR.
        "ALTER TABLE rag_spaces ALTER COLUMN chunk_strategy DROP DEFAULT",
        "ALTER TABLE rag_spaces ALTER COLUMN chunk_strategy TYPE VARCHAR USING chunk_strategy::text",
        "ALTER TABLE rag_spaces ALTER COLUMN chunk_mode DROP DEFAULT",
        "ALTER TABLE rag_spaces ALTER COLUMN chunk_mode TYPE VARCHAR USING chunk_mode::text",
        # Normalise legacy values to the new catalog vocabulary
        "UPDATE rag_spaces SET chunk_strategy = lower(chunk_strategy) WHERE chunk_strategy IS NOT NULL",
        "UPDATE documents  SET chunk_strategy = lower(chunk_strategy) WHERE chunk_strategy IS NOT NULL",
        "UPDATE rag_spaces SET chunk_mode = 'SINGLE' WHERE chunk_mode IN ('FIXED_ALL', 'ADAPTIVE')",
        "ALTER TABLE rag_spaces ALTER COLUMN chunk_strategy SET DEFAULT 'recursive'",
        "ALTER TABLE rag_spaces ALTER COLUMN chunk_mode SET DEFAULT 'SINGLE'",
        # ── Versioning + ownership/permissions ──
        # owner_id stays NULL on existing rows (legacy → visible to all IT).
        "ALTER TABLE rag_spaces ADD COLUMN IF NOT EXISTS owner_id VARCHAR",
        "ALTER TABLE rag_spaces ADD COLUMN IF NOT EXISTS deployed_version_id VARCHAR",
        # IMPORTANT: DB default FALSE (not TRUE) so already-deployed spaces stay
        # visible to end users. New spaces are set private via the ORM.
        "ALTER TABLE rag_spaces ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT FALSE",
        "ALTER TABLE rag_spaces ADD COLUMN IF NOT EXISTS reindex_required BOOLEAN DEFAULT FALSE",
        # Convert status from the native enum to VARCHAR so new statuses (EDITING)
        # don't need an enum migration. Safe no-op if already VARCHAR.
        "ALTER TABLE rag_spaces ALTER COLUMN status DROP DEFAULT",
        "ALTER TABLE rag_spaces ALTER COLUMN status TYPE VARCHAR USING status::text",
        "ALTER TABLE rag_spaces ALTER COLUMN status SET DEFAULT 'DRAFT'",
    ]
    # Each statement in its own transaction so one failure (e.g. an enum
    # conversion on an unexpected state) can't abort the rest.
    applied = 0
    for s in stmts:
        try:
            with engine.begin() as conn:
                conn.execute(_sql_text(s))
            applied += 1
        except Exception as e:
            print(f"⚠️  migration step skipped: {s[:60]}… ({e})")
    print(f"✅ Light migrations applied ({applied}/{len(stmts)} steps)")


_run_light_migrations()

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