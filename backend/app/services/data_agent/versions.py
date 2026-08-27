"""
Versions — save / apply / deploy config snapshots of a data agent
(the rag_service versions lifecycle, mirrored).

A version stores the PIPELINE config only: generation, model sources,
retrieval, chunking and execution safety. It deliberately excludes the
connection identity (dialect, host, credentials) — a version is "how the
agent thinks", not "where it connects" — and the trained index, which is
rebuilt by Train, not restored.

Deployed = the single row with status DEPLOYED; deploying a version archives
the previous one, so the pointer needs no extra column on data_sources.
"""
from __future__ import annotations

import json
import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.data_agent import DataSource, DataSourceVersion
from app.services.data_agent import sources

logger = logging.getLogger(__name__)

# The columns captured in a snapshot. Connection + identity/lifecycle fields
# (name, host, credentials, department, status) are intentionally excluded.
_CONFIG_COLUMNS = [
    # execution safety
    "row_limit", "timeout_ms", "mode_override", "send_results_to_llm",
    # generation
    "llm_provider", "llm_model", "llm_provider_id", "llm_api_key_enc",
    "llm_base_url", "llm_temperature", "llm_max_tokens",
    "prompt_mode", "system_prompt",
    # embedding
    "embedding_provider", "embedding_model", "embedding_provider_id",
    "embedding_api_key_enc", "embedding_base_url",
    # JSON configs (retrieval_params embeds the encrypted Voyage key)
    "retrieval_params", "chunk_params",
]
# Top-level snapshot keys never sent to the client.
_SECRET_KEYS = ("llm_api_key_enc", "embedding_api_key_enc")

# Changing any of these means the trained vectors no longer match — the
# same trigger set as sources._REINDEX_TRIGGERS.
_REINDEX_COLUMNS = ["embedding_provider", "embedding_model",
                    "embedding_provider_id"]


def _load_json(raw) -> dict:
    try:
        v = json.loads(raw) if isinstance(raw, str) else (raw or {})
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _snapshot(source: DataSource) -> dict:
    return {c: getattr(source, c, None) for c in _CONFIG_COLUMNS}


def _apply(source: DataSource, cfg: dict) -> None:
    for c in _CONFIG_COLUMNS:
        if c in cfg:
            setattr(source, c, cfg[c])


def _reindex_fp(source_or_cfg, from_cfg: bool = False) -> tuple:
    get = (source_or_cfg.get if from_cfg
           else lambda c, d=None: getattr(source_or_cfg, c, d))
    return tuple(str(get(c) or "") for c in _REINDEX_COLUMNS)


def _version_dict(v: DataSourceVersion) -> dict:
    cfg = _load_json(v.config)
    safe = {k: val for k, val in cfg.items() if k not in _SECRET_KEYS}
    # the Voyage re-ranker key travels INSIDE retrieval_params — strip it too
    rp = _load_json(safe.get("retrieval_params"))
    rp.pop("reranker_api_key_enc", None)
    safe["retrieval_params"] = rp
    safe["chunk_params"] = _load_json(safe.get("chunk_params"))
    return {
        "id": v.id, "data_source_id": v.data_source_id,
        "version_number": v.version_number, "label": v.label,
        "status": v.status, "notes": v.notes, "config": safe,
        "has_own_llm_key": bool(cfg.get("llm_api_key_enc")),
        "has_own_embedding_key": bool(cfg.get("embedding_api_key_enc")),
        "created_by": v.created_by, "created_at": str(v.created_at),
    }


def _find_version(db: Session, source_id: str, version_id: str) -> DataSourceVersion:
    v = (db.query(DataSourceVersion)
         .filter(DataSourceVersion.id == version_id,
                 DataSourceVersion.data_source_id == source_id).first())
    if not v:
        raise HTTPException(404, "Version not found")
    return v


def _next_number(db: Session, source_id: str) -> int:
    last = (db.query(DataSourceVersion)
            .filter(DataSourceVersion.data_source_id == source_id)
            .order_by(DataSourceVersion.version_number.desc()).first())
    return (last.version_number + 1) if last else 1


def _refresh_runtime(source_id: str) -> None:
    """Config changed → the pooled engine and the Vanna client are stale."""
    from app.services.data_agent.database import dispose
    from app.services.data_agent.vanna.client import evict
    dispose(source_id)
    evict(source_id)


def list_versions(db: Session, source_id: str, user) -> list:
    sources.require_manager(db, source_id, user.organization_id, user)
    rows = (db.query(DataSourceVersion)
            .filter(DataSourceVersion.data_source_id == source_id)
            .order_by(DataSourceVersion.version_number.desc()).all())
    return [_version_dict(v) for v in rows]


def save_version(db: Session, source_id: str, user,
                 label: str = None, notes: str = None) -> dict:
    s = sources.require_manager(db, source_id, user.organization_id, user)
    n = _next_number(db, s.id)
    v = DataSourceVersion(
        data_source_id=s.id, version_number=n,
        label=(label or f"v{n}").strip(), status="SAVED", notes=notes,
        config=json.dumps(_snapshot(s), default=str),
        created_by=getattr(user, "id", None))
    db.add(v)
    db.commit()
    db.refresh(v)
    return _version_dict(v)


def apply_version(db: Session, source_id: str, user, version_id: str) -> dict:
    """Load a version's config into the working agent — no deploy."""
    s = sources.require_manager(db, source_id, user.organization_id, user)
    if s.status == "deployed":
        raise HTTPException(409, "This agent is deployed and live. Pause the "
                                 "deployment before loading another config.")
    v = _find_version(db, s.id, version_id)
    fp_before = _reindex_fp(s)
    _apply(s, _load_json(v.config))
    if _reindex_fp(s) != fp_before and s.status in ("trained", "stale"):
        s.status = "stale"                 # embeddings changed → re-train
    db.commit()
    db.refresh(s)
    _refresh_runtime(s.id)
    return {"source": sources.source_dict(db, s)}


def deploy_version(db: Session, source_id: str, user, version_id: str) -> dict:
    """Apply a version's config AND make it the live one (agent → deployed)."""
    s = sources.require_manager(db, source_id, user.organization_id, user)
    if s.status not in ("trained", "stale", "deployed"):
        raise HTTPException(400, "Train the agent before deploying a version")
    v = _find_version(db, s.id, version_id)
    fp_before = _reindex_fp(s)
    _apply(s, _load_json(v.config))
    if _reindex_fp(s) != fp_before:
        s.status = "stale"                 # deployed, but needs a re-train
    else:
        s.status = "deployed"
    s.is_private = False                   # deploy = visible to the department
    # exactly one DEPLOYED row per source
    (db.query(DataSourceVersion)
     .filter(DataSourceVersion.data_source_id == s.id,
             DataSourceVersion.status == "DEPLOYED")
     .update({DataSourceVersion.status: "ARCHIVED"}))
    v.status = "DEPLOYED"
    db.commit()
    db.refresh(s)
    _refresh_runtime(s.id)
    return {"source": sources.source_dict(db, s)}


def delete_version(db: Session, source_id: str, user, version_id: str) -> dict:
    sources.require_manager(db, source_id, user.organization_id, user)
    v = _find_version(db, source_id, version_id)
    if v.status == "DEPLOYED":
        raise HTTPException(400, "Can't delete the currently deployed version")
    db.delete(v)
    db.commit()
    return {"deleted": True}
