"""
Schemas for ApiProvider.

KEY SECURITY RULE: the API key is WRITE-ONLY from the client's perspective.
- On create/update, the client sends `api_key` (plaintext, over HTTPS).
- On read, the server returns ONLY `api_key_masked` (e.g. "sk-•••4f2").
  The real key never leaves the server.
"""
from typing import Optional, List
from pydantic import BaseModel


class CreateProviderRequest(BaseModel):
    name: str
    kind: str            # "LLM" | "EMBEDDING"
    family: str          # "OPENAI" | "ANTHROPIC" | "GOOGLE" | "GROQ" | "VOYAGE" | "LOCAL" | "CUSTOM"
    base_url: Optional[str] = None
    api_key: Optional[str] = None        # plaintext on the way in, encrypted at rest
    models: Optional[str] = None         # "gpt-4o-mini,gpt-4o"


class UpdateProviderRequest(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    family: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None        # if provided, replaces the stored key
    models: Optional[str] = None


class ProviderResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    kind: str
    family: str
    base_url: Optional[str] = None
    api_key_masked: str                  # ONLY the masked preview, never the real key
    has_key: bool
    models: List[str]
    created_at: str