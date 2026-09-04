# Running AgentFlow with Docker

The fastest way to run the whole platform — no Python, Node, or PostgreSQL
needed on your machine, only **Docker Desktop**.

Three containers, started with one command:

| Container  | What it is                         | Open at                     |
|------------|------------------------------------|-----------------------------|
| `db`       | PostgreSQL 16 + pgvector           | (internal) host port `5433` |
| `backend`  | FastAPI API                        | http://localhost:8000 (Swagger at `/docs`) |
| `frontend` | React app (built, served by nginx) | http://localhost:5173       |

To understand what each part does (roles, architecture, endpoints, all env
variables), read [backend/README.md](backend/README.md) and
[frontend/README.md](frontend/README.md).

## 1. Prerequisites

- **Docker Desktop** installed and **running** (8 GB+ RAM recommended — the
  backend loads ML models for document parsing and embeddings).
- **`backend/.env`** exists — secrets and settings (SMTP account, `SECRET_KEY`,
  `FERNET_KEY`, vision API key…). Compose reads it automatically.
  The full variable reference is in [backend/README.md](backend/README.md).
- **`frontend/.env`** exists — `VITE_API_URL=http://localhost:8000/api`
  (+ optional Google Drive keys). These are baked in **at build time**, so
  changing them requires `docker compose up --build`.

## 2. Start

From the project root (where `docker-compose.yml` is):

```bash
docker compose up --build
```

- The **first** build is long (10–40 min) and large — the backend image pulls
  heavy ML/RAG libraries (Docling, crawl4ai/Chromium, HuggingFace…).
- On first startup the backend also downloads a few models; they are cached in
  a volume, so later starts are fast.
- When the backend logs settle, open **http://localhost:5173**.

**First login:** there is no seed account. Click **Sign up** — the first
registration creates the organization and its **admin**. The admin then invites
IT and end users by email from the Users page (this is why the `MAIL_*`
variables must be a working SMTP account).

## 3. Everyday use

```bash
docker compose up          # start (no rebuild)
docker compose up --build  # rebuild after you change the code
docker compose down        # stop (keeps the database)
docker compose down -v     # stop AND delete the database + model caches
docker compose logs -f backend   # follow the backend logs
```

## 4. How it fits together

- The database lives in a Docker volume (`pgdata`) and survives restarts; the
  schema is created automatically by the backend on boot (no migration step).
- Uploaded documents are stored in `backend/uploads/` **on your machine**
  (bind-mounted), so they survive rebuilds too.
- Downloaded ML models are cached in the `appcache` volume.
- `DATABASE_URL` is overridden by compose to point at the `db` container, so
  the `DATABASE_URL` line in `backend/.env` is ignored under Docker.
- The frontend is a static build served by nginx; it calls the backend at
  `VITE_API_URL` and authenticates via HttpOnly cookies, which is why it must
  be served on port **5173** (the only origin the backend's CORS allows).

## 5. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `port is already allocated` | Something local uses 5173, 8000, or 5433 — stop it or change the host port in `docker-compose.yml`. |
| Backend exits immediately | A required variable is missing in `backend/.env` — read the first error lines in `docker compose logs backend`. |
| Backend killed / `std::bad_alloc` while indexing | Not enough RAM for Docling. Give Docker more memory, or set `PDF_EXTRACTION_MODE=fast` in `backend/.env`. |
| Invitation / reset emails never arrive | `MAIL_*` values are wrong, or `FRONTEND_URL` doesn't match the URL users open (links in the emails are built from it). |
| Frontend loads but every request fails | `VITE_API_URL` was wrong at build time — fix `frontend/.env` and rebuild (`docker compose up --build frontend`). |
| First question to an agent is very slow | Normal: embedding/reranker models warm up in the background after boot. |
