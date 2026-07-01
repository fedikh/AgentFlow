"""
ApiProvider service — admin-only CRUD.

CHANGES:
  - Providers limited to: OPENAI, ANTHROPIC, GOOGLE, GROQ (+ OLLAMA/CUSTOM for local).
  - No Voyage.
  - Models are fetched LIVE from the provider's API (provider_models_live.py),
    not stored or hardcoded. The admin only gives name + family + key.
  - get_provider_models() calls the provider's /models endpoint in real time.
  - Deleting a provider used by spaces is blocked (Option C safety).
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.api_provider import ApiProvider, ProviderKind, ProviderFamily
from app.models.user import User, RoleType
from app.services.providers_crypto import encrypt_key, decrypt_key, mask_key
from app.services.provider_models_live import fetch_models


def _provider_dict(p: ApiProvider) -> dict:
    """Serialize for the client. NEVER includes the real key — only a mask."""
    masked = ""
    has_key = bool(p.api_key_encrypted)
    if has_key:
        try:
            masked = mask_key(decrypt_key(p.api_key_encrypted))
        except Exception:
            masked = "•••"
    fam = p.family.value if hasattr(p.family, "value") else str(p.family)
    return {
        "id": p.id,
        "organization_id": p.organization_id,
        "name": p.name,
        "kind": p.kind.value if hasattr(p.kind, "value") else str(p.kind),
        "family": fam,
        "base_url": p.base_url,
        "api_key_masked": masked,
        "has_key": has_key,
        "created_at": str(p.created_at),
    }


def _require_admin(user: User):
    if user.role != RoleType.ADMIN:
        raise HTTPException(403, "Only Admin can manage API providers")


def _validate_enums(kind: str, family: str):
    valid_kind = {k.value for k in ProviderKind}
    valid_family = {f.value for f in ProviderFamily}
    if kind not in valid_kind:
        raise HTTPException(400, f"Invalid kind. Use one of: {', '.join(valid_kind)}")
    if family not in valid_family:
        raise HTTPException(400, f"Invalid family. Use one of: {', '.join(valid_family)}")


# ── CRUD ──

def list_providers(db: Session, org_id: str) -> list[dict]:
    rows = db.query(ApiProvider).filter(ApiProvider.organization_id == org_id).all()
    return [_provider_dict(p) for p in rows]


def create_provider(db: Session, org_id: str, data, admin_user: User) -> dict:
    _require_admin(admin_user)
    _validate_enums(data.kind, data.family)

    if not data.name or not data.name.strip():
        raise HTTPException(400, "Provider name is required")

    p = ApiProvider(
        organization_id=org_id,
        name=data.name.strip(),
        kind=ProviderKind(data.kind),
        family=ProviderFamily(data.family),
        base_url=(data.base_url or None),
        api_key_encrypted=encrypt_key(data.api_key) if data.api_key else None,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _provider_dict(p)


def update_provider(db: Session, org_id: str, provider_id: str, data, admin_user: User) -> dict:
    _require_admin(admin_user)

    p = db.query(ApiProvider).filter(
        ApiProvider.id == provider_id,
        ApiProvider.organization_id == org_id,
    ).first()
    if not p:
        raise HTTPException(404, "Provider not found")

    if data.name is not None:
        p.name = data.name.strip()
    if data.kind is not None:
        _validate_enums(data.kind, p.family.value if hasattr(p.family, "value") else str(p.family))
        p.kind = ProviderKind(data.kind)
    if data.family is not None:
        _validate_enums(p.kind.value if hasattr(p.kind, "value") else str(p.kind), data.family)
        p.family = ProviderFamily(data.family)
    if data.base_url is not None:
        p.base_url = data.base_url or None
    if data.api_key:
        p.api_key_encrypted = encrypt_key(data.api_key)

    db.commit()
    db.refresh(p)
    return _provider_dict(p)


def delete_provider(db: Session, org_id: str, provider_id: str, admin_user: User) -> dict:
    _require_admin(admin_user)
    p = db.query(ApiProvider).filter(
        ApiProvider.id == provider_id,
        ApiProvider.organization_id == org_id,
    ).first()
    if not p:
        raise HTTPException(404, "Provider not found")

    from app.models.rag_space import RAGSpace
    in_use = db.query(RAGSpace).filter(RAGSpace.llm_provider_id == provider_id).count()
    if in_use > 0:
        raise HTTPException(
            400,
            f"Cannot delete '{p.name}': {in_use} RAG space(s) still use it. "
            "Change their LLM provider first, then delete."
        )

    name = p.name
    db.delete(p)
    db.commit()
    return {"message": f"Provider '{name}' deleted"}


def get_provider_models(db: Session, org_id: str, provider_id: str) -> dict:
    """
    LIVE: call the provider's API to list its models right now.
    Returns every model the API reports (no filtering).
    """
    p = db.query(ApiProvider).filter(
        ApiProvider.id == provider_id,
        ApiProvider.organization_id == org_id,
    ).first()
    if not p:
        raise HTTPException(404, "Provider not found")

    fam = p.family.value if hasattr(p.family, "value") else str(p.family)
    key = decrypt_key(p.api_key_encrypted) if p.api_key_encrypted else ""
    models = fetch_models(fam, key, p.base_url or "")
    return {"provider_id": p.id, "family": fam, "models": models}