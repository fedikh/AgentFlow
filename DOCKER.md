# Running AgentFlow with Docker

Three containers, started with one command:

| Container  | What it is                       | Open at                     |
|------------|----------------------------------|-----------------------------|
| `db`       | PostgreSQL 16 + pgvector         | (internal) host port `5433` |
| `backend`  | FastAPI API                      | http://localhost:8000       |
| `frontend` | React app (built, served by nginx) | http://localhost:5173     |

## 1. Prerequisites
- **Docker Desktop** installed and **running**.
- `backend/.env` exists (your secrets). Docker reads it automatically.
  You do **not** need Python, Node, or a local PostgreSQL installed.

## 2. Start
From the project root (where `docker-compose.yml` is):

```bash
docker compose up --build
```

- The **first** build is long (10–40 min) and large — the backend pulls heavy
  ML/RAG libraries (Docling, crawl4ai/Chromium, HuggingFace, DeepTeam…).
- On first startup the backend also downloads a few models; they are cached, so
  later starts are fast.
- When you see the backend logs settle, open **http://localhost:5173**.

## 3. Everyday use
```bash
docker compose up          # start (no rebuild)
docker compose up --build  # rebuild after you change the code
docker compose down        # stop (keeps the database)
docker compose down -v     # stop AND delete the database + caches
docker compose logs -f backend   # follow the backend logs
```

## 4. Notes
- The database lives in a Docker volume (`pgdata`) and survives restarts.
- Uploaded documents are stored in `backend/uploads/` on your machine.
- `DATABASE_URL` is overridden by compose to point at the `db` container, so the
  `DATABASE_URL` line in `backend/.env` is ignored when running via Docker.
- The frontend talks to the backend via `VITE_API_URL` in `frontend/.env`
  (`http://localhost:8000/api`) — correct for this setup out of the box.
