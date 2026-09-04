# AgentFlow — Backend (FastAPI)

The API behind AgentFlow, a platform where a company builds **RAG-powered AI agents**
over its own documents:

- **Admins** manage the organization: users, departments, company LLM/embedding
  providers and their API keys.
- **IT** builds and tunes **RAG spaces** (document ingestion, chunking, embeddings,
  retrieval, evaluation, security testing) and deploys them as agents.
- **End users** chat with the deployed agents of their department; every answer
  cites its source documents.

> To run the whole stack with one command, see [../DOCKER.md](../DOCKER.md).
> This file is for understanding the backend and running it directly (dev mode).

---

## Tech stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + Uvicorn (Python 3.11+) |
| Database | PostgreSQL 15+ with the **pgvector** extension |
| ORM | SQLAlchemy 2.0 (schema auto-created at startup via `create_all`) |
| Auth | JWT (HS256) in HttpOnly cookies + bcrypt, email OTP for password reset |
| Email | fastapi-mail (SMTP) — invitations, password reset |
| Document parsing | Docling (ML layout/tables/images) or PyMuPDF (fast mode), OCR fallback via vision LLM |
| Chunking | Fixed / semantic / hierarchical / LLM / agentic strategies |
| Embeddings | Local sentence-transformers (BGE-M3, MiniLM, …) or provider APIs |
| LLMs | Multi-provider: Groq, OpenAI, Gemini, Ollama (local) — keys stored encrypted (Fernet) |
| Retrieval | pgvector similarity + BGE cross-encoder reranking |
| Web ingestion | crawl4ai / Playwright (Chromium), falls back to plain requests |
| Chat cache | Upstash Redis REST (optional) |
| Observability | Langfuse tracing (optional) |
| Security eval | Built-in attack corpus + campaigns (prompt-injection testing) |

---

## Running locally (without Docker)

### 1. Prerequisites

- Python **3.11+** (3.12 recommended — same as the Docker image)
- PostgreSQL **15+** with pgvector installed, and a database created:

```sql
CREATE DATABASE agentflow;
\c agentflow
CREATE EXTENSION IF NOT EXISTS vector;
```

- (Optional) [Ollama](https://ollama.com) if you want local LLMs with no API key.

### 2. Install

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows   (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
```

The install is **heavy** (Docling, HuggingFace, LangChain, LlamaIndex, crawl4ai…)
— expect several GB and a long first install.

### 3. Configure `.env`

Create `backend/.env`. Variables (from [app/config.py](app/config.py)):

| Variable | Required | What it does |
|---|---|---|
| `DATABASE_URL` | ✅ | e.g. `postgresql://postgres:postgres@localhost:5432/agentflow` |
| `SECRET_KEY` | ✅ | JWT signing secret (any long random string) |
| `ALGORITHM` | ✅ | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | e.g. `1440` |
| `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_FROM` / `MAIL_SERVER` / `MAIL_PORT` | ✅ | SMTP account used to send invitations and OTP emails |
| `FRONTEND_URL` | ✅ | Public URL of the frontend (`http://localhost:5173` in dev). Used to build activation/reset links in emails — a wrong value means dead links. |
| `FERNET_KEY` | ✅ | Encrypts provider API keys stored in the DB. Generate once: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `VISION_PROVIDER` / `VISION_MODEL` / `VISION_API_KEY` | ✅ | Vision LLM that describes images found in documents (`openai` \| `gemini` \| `ollama`) |
| `GROQ_API_KEY` | optional | Fallback Groq key (normally keys come from admin-managed providers) |
| `OPENAI_API_KEY` / `CHUNK_LLM_MODEL` | optional | Key/model for LLM & agentic chunking (degrades to structural chunking if absent) |
| `OLLAMA_BASE_URL` | optional | Local Ollama server (default `http://localhost:11434`) |
| `PDF_EXTRACTION_MODE` | optional | `accurate` (Docling, slow on CPU) or `fast` (PyMuPDF, ~40× faster, no ML tables/images) |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | optional | Chat answer cache — empty = disabled |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | optional | RAG observability tracing — empty = disabled |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` / `TOP_K` | optional | RAG defaults (512 / 50 / 5) |
| `DOCLING_*`, `PDF_OCR_*`, `CLEAN_*`, `WEB_IMAGE_VISION_MAX`, `VISION_MAX_WORKERS` | optional | Parsing/cleaning performance tuning — the defaults in `config.py` are documented inline and safe |

### 4. Run

```bash
uvicorn app.main:app --reload
```

- API: http://localhost:8000 — Swagger: http://localhost:8000/docs — ReDoc: `/redoc`
- **First startup is slow**: tables are created, the security attack corpus is
  seeded, and the ML models (Docling, embeddings, reranker) are downloaded and
  warmed up in a background thread. Later startups are fast — models are cached
  and `HF_HUB_OFFLINE=1` keeps the app from calling HuggingFace at runtime.
- **Do not add `--workers`**: evaluation/security runs keep in-memory job state,
  the app must stay a single process.

There is no seed user — open the frontend and **Sign up**: the first registration
creates the organization and its admin account. Everyone else is invited by email
from the admin's Users page.

---

## Project layout

```
backend/app/
├── main.py            # App entry: CORS, routers, startup warmups, create_all
├── config.py          # All settings, read from .env (pydantic-settings)
├── database.py        # Engine + SessionLocal
├── models/            # SQLAlchemy tables
│   ├── organization / department / user / user_department
│   ├── rag_space / rag_space_access / rag_space_collaborator / rag_space_version
│   ├── document / chunk / chunk_vector    # chunk_vectors_<dim> per embedding size
│   ├── chat            # ChatSession + ChatMessage (end-user conversations)
│   ├── api_provider    # Company LLM/embedding providers (encrypted keys)
│   ├── api_key         # Agent API keys + request logs (external access)
│   ├── evaluation      # Eval datasets + experiment runs
│   └── security        # Attack corpus + security campaigns/results
├── schemas/           # Pydantic request/response models
├── routes/            # HTTP endpoints (see table below)
└── services/          # Business logic
    ├── rag_service.py         # Ingestion pipeline orchestration
    ├── providers/             # Document loaders/parsers per format
    ├── embedding_factory/     # Local + API embeddings
    ├── llm_factory/           # Multi-provider LLM clients
    ├── retrieval/             # Vector search + reranking + query transform
    ├── chat/                  # Chat sessions, answering, caching
    ├── evaluation/ security/  # Quality & security testing of agents
    ├── pgvector_store.py      # Vector storage
    └── observability.py       # Langfuse tracing
```

## API surface

All routes are under `/api` except the public agent API.

| Prefix | File | What it serves |
|---|---|---|
| `/api/auth` | `routes/auth.py` | Register, login/logout (HttpOnly cookie), me, forgot/reset password (OTP) |
| `/api/users` | `routes/users.py` | Users CRUD, invitations, roles, departments |
| `/api/rag` | `routes/rag.py` | RAG spaces: config, documents, ingestion, query, versions, evaluation, security |
| `/api/chat` | `routes/chat.py` | End-user chat sessions + messages with deployed agents |
| `/api/dashboard` | `routes/dashboard.py` | Read-only aggregates for the role dashboards |
| `/api/providers` | `routes/api_provider.py` | Admin-managed company LLM/embedding providers |
| `/api/models` | `routes/models.py` | Model catalog per provider |
| `/api/rag/spaces/{id}/api-keys` | `routes/agent_api.py` | Manage agent API keys (owner/admin) |
| `/v1/...` | `routes/agent_api.py` | **Public agent API** — API-key auth, lets external apps query a deployed agent |

Full request/response detail: run the server and open **http://localhost:8000/docs**.

## Database schema & migrations

The schema is created automatically at startup from the SQLAlchemy models
(`Base.metadata.create_all`) — new tables and indexes appear on boot, so a fresh
database needs **no migration step**. The [migrations/](migrations/) folder only
holds one-off SQL patches for columns added to already-populated databases.

Uploaded documents are stored on disk in `backend/uploads/<space_id>/`.
