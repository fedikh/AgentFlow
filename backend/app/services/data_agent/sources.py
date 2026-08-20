"""
Data sources — the connection records, their CRUD, and the lifecycle.

    draft → connected → trained → deployed        (stale = re-train needed)

Security model (mirrors the RAG-space conventions):
  · secrets (DB password, own LLM/embedding keys) are Fernet-encrypted on
    write and NEVER returned — the UI receives a boolean + a masked preview
  · management is owner-or-admin; consumption goes through
    orchestrator.check_source_access
  · the connection manager owns engines, so any credential change disposes
    the pooled engine immediately

The UI must state, and this module assumes, that the credentials belong to
a READ-ONLY database user. Everything else is defense in depth.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.data_agent import DataSource, DataSourceAccess
from app.services.data_agent.database import (adapter_for, dispose,
                                              supported_dialects)
from app.services.providers_crypto import decrypt_key, encrypt_key

logger = logging.getLogger(__name__)

_EDITABLE = {
    # identity & access
    "name", "description", "department_id", "is_private",
    # connection
    "host", "port", "database", "username", "dialect",
    # execution safety
    "row_limit", "timeout_ms", "mode_override", "send_results_to_llm",
    # generation
    "llm_provider", "llm_model", "llm_provider_id", "llm_base_url",
    "llm_temperature", "llm_max_tokens", "prompt_mode", "system_prompt",
    # embedding
    "embedding_provider", "embedding_model", "embedding_provider_id",
    "embedding_base_url",
}
_JSON_FIELDS = {"extra_params", "schema_whitelist", "retrieval_params",
                "chunk_params"}
_SECRETS = {"password": "password_enc",
            "llm_api_key": "llm_api_key_enc",
            "embedding_api_key": "embedding_api_key_enc"}
# changing any of these invalidates the trained index
_REINDEX_TRIGGERS = {"embedding_provider", "embedding_model",
                     "embedding_provider_id"}


def _now():
    return datetime.now(timezone.utc)


def _role(user) -> str:
    r = str(getattr(user, "role", "") or "")
    return r.split(".")[-1] if "." in r else r


def _is_owner_or_admin(source: DataSource, user) -> bool:
    return _role(user) == "ADMIN" or getattr(source, "owner_id", None) == user.id


def find_source(db: Session, source_id: str, org_id: str) -> DataSource:
    s = (db.query(DataSource)
         .filter(DataSource.id == source_id,
                 DataSource.organization_id == org_id).first())
    if not s:
        raise HTTPException(404, "Data agent not found")
    return s


def require_manager(db: Session, source_id: str, org_id: str, user) -> DataSource:
    s = find_source(db, source_id, org_id)
    if not _is_owner_or_admin(s, user):
        raise HTTPException(403, "Only the owner can manage this data agent")
    return s


def _masked(enc) -> str | None:
    if not enc:
        return None
    try:
        k = decrypt_key(enc) or ""
        return f"{k[:3]}…{k[-3:]}" if len(k) > 8 else "•••"
    except Exception:
        return None


def _retrieval_secrets(s: DataSource, params: dict) -> dict:
    """The Voyage re-ranker key travels in retrieval_params (write-only, like
    every other key here) and is stored Fernet-encrypted in the same JSON —
    no extra column, and the clear key never comes back out.

    A blank/absent field keeps the stored key; the string "" clears it.
    """
    raw = params.pop("reranker_api_key", None)
    params.pop("reranker_has_own_key", None)      # read-only flag, never stored
    current = ""
    try:
        current = json.loads(s.retrieval_params or "{}").get("reranker_api_key_enc") or ""
    except Exception:
        current = ""
    if raw is None:
        params["reranker_api_key_enc"] = params.get("reranker_api_key_enc") or current
    elif str(raw).strip():
        params["reranker_api_key_enc"] = encrypt_key(str(raw).strip())
    else:
        params["reranker_api_key_enc"] = ""
    if not params["reranker_api_key_enc"]:
        params.pop("reranker_api_key_enc")
    return params


def _allowed_ids(db: Session, source_id: str) -> list:
    return [a.user_id for a in db.query(DataSourceAccess)
            .filter(DataSourceAccess.data_source_id == source_id).all()]


def source_dict(db: Session, s: DataSource) -> dict:
    """Public shape — no secret ever leaves the backend."""
    from app.services.data_agent.config import (chunking_config,
                                                effective_mode,
                                                generation_config,
                                                retrieval_config)
    rcfg = retrieval_config(s)
    return {
        "id": s.id, "name": s.name, "description": s.description or "",
        "dialect": s.dialect, "host": s.host, "port": s.port,
        "database": s.database, "username": s.username,
        "has_password": bool(s.password_enc),
        "extra_params": json.loads(s.extra_params) if s.extra_params else {},
        "schema_whitelist": (json.loads(s.schema_whitelist)
                             if s.schema_whitelist else []),
        "table_count": s.table_count or 0,
        "mode_auto": s.mode_auto or "base", "mode_override": s.mode_override,
        "mode": effective_mode(s),
        "row_limit": s.row_limit, "timeout_ms": s.timeout_ms,
        "status": s.status or "draft", "last_error": s.last_error,
        "is_private": bool(s.is_private),
        # models
        "llm_provider": s.llm_provider, "llm_model": s.llm_model,
        "llm_provider_id": s.llm_provider_id,
        "llm_has_own_key": bool(s.llm_api_key_enc),
        "llm_api_key_masked": _masked(s.llm_api_key_enc),
        "llm_base_url": s.llm_base_url,
        "embedding_provider": s.embedding_provider,
        "embedding_model": s.embedding_model,
        "embedding_provider_id": s.embedding_provider_id,
        "embedding_has_own_key": bool(s.embedding_api_key_enc),
        "embedding_api_key_masked": _masked(s.embedding_api_key_enc),
        "embedding_base_url": s.embedding_base_url,
        # configs
        "generation": generation_config(s).model_dump(),
        "retrieval": rcfg.public(),
        "reranker_api_key_masked": _masked(rcfg.reranker_api_key_enc or None),
        "chunking": chunking_config(s).model_dump(),
        # knowledge documents live in this hidden RAG space
        "knowledge_space_id": s.knowledge_space_id,
        # ownership
        "owner_id": s.owner_id, "department_id": s.department_id,
        "allowed_user_ids": _allowed_ids(db, s.id),
        "last_introspected_at": str(s.last_introspected_at or "") or None,
        "created_at": str(s.created_at),
    }


def list_sources(db: Session, user) -> list:
    """Role-scoped (mirror of RAG list_spaces):
      ADMIN → every agent · IT → the agents they own
      USER  → only DEPLOYED, published agents of their departments they are
              authorized on."""
    rows = (db.query(DataSource)
            .filter(DataSource.organization_id == user.organization_id)
            .order_by(DataSource.created_at.desc()).all())
    role = _role(user)
    if role == "ADMIN":
        return [source_dict(db, s) for s in rows]
    if role == "IT":
        return [source_dict(db, s) for s in rows if s.owner_id == user.id]

    dept_ids = {d.id for d in getattr(user, "departments", [])}
    out = []
    for s in rows:
        if s.status != "deployed" or s.is_private:
            continue
        if s.department_id and s.department_id not in dept_ids:
            continue
        allowed = _allowed_ids(db, s.id)
        if allowed and user.id not in allowed:
            continue
        out.append(source_dict(db, s))
    return out


def create_source(db: Session, user, data: dict) -> dict:
    if _role(user) not in ("ADMIN", "IT"):
        raise HTTPException(403, "Only IT or admin can create data agents")
    dialect = str(data.get("dialect") or "postgres").lower()
    adapter = adapter_for(dialect)               # validates the dialect
    s = DataSource(
        name=(data.get("name") or "").strip() or "Unnamed agent",
        description=(data.get("description") or "").strip() or None,
        is_private=bool(data.get("is_private", True)),
        dialect=dialect,
        host=(data.get("host") or "").strip(),
        port=int(data.get("port") or adapter.default_port or 0),
        database=(data.get("database") or "").strip(),
        username=(data.get("username") or "").strip(),
        password_enc=encrypt_key(data["password"]) if data.get("password") else None,
        extra_params=json.dumps(data.get("extra_params") or {}),
        schema_whitelist=json.dumps(data.get("schema_whitelist") or []),
        department_id=data.get("department_id") or None,
        owner_id=user.id, organization_id=user.organization_id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return source_dict(db, s)


def update_source(db: Session, source_id: str, user, data: dict) -> dict:
    from app.services.data_agent.vanna.client import evict

    s = require_manager(db, source_id, user.organization_id, user)
    reindex = False
    for k, v in (data or {}).items():
        if v is None:
            continue
        if k in _EDITABLE:
            if k in _REINDEX_TRIGGERS and getattr(s, k, None) != v:
                reindex = True
            setattr(s, k, v)
        elif k in _JSON_FIELDS:
            if k == "retrieval_params":
                v = _retrieval_secrets(s, dict(v or {}))
            setattr(s, k, json.dumps(v))
        elif k in _SECRETS and str(v).strip():
            setattr(s, _SECRETS[k], encrypt_key(str(v).strip()))
    if data.get("mode_override") == "":
        s.mode_override = None
    if reindex and s.status in ("trained", "deployed"):
        s.status = "stale"                # embeddings changed → re-train
    s.updated_at = _now()
    db.commit()
    db.refresh(s)
    dispose(s.id)                         # rebuild the pooled engine
    evict(s.id)                           # rebuild the Vanna client
    return source_dict(db, s)


def delete_source(db: Session, source_id: str, user) -> dict:
    from app.services.data_agent.knowledge import delete_space
    from app.services.data_agent.vanna.client import evict
    s = require_manager(db, source_id, user.organization_id, user)
    dispose(s.id)
    evict(s.id)
    delete_space(db, s)                   # the hidden knowledge RAG space
    db.delete(s)                          # schema, vectors, sessions cascade
    db.commit()
    return {"deleted": True}


def test_connection(db: Session, source_id: str, user) -> dict:
    """Live test with the CURRENTLY saved credentials."""
    from app.services.data_agent.database import test_connection as probe
    s = require_manager(db, source_id, user.organization_id, user)
    result = probe(s)
    if result["ok"]:
        if s.status in ("draft", "error"):
            s.status = "connected"
        s.last_error = None
    else:
        s.status = "error"
        s.last_error = result.get("error")
    db.commit()
    return result


def set_authorization(db: Session, source_id: str, user, user_ids) -> dict:
    """Replace the allowed-users list. Empty = the whole department."""
    s = require_manager(db, source_id, user.organization_id, user)
    db.query(DataSourceAccess).filter(
        DataSourceAccess.data_source_id == s.id).delete()
    for uid in (user_ids or []):
        db.add(DataSourceAccess(data_source_id=s.id, user_id=uid))
    db.commit()
    return source_dict(db, s)


def deploy_source(db: Session, source_id: str, user) -> dict:
    s = require_manager(db, source_id, user.organization_id, user)
    if s.status not in ("trained", "stale"):
        raise HTTPException(400, "Train the agent before deploying")
    s.status = "deployed"
    s.is_private = False                  # deploy = visible to the department
    db.commit()
    db.refresh(s)
    return source_dict(db, s)


def pause_source(db: Session, source_id: str, user) -> dict:
    s = require_manager(db, source_id, user.organization_id, user)
    if s.status == "deployed":
        s.status = "trained"
        db.commit()
        db.refresh(s)
    return source_dict(db, s)


def dialects() -> list:
    return supported_dialects()
