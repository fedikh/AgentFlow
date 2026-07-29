"""
Embedding key resolver — decides WHICH provider + model + key to use for a
space's embeddings. Mirror of the LLM resolver.

Resolution order: space's own key → company provider (EMBEDDING) → local BGE-M3.

Unlike the LLM resolver (strict Option C), embeddings fall back to the free
local model rather than raising, because breaking indexing/search on a bad key
would be worse than silently using the free baseline. Problems are logged.
"""
import logging
from sqlalchemy.orm import Session

from app.services.providers_crypto import decrypt_key

logger = logging.getLogger(__name__)

LOCAL_DEFAULT = {
    "family": "LOCAL",
    "model": "BAAI/bge-m3",
    "api_key": "",
    "base_url": "",
}


def resolve_embedding_config(db: Session, space) -> dict:
    model = getattr(space, "embedding_model", "") or "BAAI/bge-m3"
    family = (getattr(space, "embedding_provider", "LOCAL") or "LOCAL").upper()

    # ── Ollama: local daemon, no key — route straight to the Ollama embedder ──
    if family == "OLLAMA":
        import os
        base = getattr(space, "embedding_base_url", "") or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        logger.info(f"[EMB-RESOLVER] Ollama · {model} · {base}")
        return {"family": "OLLAMA", "model": model or "nomic-embed-text", "api_key": "", "base_url": base}

    # ── 1. Space's own key ──
    own_key_enc = getattr(space, "embedding_api_key_enc", None)
    if own_key_enc:
        try:
            key = decrypt_key(own_key_enc)
        except Exception as e:
            logger.warning(f"[EMB-RESOLVER] own key decrypt failed: {e}; using local")
            key = ""
        if key:
            fam = family if family in ("OPENAI", "VOYAGE", "GOOGLE") else "OPENAI"
            logger.info(f"[EMB-RESOLVER] own key · {fam} · {model}")
            return {
                "family": fam,
                "model": model,
                "api_key": key,
                "base_url": getattr(space, "embedding_base_url", "") or "",
            }

    # ── 2. Company provider (EMBEDDING kind) ──
    provider_id = getattr(space, "embedding_provider_id", None)
    if provider_id:
        from app.models.api_provider import ApiProvider
        p = db.query(ApiProvider).filter(ApiProvider.id == provider_id).first()
        if not p:
            logger.warning("[EMB-RESOLVER] company provider missing; using local")
            return dict(LOCAL_DEFAULT)
        key = ""
        if p.api_key_encrypted:
            try:
                key = decrypt_key(p.api_key_encrypted)
            except Exception:
                key = ""
        if not key:
            logger.warning(f"[EMB-RESOLVER] provider '{p.name}' has no key; using local")
            return dict(LOCAL_DEFAULT)
        fam = (p.family.value if hasattr(p.family, "value") else str(p.family)).upper()
        logger.info(f"[EMB-RESOLVER] company '{p.name}' · {fam} · {model}")
        return {
            "family": fam,
            "model": model,
            "api_key": key,
            "base_url": p.base_url or "",
        }

    # ── 3. Local free default (BGE-M3, 1024d) ──
    logger.info("[EMB-RESOLVER] local BGE-M3")
    return dict(LOCAL_DEFAULT)
