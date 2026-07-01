"""
Key resolver — decides WHICH provider + key to use for a given RAG space.

Resolution order (first match wins):
  1. The space's OWN key   (IT typed its own key on the space)
  2. The company provider  (admin's ApiProvider row the space points to)
  3. Local free model      (GROQ default — only if IT explicitly chose local)

OPTION C (strict): if the space points to a company provider that no longer
exists, OR whose key is empty, we RAISE an explicit error instead of silently
falling back. This makes a broken config visible so the IT reconfigures it,
rather than getting answers from an unexpected model.

The local GROQ fallback applies ONLY when the space explicitly uses local
(llm_provider in GROQ/OLLAMA and no company provider / own key set).
"""
import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.services.providers_crypto import decrypt_key

logger = logging.getLogger(__name__)


def resolve_llm_config(db: Session, space) -> dict:
    """
    Return {family, model, api_key, base_url, temperature, max_tokens}
    ready to pass to factory.get_llm(**config).

    Raises HTTPException(400) if the configured company provider is missing
    or has no key (Option C — explicit error, no silent fallback).
    """
    temperature = getattr(space, "llm_temperature", 0.2)
    if temperature is None:
        temperature = 0.2
    max_tokens = getattr(space, "llm_max_tokens", 1024) or 1024
    model = getattr(space, "llm_model", "") or ""
    family = (getattr(space, "llm_provider", "GROQ") or "GROQ").upper()

    # ── 1. Space's own key (IT supplied its own) ──
    own_key_enc = getattr(space, "llm_api_key_enc", None)
    if own_key_enc:
        try:
            key = decrypt_key(own_key_enc)
        except Exception as e:
            logger.warning(f"[RESOLVER] Failed to decrypt space key: {e}")
            raise HTTPException(
                400,
                "This space's own API key could not be read. Re-enter the key in the LLM config."
            )
        if key:
            logger.info("[RESOLVER] Using space's own key")
            return {
                "family": family,
                "model": model,
                "api_key": key,
                "base_url": getattr(space, "llm_base_url", "") or "",
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

    # ── 2. Company provider (points to an ApiProvider row) ──
    provider_id = getattr(space, "llm_provider_id", None)
    if provider_id:
        from app.models.api_provider import ApiProvider
        p = db.query(ApiProvider).filter(ApiProvider.id == provider_id).first()

        # OPTION C — provider was deleted
        if not p:
            raise HTTPException(
                400,
                "The LLM provider configured for this space no longer exists. "
                "Please reconfigure the LLM in the space settings."
            )

        # OPTION C — provider exists but has no key
        key = ""
        if p.api_key_encrypted:
            try:
                key = decrypt_key(p.api_key_encrypted)
            except Exception:
                key = ""
        if not key:
            raise HTTPException(
                400,
                f"The provider '{p.name}' has no valid API key. "
                "Ask your admin to set its key, or choose another provider."
            )

        fam = p.family.value if hasattr(p.family, "value") else str(p.family)
        logger.info(f"[RESOLVER] Using company provider '{p.name}' ({fam})")
        return {
            "family": fam.upper(),
            "model": model,   # the model the IT picked for this space
            "api_key": key,
            "base_url": p.base_url or "",
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    # ── 3. Local free fallback (only when explicitly local) ──
    from app.config import settings
    logger.info("[RESOLVER] Using local/free default (GROQ)")
    return {
        "family": family if family in ("GROQ", "OLLAMA", "LOCAL") else "GROQ",
        "model": model or "llama-3.3-70b-versatile",
        "api_key": settings.GROQ_API_KEY,
        "base_url": "",
        "temperature": temperature,
        "max_tokens": max_tokens,
    }