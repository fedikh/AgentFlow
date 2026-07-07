"""
Key resolver — decides WHICH provider + model + key to use for a space.

BUG FIX: the previous version could send a model from one provider (e.g.
gpt-4o-mini) to a different provider (e.g. GROQ), causing a 404. Now:

  - When a COMPANY provider is chosen, we use the PROVIDER'S family AND
    validate the model against that family's catalog. If the stored model
    doesn't belong to the provider's family, we fall back to that family's
    first recommended model (never send a foreign model).

  - When the space uses its OWN key, family = space.llm_provider, and we
    likewise keep model consistent.

  - Local source = OLLAMA (Batch 8). Models are listed live from the local
    Ollama daemon, so we trust the stored model as-is (no static catalog).

Resolution order: own key → company provider → local (Ollama).
Option C: missing/keyless company provider → explicit HTTP 400 (no silent
fallback to local).
"""
import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.services.providers_crypto import decrypt_key
from app.services.provider_models import models_for_family

logger = logging.getLogger(__name__)


def _valid_model_for_family(family: str, model: str) -> str:
    """
    Return a model guaranteed to belong to `family`.
    If `model` is in the family's catalog, keep it. Otherwise use the
    family's first recommended model. This prevents cross-provider mismatch.
    """
    catalog = models_for_family(family)
    ids = [m["id"] for m in catalog]
    if model and model in ids:
        return model
    if ids:
        logger.warning(
            f"[RESOLVER] model '{model}' not valid for {family}; "
            f"using '{ids[0]}' instead"
        )
        return ids[0]
    # unknown family with no catalog: keep whatever was given
    return model or ""


def resolve_llm_config(db: Session, space) -> dict:
    temperature = getattr(space, "llm_temperature", 0.2)
    if temperature is None:
        temperature = 0.2
    max_tokens = getattr(space, "llm_max_tokens", 1024) or 1024
    model = getattr(space, "llm_model", "") or ""
    family = (getattr(space, "llm_provider", "GROQ") or "GROQ").upper()

    # ── 1. Space's own key ──
    own_key_enc = getattr(space, "llm_api_key_enc", None)
    if own_key_enc:
        try:
            key = decrypt_key(own_key_enc)
        except Exception as e:
            logger.warning(f"[RESOLVER] Failed to decrypt space key: {e}")
            raise HTTPException(
                400,
                "This space's own API key could not be read. Re-enter it in the LLM config."
            )
        if key:
            fam = family
            safe_model = _valid_model_for_family(fam, model)
            logger.info(f"[RESOLVER] own key · {fam} · {safe_model}")
            return {
                "family": fam,
                "model": safe_model,
                "api_key": key,
                "base_url": getattr(space, "llm_base_url", "") or "",
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

    # ── 2. Company provider ──
    provider_id = getattr(space, "llm_provider_id", None)
    if provider_id:
        from app.models.api_provider import ApiProvider
        p = db.query(ApiProvider).filter(ApiProvider.id == provider_id).first()

        if not p:
            raise HTTPException(
                400,
                "The LLM provider configured for this space no longer exists. "
                "Please reconfigure the LLM in the space settings."
            )

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

        fam = (p.family.value if hasattr(p.family, "value") else str(p.family)).upper()
        # CRITICAL: the model must belong to the PROVIDER's family, not the
        # space's old llm_provider. This is the bug fix.
        safe_model = _valid_model_for_family(fam, model)
        logger.info(f"[RESOLVER] company '{p.name}' · {fam} · {safe_model}")
        return {
            "family": fam,
            "model": safe_model,
            "api_key": key,
            "base_url": p.base_url or "",
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    # ── 3. Local source = Ollama (live-listed models, no key) ──
    # Ollama models are listed live from the daemon, so trust the stored model
    # as-is rather than forcing it against a static catalog (which would rewrite
    # e.g. "llama3.1:8b" to a model that isn't actually installed).
    from app.config import settings
    safe_model = model or "llama3.1:8b"
    base_url = getattr(space, "llm_base_url", "") or settings.OLLAMA_BASE_URL or ""
    logger.info(f"[RESOLVER] local ollama · {safe_model}")
    return {
        "family": "OLLAMA",
        "model": safe_model,
        "api_key": "",
        "base_url": base_url,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }