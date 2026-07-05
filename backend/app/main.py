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
    ]
    try:
        with engine.begin() as conn:
            for s in stmts:
                conn.execute(_sql_text(s))
        print("✅ Light migrations applied (chunks.chunk_type, chunks.image_path)")
    except Exception as e:
        print(f"⚠️  Light migrations skipped: {e}")


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


@app.on_event("startup")
async def startup():
    test_connection()


@app.get("/")
def root():
    return {"message": "AgentFlow API is running"}