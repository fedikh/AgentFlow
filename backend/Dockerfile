# ── AgentFlow backend (FastAPI + heavy RAG/ML deps) ──
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System libraries the document / vision / web dependencies need at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
      poppler-utils \
      tesseract-ocr \
      libgl1 \
      libglib2.0-0 \
      curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cached layer — only re-runs when requirements change)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Chromium + its OS deps for the web crawler (crawl4ai / Playwright).
# Non-fatal: without it, web crawling falls back to plain requests.
RUN python -m playwright install --with-deps chromium || true

# Application code
COPY . .

EXPOSE 8000

# One worker: the app keeps in-memory job state (evaluation / security runs),
# so it must run as a single process — do NOT add --workers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
