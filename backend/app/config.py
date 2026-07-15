from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Email
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    # Public URL of the frontend — used to build activation / reset links in
    # emails. Read from .env (FRONTEND_URL). MUST be a real reachable URL in
    # production (e.g. https://app.com), otherwise invites get a dead link.
    FRONTEND_URL: str

    # Groq (LLM provider — key comes from an admin/own-key provider now)
    GROQ_API_KEY: str = ""

    # Ollama (Batch 8: the "Local" LLM source — local models, no key)
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Encryption key for stored API keys (Fernet). Generate once with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    FERNET_KEY: str = ""

    # ── Vision (image description for multi-vector RAG) ──
    # Provider used to describe extracted images. "openai" | "gemini" | "ollama".
    VISION_PROVIDER: str = "openai"
    # Model for the chosen provider. Defaults resolve per-provider if left blank
    # (openai→gpt-4o-mini, gemini→gemini-2.5-flash, ollama→llava).
    VISION_MODEL: str = "gpt-4o-mini"
    # API key for openai/gemini (not needed for ollama — that uses OLLAMA_BASE_URL).
    VISION_API_KEY: str = ""

    # RAG defaults
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    TOP_K: int = 5

    # ── Extraction / parsing tuning (load + parse speed) ──
    # "accurate" → Docling (ML layout/tables/images, slow on CPU)
    # "fast"     → PyMuPDF text extraction (~40× faster, no ML tables/images)
    PDF_EXTRACTION_MODE: str = "accurate"
    # Docling image render scale. 2.0 caused std::bad_alloc (OOM) → skipped pages
    # on CPU; 1.0 is reliable and still fine for the vision LLM.
    DOCLING_IMAGES_SCALE: float = 1.0
    # Thread count for Docling's CPU inference. Keep at physical-core count —
    # oversubscribing (logical cores) slows it down.
    DOCLING_NUM_THREADS: int = 4
    DOCLING_TABLE_MODE: str = "fast"        # "fast" | "accurate"
    # Warm the Docling models at startup so the first parse isn't slow.
    DOCLING_WARMUP: bool = True
    # Parallel workers for Gemini image summarization (serial before → slow).
    VISION_MAX_WORKERS: int = 6

    # ── Cleaning pipeline toggles ──
    CLEAN_REMOVE_NOISE: bool = True         # page numbers, headers/footers, watermarks
    CLEAN_DEDUP: bool = True                # drop duplicate sections/paragraphs
    CLEAN_STRIP_HTML: bool = True           # strip stray HTML tags
    CLEAN_DETECT_PII: bool = True           # count PII → metadata (non-destructive)
    CLEAN_REDACT_PII: bool = False          # actually replace PII in text (destructive)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()