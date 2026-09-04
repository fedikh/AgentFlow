# AgentFlow

AgentFlow lets a company turn its internal documents into **AI agents its
employees can chat with**. Every answer is grounded in the company's own
documents and cites its sources (RAG — retrieval-augmented generation).

**Three roles, one platform:**

- **Admin** — manages the organization: users, departments, and the company's
  LLM/embedding providers and API keys.
- **IT** — builds the agents: creates RAG spaces, uploads documents (PDF, DOCX,
  web pages…), tunes parsing/chunking/embeddings/retrieval, evaluates answer
  quality and security, then deploys the agent to a department.
- **End user** — opens a full-page chat, picks an agent from their department,
  asks questions, and gets cited answers with a click-through to the source
  document.

## Repository layout

| Folder | What it is | Docs |
|---|---|---|
| [backend/](backend/) | FastAPI API — auth, RAG pipeline, chat, evaluation | [backend/README.md](backend/README.md) |
| [frontend/](frontend/) | React SPA — the three role experiences | [frontend/README.md](frontend/README.md) |
| [docker-compose.yml](docker-compose.yml) | Full stack in 3 containers | [DOCKER.md](DOCKER.md) |

## Quick start

**Recommended — Docker (nothing to install but Docker Desktop):**

```bash
docker compose up --build
```

Then open http://localhost:5173 and **Sign up** (the first account becomes the
admin). Full guide, prerequisites, and troubleshooting: [DOCKER.md](DOCKER.md).

**Manual (dev mode):** run PostgreSQL+pgvector, then the backend
(`uvicorn app.main:app --reload`, port 8000) and the frontend (`npm run dev`,
port 5173) — step-by-step in the two READMEs above, including the `.env`
variable reference for each side.
