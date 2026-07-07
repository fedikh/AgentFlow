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

    # Groq (LLM provider — key comes from an admin/own-key provider now)
    GROQ_API_KEY: str = ""

    # Ollama (Batch 8: the "Local" LLM source — local models, no key)
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Encryption key for stored API keys (Fernet). Generate once with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    FERNET_KEY: str = ""
    VISION_API_KEY: str = ""

    # RAG defaults
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    TOP_K: int = 5

    class Config:
        env_file = ".env"


settings = Settings()