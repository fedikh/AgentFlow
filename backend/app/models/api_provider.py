"""
ApiProvider model — company-level LLM / embedding providers.

Families supported: OPENAI, ANTHROPIC, GOOGLE, GROQ (paid, live model listing)
plus OLLAMA / LOCAL / CUSTOM for self-hosted. Voyage removed.

The admin adds only: name + family + key. Models are fetched LIVE from the
provider's API when the IT opens the model picker.
"""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
from app.database import Base


class ProviderKind(str, enum.Enum):
    LLM       = "LLM"
    EMBEDDING = "EMBEDDING"


class ProviderFamily(str, enum.Enum):
    OPENAI    = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GOOGLE    = "GOOGLE"
    GROQ      = "GROQ"
    VOYAGE    = "VOYAGE"      # embedding-only provider
    OLLAMA    = "OLLAMA"
    LOCAL     = "LOCAL"
    CUSTOM    = "CUSTOM"


# Batch 7: which provider families are valid for each provider kind.
FAMILIES_BY_KIND = {
    "LLM":       {"OPENAI", "ANTHROPIC", "GOOGLE", "GROQ", "CUSTOM"},
    "EMBEDDING": {"OPENAI", "VOYAGE"},
}


class ApiProvider(Base):
    __tablename__ = "api_providers"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    name            = Column(String, nullable=False)
    kind            = Column(SAEnum(ProviderKind), nullable=False, default=ProviderKind.LLM)
    family          = Column(SAEnum(ProviderFamily), nullable=False, default=ProviderFamily.OPENAI)
    base_url        = Column(String, nullable=True)

    api_key_encrypted = Column(Text, nullable=True)

    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))