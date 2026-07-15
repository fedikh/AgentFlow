"""
RAG Service v7 — LLM Factory Edition

CHANGES from v6:
  - generate_answer() removed (the hardcoded Groq one).
  - Now imports generate_answer from app.services.llm_factory.
  - query() calls generate_answer(db, space, question, context, sources_text)
    → the LLM provider/model/key/prompt are now resolved from the space config
      (space's own key → company provider → local GROQ fallback).

Everything else (loaders, parsers, chunking, embedding, search) is UNCHANGED.
"""

import os
import json
import uuid
import glob
import shutil
import tempfile
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import text, or_
from fastapi import HTTPException, UploadFile

from app.models.rag_space import RAGSpace, SpaceStatus
from app.models.rag_space_access import RAGSpaceAccess
from app.models.rag_space_version import RAGSpaceVersion
from app.models.document import Document, DocStatus
from app.models.chunk import Chunk
from app.models.user import User, RoleType
from app.models.department import Department
from app.schemas.rag import CreateRAGSpaceRequest, UpdateRAGSpaceRequest, QueryRequest
from app.config import settings

# ── Modular Loaders & Parsers ──
from app.services.providers.loaders import (
    load_document as li_load_document,
    load_from_url as li_load_from_url,
    SUPPORTED_FORMATS,
)
from app.services.providers.loaders._utils import validate_url, get_url_filename
from app.services.providers.parsers import parse_document as li_parse_document

# ── Chunking factory ──
from app.services.providers.chunking_factory import chunk_document, resolve_config

# ── LLM Factory (NEW) — replaces the hardcoded Groq generate_answer ──
from app.services.llm_factory import generate_answer


import logging

logger = logging.getLogger(__name__)

# ── Embeddings (Batch 6: now resolved per-space via the embedding factory) ──
# The factory picks the space's embedding source (own key → company provider →
# local BGE-M3) and guards the 1024-dim pgvector column. Index-time and
# query-time both go through it with the same space config, so they stay
# consistent. Default behaviour is unchanged (local BGE-M3).
from app.services.embedding_factory import (
    embed_texts as _ef_embed_texts,
    embed_query as _ef_embed_query,
)


def embed_texts(db, space, texts: list[str]) -> list[list[float]]:
    return _ef_embed_texts(db, space, texts)


def embed_query(db, space, text: str) -> list[float]:
    return _ef_embed_query(db, space, text)


# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def _find_space(db: Session, space_id: str, org_id: str) -> RAGSpace:
    space = db.query(RAGSpace).filter(RAGSpace.id == space_id, RAGSpace.organization_id == org_id).first()
    if not space:
        raise HTTPException(404, "RAG Space not found")
    return space


# ══════════════════════════════════════════════════════
# ACCESS CONTROL (Batch 1) — per-user access within a department
# ══════════════════════════════════════════════════════

def _get_access_user_ids(db: Session, space_id: str) -> list[str]:
    """All user_ids explicitly allowed on this space. Empty list = no restriction."""
    rows = db.query(RAGSpaceAccess).filter(RAGSpaceAccess.rag_space_id == space_id).all()
    return [r.user_id for r in rows]


def _set_space_access(db: Session, space: RAGSpace, org_id: str, user_ids):
    """
    Replace the access list for a space.
      user_ids None  → do nothing (caller decides)
      user_ids []    → clear all restrictions (every department user can query)
      user_ids [..]  → restrict to exactly these users
    Only users that belong to the space's department are kept (safety).
    """
    if user_ids is None:
        return

    # wipe current rows
    db.query(RAGSpaceAccess).filter(RAGSpaceAccess.rag_space_id == space.id).delete()

    unique_ids = list(dict.fromkeys(user_ids))  # de-dupe, keep order
    if not unique_ids:
        return  # cleared → unrestricted

    # keep only valid users of this org that are members of the space's department
    for uid in unique_ids:
        user = db.query(User).filter(User.id == uid, User.organization_id == org_id).first()
        if not user:
            continue
        if space.department_id and not any(d.id == space.department_id for d in user.departments):
            continue
        db.add(RAGSpaceAccess(rag_space_id=space.id, user_id=uid))


# ══════════════════════════════════════════════════════
# PERMISSIONS — ownership (build) vs department-wide read (view)
# ══════════════════════════════════════════════════════

def _role_name(user) -> str:
    return _strval(getattr(user, "role", None)) or ""


def _is_dept_member(space: RAGSpace, user) -> bool:
    dept_id = getattr(space, "department_id", None)
    return bool(dept_id) and any(
        d.id == dept_id for d in getattr(user, "departments", [])
    )


def _is_owner_or_admin(space: RAGSpace, user) -> bool:
    if _role_name(user) == "ADMIN":
        return True
    owner_id = getattr(space, "owner_id", None)
    # Legacy owner-less spaces: any IT acts as owner (no backfill available).
    if owner_id is None:
        return _role_name(user) == "IT"
    return owner_id == user.id


def _can_build(db: Session, space: RAGSpace, user) -> bool:
    """Only the OWNER (or admin) may edit/config/version/deploy/delete a space."""
    if user is None:
        return False
    return _is_owner_or_admin(space, user)


def _require_builder(db: Session, space: RAGSpace, user):
    """Raise 403 unless `user` owns this space (or is admin)."""
    if not _can_build(db, space, user):
        raise HTTPException(403, "Only the space owner can modify this space")


def _can_view(db: Session, space: RAGSpace, user) -> bool:
    """Any IT of the space's department may VIEW it (read-only). Owner/admin edit."""
    if user is None:
        return True
    if _can_build(db, space, user):
        return True
    return _role_name(user) == "IT" and _is_dept_member(space, user)


def _require_view(db: Session, space: RAGSpace, user):
    """Raise 403 unless `user` may at least view this space."""
    if not _can_view(db, space, user):
        raise HTTPException(403, "You don't have access to this space")


def require_owner(db: Session, space_id: str, org_id: str, user) -> RAGSpace:
    """Owner-only actions (upload/delete docs, deploy, publish). Raises 403."""
    space = _find_space(db, space_id, org_id)
    if not _is_owner_or_admin(space, user):
        raise HTTPException(403, "Only the space owner can do this")
    return space


def require_editable(db: Session, space_id: str, org_id: str, user) -> RAGSpace:
    """Owner-only AND the space must not be live. A deployed (ACTIVE) space is
    locked; the owner must 'Stop to edit' (pause) before changing docs/config."""
    space = require_owner(db, space_id, org_id, user)
    if _strval(space.status) == "ACTIVE":
        raise HTTPException(
            409,
            "This space is deployed and live. Click 'Stop to edit' before making changes.",
        )
    return space


def list_department_users(db: Session, dept_id: str, org_id: str) -> list[dict]:
    """
    List the members of a department the owner can grant usage to — both
    end-users AND IT users (an owner can personalise who consumes the deployed
    agent). Scoped to the caller's organization.
    """
    dept = db.query(Department).filter(
        Department.id == dept_id, Department.organization_id == org_id
    ).first()
    if not dept:
        raise HTTPException(404, "Department not found")

    users = (
        db.query(User)
        .filter(User.organization_id == org_id,
                User.role.in_([RoleType.USER, RoleType.IT]))
        .all()
    )
    members = [u for u in users if any(d.id == dept_id for d in u.departments)]
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role.value if hasattr(u.role, "value") else str(u.role),
            "status": u.status.value if hasattr(u.status, "value") else str(u.status),
        }
        for u in members
    ]


def check_space_access(db: Session, space: RAGSpace, user: User):
    """
    Enforce query-time (consumption) access. Raises if the user may not use it.
      - ADMIN            → always allowed.
      - OWNER            → always allowed (builds & tests the space).
      - everyone else    → the space must be DEPLOYED + published, the user a
                           member of its department, and (if a restriction is
                           set) listed in rag_space_access. This now applies to
                           non-owner IT consumers too, so the owner can truly
                           restrict who uses the agent.
    Org scoping is already handled by _find_space.
    """
    if _role_name(user) == "ADMIN" or getattr(space, "owner_id", None) == user.id:
        return

    # A space paused for editing is visible but temporarily unusable.
    if _strval(space.status) == "EDITING":
        raise HTTPException(409, "This agent is being updated. Please check back soon.")
    # Must be DEPLOYED and published to consumers.
    if _strval(space.status) != "ACTIVE" or getattr(space, "is_private", False):
        raise HTTPException(403, "This space is not available")

    # Must belong to the space's department
    if space.department_id and not _is_dept_member(space, user):
        raise HTTPException(403, "You are not a member of this space's department")

    allowed = _get_access_user_ids(db, space.id)
    if allowed and user.id not in allowed:
        raise HTTPException(403, "You are not allowed to use this space")


def _strval(v):
    """Enum-or-string → lowercase-safe string name (or None)."""
    if v is None:
        return None
    return str(v.value if hasattr(v, "value") else v)


def _load_json(raw):
    """JSON text (or dict) → dict; {} on anything unparseable."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _norm_chunk_mode(mode) -> str:
    """Legacy FIXED_ALL/ADAPTIVE → SINGLE; PER_DOCUMENT preserved."""
    m = _strval(mode) or "SINGLE"
    m = m.upper()
    return "PER_DOCUMENT" if m in ("PER_DOCUMENT", "PER_DOC") else "SINGLE"


def _space_dict(db, space, user=None):
    num_docs = db.query(Document).filter(Document.rag_space_id == space.id).count()
    num_chunks = db.query(Chunk).filter(Chunk.rag_space_id == space.id).count()
    return {
        "id": space.id, "name": space.name, "description": space.description,
        "status": _strval(getattr(space, 'status', 'DRAFT')) or 'DRAFT',
        "organization_id": space.organization_id,
        "department_id": space.department_id,
        # ── Ownership / lifecycle (versioning + permissions) ──
        "owner_id": getattr(space, "owner_id", None),
        "is_private": bool(getattr(space, "is_private", False)),
        "deployed_version_id": getattr(space, "deployed_version_id", None),
        "reindex_required": bool(getattr(space, "reindex_required", False)),
        "version_count": db.query(RAGSpaceVersion).filter(
            RAGSpaceVersion.rag_space_id == space.id
        ).count(),
        "is_owner": (user is not None and getattr(space, "owner_id", None) == user.id),
        "can_build": _can_build(db, space, user) if user is not None else True,
        "department_name": space.department.name if getattr(space, "department", None) else None,
        "chunk_size": space.chunk_size, "chunk_overlap": space.chunk_overlap,
        "chunk_strategy": _strval(space.chunk_strategy) or "recursive",
        "chunk_params": _load_json(getattr(space, 'chunk_params', None)),
        "chunk_format_map": _load_json(getattr(space, 'chunk_format_map', None)),
        "chunk_mode": _norm_chunk_mode(getattr(space, 'chunk_mode', None)),
        "embedding_provider": getattr(space, 'embedding_provider', 'LOCAL') or 'LOCAL',
        "embedding_model": getattr(space, 'embedding_model', 'BAAI/bge-m3') or 'BAAI/bge-m3',
        # NEW (Batch 6): embedding source for the IT selector (mirrors LLM)
        "embedding_provider_id": getattr(space, 'embedding_provider_id', None),
        "embedding_has_own_key": bool(getattr(space, 'embedding_api_key_enc', None)),
        "embedding_base_url": getattr(space, 'embedding_base_url', None),
        "llm_provider": getattr(space, 'llm_provider', 'GROQ') or 'GROQ',
        "llm_model": getattr(space, 'llm_model', 'llama-3.3-70b-versatile') or 'llama-3.3-70b-versatile',
        "llm_temperature": getattr(space, 'llm_temperature', 0.2) if getattr(space, 'llm_temperature', None) is not None else 0.2,
        "llm_max_tokens": getattr(space, 'llm_max_tokens', 1024) or 1024,
        # NEW: provider source for the IT selector (safe getattr — may not exist yet)
        "llm_provider_id": getattr(space, 'llm_provider_id', None),
        "llm_has_own_key": bool(getattr(space, 'llm_api_key_enc', None)),
        "top_k": space.top_k,
        "search_engine": getattr(space, 'search_engine', 'HYBRID') or 'HYBRID',
        "semantic_weight": getattr(space, 'semantic_weight', 0.7) if getattr(space, 'semantic_weight', None) is not None else 0.7,
        "reranking_enabled": getattr(space, 'reranking_enabled', False) or False,
        "system_prompt": getattr(space, 'system_prompt', None),
        # NEW (Batch 1): per-user access control
        "allowed_user_ids": _get_access_user_ids(db, space.id),
        "num_documents": num_docs, "num_chunks": num_chunks,
        "created_at": str(space.created_at),
    }

def _doc_dict(doc):
    status = doc.status.value if hasattr(doc.status, 'value') else str(doc.status)
    return {
        "id": doc.id, "file_name": doc.file_name, "file_type": doc.file_type,
        "file_size": doc.file_size,
        "source_type": getattr(doc, 'source_type', 'local') or 'local',
        "source_url": getattr(doc, 'source_url', None),
        "num_chunks": doc.num_chunks, "status": status, "error_msg": doc.error_msg,
        "chunk_strategy": _strval(getattr(doc, 'chunk_strategy', None)),
        "chunk_params": _load_json(getattr(doc, 'chunk_params', None)),
        "chosen_strategy": getattr(doc, 'chosen_strategy', None),
        "extract_images": bool(getattr(doc, 'extract_images', True)),
        "has_loaded_content": bool(doc.loaded_content) if hasattr(doc, 'loaded_content') else False,
        "has_extracted_content": bool(doc.extracted_content) if hasattr(doc, 'extracted_content') else False,
        "rag_space_id": doc.rag_space_id, "uploaded_at": str(doc.uploaded_at),
    }


# ══════════════════════════════════════════════════════
# VERSIONING — config snapshots + deploy lifecycle
# ══════════════════════════════════════════════════════

# The pipeline columns captured in a version snapshot. Identity/lifecycle fields
# (name, department, status, owner, is_private) are intentionally excluded.
_VERSION_CONFIG_COLUMNS = [
    "chunk_mode", "chunk_size", "chunk_overlap", "chunk_strategy",
    "chunk_params", "chunk_format_map",
    "embedding_provider", "embedding_model",
    "embedding_provider_id", "embedding_api_key_enc", "embedding_base_url",
    "llm_provider", "llm_model", "llm_temperature", "llm_max_tokens",
    "llm_provider_id", "llm_api_key_enc", "llm_base_url",
    "top_k", "search_engine", "semantic_weight", "reranking_enabled",
    "system_prompt",
]
_VERSION_SECRET_KEYS = ("llm_api_key_enc", "embedding_api_key_enc")

# Only these columns affect the built index. A change to any of them means the
# stored chunks are stale and a full re-index is needed. Query-time fields
# (llm_*, top_k, semantic_weight, reranking, system_prompt) do NOT.
_INDEX_COLUMNS = [
    "chunk_mode", "chunk_size", "chunk_overlap", "chunk_strategy",
    "chunk_params", "chunk_format_map",
    "embedding_provider", "embedding_model",
    "embedding_provider_id", "embedding_api_key_enc", "embedding_base_url",
]


def _index_fp(space) -> tuple:
    """Fingerprint of the index-relevant config; compare before/after an edit to
    decide whether a re-index is actually required."""
    return tuple(str(getattr(space, c, None)) for c in _INDEX_COLUMNS)


def _config_fp(space) -> tuple:
    """Fingerprint of the FULL pipeline config (index + query-time). Used to tell
    whether an edit changed the pipeline — a change is not allowed while a space
    is deployed (live); the owner must 'Stop to edit' first."""
    return tuple(str(getattr(space, c, None)) for c in _VERSION_CONFIG_COLUMNS)


def _snapshot_config(space: RAGSpace) -> dict:
    """Capture the space's current pipeline config as a JSON-serializable dict.
    chunk_params/chunk_format_map are stored as text and copied verbatim."""
    return {col: getattr(space, col, None) for col in _VERSION_CONFIG_COLUMNS}


def _apply_config(space: RAGSpace, cfg: dict):
    """Write a version's snapshot back onto the space columns."""
    for col in _VERSION_CONFIG_COLUMNS:
        if col in cfg:
            setattr(space, col, cfg[col])


def _version_dict(v: RAGSpaceVersion) -> dict:
    cfg = _load_json(v.config)
    # Never leak encrypted keys to the client — expose only their presence.
    safe_cfg = {k: val for k, val in cfg.items() if k not in _VERSION_SECRET_KEYS}
    return {
        "id": v.id,
        "rag_space_id": v.rag_space_id,
        "version_number": v.version_number,
        "label": v.label,
        "status": v.status,
        "notes": v.notes,
        "config": safe_cfg,
        "has_own_llm_key": bool(cfg.get("llm_api_key_enc")),
        "has_own_embedding_key": bool(cfg.get("embedding_api_key_enc")),
        "created_by": v.created_by,
        "created_at": str(v.created_at),
    }


def _find_version(db: Session, space_id: str, version_id: str) -> RAGSpaceVersion:
    v = db.query(RAGSpaceVersion).filter(
        RAGSpaceVersion.id == version_id,
        RAGSpaceVersion.rag_space_id == space_id,
    ).first()
    if not v:
        raise HTTPException(404, "Version not found")
    return v


def _next_version_number(db: Session, space_id: str) -> int:
    last = db.query(RAGSpaceVersion).filter(
        RAGSpaceVersion.rag_space_id == space_id
    ).order_by(RAGSpaceVersion.version_number.desc()).first()
    return (last.version_number + 1) if last else 1


def _create_version(db, space, user, label=None, notes=None) -> RAGSpaceVersion:
    n = _next_version_number(db, space.id)
    v = RAGSpaceVersion(
        rag_space_id=space.id,
        version_number=n,
        label=(label or f"v{n}").strip(),
        status="SAVED",
        notes=notes,
        config=json.dumps(_snapshot_config(space)),
        created_by=getattr(user, "id", None),
    )
    db.add(v)
    db.flush()
    return v


def save_version(db, space_id, org_id, user, label=None, notes=None) -> dict:
    space = _find_space(db, space_id, org_id)
    _require_builder(db, space, user)
    v = _create_version(db, space, user, label, notes)
    db.commit()
    db.refresh(v)
    return _version_dict(v)


def list_versions(db, space_id, org_id, user) -> list[dict]:
    space = _find_space(db, space_id, org_id)
    _require_view(db, space, user)   # read-only for non-owner IT of the department
    versions = db.query(RAGSpaceVersion).filter(
        RAGSpaceVersion.rag_space_id == space.id
    ).order_by(RAGSpaceVersion.version_number.desc()).all()
    return [_version_dict(v) for v in versions]


def apply_version(db, space_id, org_id, user, version_id) -> dict:
    """Load a version's config into the working space (without deploying it)."""
    space = _find_space(db, space_id, org_id)
    _require_builder(db, space, user)
    if _strval(space.status) == "ACTIVE":
        raise HTTPException(
            409,
            "This space is deployed and live. Click 'Stop to edit' before loading another config.",
        )
    v = _find_version(db, space.id, version_id)
    fp_before = _index_fp(space)
    _apply_config(space, _load_json(v.config))
    if _index_fp(space) != fp_before:
        space.reindex_required = True   # index-relevant config changed
    db.commit()
    db.refresh(space)
    return {"space": _space_dict(db, space, user),
            "reindex_required": bool(space.reindex_required)}


def _mark_deployed(db, space, version: RAGSpaceVersion, publish: bool):
    """Shared deploy tail: flip status/pointer + archive the prior deployed one.
    Does NOT touch reindex_required — callers set it only when the config that's
    being deployed actually differs from what's indexed."""
    # Archive any previously-deployed version of this space.
    db.query(RAGSpaceVersion).filter(
        RAGSpaceVersion.rag_space_id == space.id,
        RAGSpaceVersion.status == "DEPLOYED",
    ).update({RAGSpaceVersion.status: "ARCHIVED"})
    version.status = "DEPLOYED"
    space.status = SpaceStatus.ACTIVE
    space.deployed_version_id = version.id
    if publish:
        space.is_private = False


def deploy_version(db, space_id, org_id, user, version_id, publish=False) -> dict:
    """Deploy an existing saved version → applies its config + flips to ACTIVE.
    Owner-only."""
    space = _find_space(db, space_id, org_id)
    if not _is_owner_or_admin(space, user):
        raise HTTPException(403, "Only the owner can deploy this space")
    v = _find_version(db, space.id, version_id)
    fp_before = _index_fp(space)
    _apply_config(space, _load_json(v.config))
    if _index_fp(space) != fp_before:
        space.reindex_required = True   # deploying a different index config
    _mark_deployed(db, space, v, publish)
    db.commit()
    db.refresh(space)
    return {"space": _space_dict(db, space, user),
            "reindex_required": bool(space.reindex_required)}


def deploy_current(db, space_id, org_id, user, label=None, notes=None, publish=False) -> dict:
    """Snapshot the current working config into a new version and deploy it.
    Owner-only."""
    space = _find_space(db, space_id, org_id)
    if not _is_owner_or_admin(space, user):
        raise HTTPException(403, "Only the owner can deploy this space")
    # Deploying the CURRENT working config → no config change, so reindex_required
    # keeps whatever it already is (True only if the IT changed index settings and
    # hasn't re-indexed yet).
    v = _create_version(db, space, user, label, notes)
    _mark_deployed(db, space, v, publish)
    db.commit()
    db.refresh(space)
    return {"space": _space_dict(db, space, user),
            "reindex_required": bool(space.reindex_required)}


def set_publish(db, space_id, org_id, user, is_private: bool) -> dict:
    """Toggle end-user exposure of a deployed space (publish / unpublish).
    Owner-only."""
    space = _find_space(db, space_id, org_id)
    if not _is_owner_or_admin(space, user):
        raise HTTPException(403, "Only the owner can publish this space")
    space.is_private = bool(is_private)
    db.commit()
    db.refresh(space)
    return _space_dict(db, space, user)


def pause_deployment(db, space_id, org_id, user) -> dict:
    """Take a deployed space offline for editing. End users see it as "updating"
    and can't query it until it's re-deployed. Owner-only."""
    space = _find_space(db, space_id, org_id)
    if not _is_owner_or_admin(space, user):
        raise HTTPException(403, "Only the owner can pause this space")
    if _strval(space.status) != "ACTIVE":
        raise HTTPException(400, "Only a deployed (ACTIVE) space can be paused")
    space.status = SpaceStatus.EDITING
    db.commit()
    db.refresh(space)
    return _space_dict(db, space, user)


def delete_version(db, space_id, org_id, user, version_id) -> dict:
    space = _find_space(db, space_id, org_id)
    _require_builder(db, space, user)
    v = _find_version(db, space.id, version_id)
    if space.deployed_version_id == v.id:
        raise HTTPException(400, "Can't delete the currently deployed version")
    db.delete(v)
    db.commit()
    return {"message": f"Version '{v.label}' deleted"}


# ══════════════════════════════════════════════════════
# SPACES CRUD
# ══════════════════════════════════════════════════════

def create_space(db: Session, data: CreateRAGSpaceRequest, org_id: str, user) -> dict:
    space = RAGSpace(
        name=data.name, description=data.description or "",
        organization_id=org_id, department_id=data.department_id,
        # Owner = the creating IT; private to the owner until deployed/published.
        owner_id=getattr(user, "id", None),
        # Default private (just the owner + IT team); the creator can opt into
        # a department space at creation.
        is_private=(data.is_private if getattr(data, "is_private", None) is not None else True),
        chunk_size=data.chunk_size or 512, chunk_overlap=data.chunk_overlap or 50,
        chunk_strategy=(_strval(data.chunk_strategy) or "recursive").lower(),
        chunk_mode=_norm_chunk_mode(getattr(data, 'chunk_mode', None)),
        chunk_params=json.dumps(data.chunk_params) if getattr(data, 'chunk_params', None) else None,
        chunk_format_map=json.dumps(data.chunk_format_map) if getattr(data, 'chunk_format_map', None) else None,
    )
    db.add(space)
    db.flush()  # need space.id before adding access rows

    # ── Access control (Batch 1) — optional at creation ──
    _set_space_access(db, space, org_id, getattr(data, "allowed_user_ids", None))

    db.commit()
    db.refresh(space)
    return _space_dict(db, space, user)


def list_spaces(db: Session, org_id: str, user) -> list:
    """Role-scoped listing (a single endpoint feeds IT / ADMIN / USER pages):
      ADMIN → every space in the org (the admin monitor depends on this).
      IT    → spaces they own or collaborate on (+ legacy owner-less spaces).
      USER  → only DEPLOYED, published, department spaces they're allowed on.
    """
    q = db.query(RAGSpace).filter(RAGSpace.organization_id == org_id)
    role = _role_name(user)

    if role == "ADMIN":
        spaces = q.all()

    elif role == "IT":
        # An IT sees every space of their department(s) — read-only for the ones
        # they don't own. Plus their own spaces and legacy owner-less spaces.
        dept_ids = [d.id for d in getattr(user, "departments", [])]
        conds = [RAGSpace.owner_id == user.id, RAGSpace.owner_id.is_(None)]
        if dept_ids:
            conds.append(RAGSpace.department_id.in_(dept_ids))
        spaces = q.filter(or_(*conds)).all()

    else:  # USER
        dept_ids = [d.id for d in getattr(user, "departments", [])]
        if not dept_ids:
            return []
        # ACTIVE = usable; EDITING = shown as "updating" (visible but not usable).
        candidates = q.filter(
            RAGSpace.status.in_([SpaceStatus.ACTIVE, SpaceStatus.EDITING]),
            RAGSpace.is_private.is_(False),
            RAGSpace.department_id.in_(dept_ids),
        ).all()
        spaces = [
            s for s in candidates
            if not (_get_access_user_ids(db, s.id))  # unrestricted
            or user.id in _get_access_user_ids(db, s.id)
        ]

    return [_space_dict(db, s, user) for s in spaces]


def get_space(db: Session, space_id: str, org_id: str, user=None) -> dict:
    space = _find_space(db, space_id, org_id)
    if user is not None:
        _require_view(db, space, user)   # any department IT may open (read-only)
    return _space_dict(db, space, user)


def update_space(db: Session, space_id: str, org_id: str, data: UpdateRAGSpaceRequest, user=None) -> dict:
    space = _find_space(db, space_id, org_id)
    if user is not None:
        _require_builder(db, space, user)
    payload = data.dict(exclude_unset=True)

    # Snapshot the index-relevant config BEFORE applying the edit. We flag a
    # re-index only if it actually CHANGES (the form re-sends every field on
    # every save, so presence alone can't mean "changed").
    _fp_before = _index_fp(space)
    # Full-config snapshot too — a live (deployed) space may NOT change its
    # pipeline config; access-list / name changes stay allowed.
    _cfp_before = _config_fp(space)
    _was_active = _strval(space.status) == "ACTIVE"

    # Chiffre la clé propre de l'IT si fournie (jamais stockée en clair)
    if "llm_api_key" in payload:
        raw = payload.pop("llm_api_key")
        if raw:
            from app.services.providers_crypto import encrypt_key
            space.llm_api_key_enc = encrypt_key(raw)
        else:
            space.llm_api_key_enc = None   # clé vidée

    # Batch 6: same for the embedding own key
    if "embedding_api_key" in payload:
        raw = payload.pop("embedding_api_key")
        if raw:
            from app.services.providers_crypto import encrypt_key
            space.embedding_api_key_enc = encrypt_key(raw)
        else:
            space.embedding_api_key_enc = None

    # ── Access control (Batch 1) — sync the allowed-user list ──
    # Pop it out so the generic setattr loop below never sees it (not a column).
    if "allowed_user_ids" in payload:
        _set_space_access(db, space, org_id, payload.pop("allowed_user_ids"))

    # ── Chunking: params dict → JSON text; normalize strategy/mode strings ──
    if "chunk_params" in payload:
        cp = payload.pop("chunk_params")
        space.chunk_params = json.dumps(cp) if cp else None
    if "chunk_format_map" in payload:
        fm = payload.pop("chunk_format_map")
        space.chunk_format_map = json.dumps(fm) if fm else None
    if payload.get("chunk_strategy"):
        payload["chunk_strategy"] = str(payload["chunk_strategy"]).lower()
    if payload.get("chunk_mode"):
        payload["chunk_mode"] = _norm_chunk_mode(payload["chunk_mode"])

    # Fields that may be explicitly set to NULL to CLEAR them (e.g. switching a
    # source from Company back to Local must null out the provider_id). Because
    # payload already excludes unset fields, a None here is an intentional clear.
    NULLABLE_FIELDS = {
        "llm_provider_id", "embedding_provider_id",
        "llm_base_url", "embedding_base_url",
        "system_prompt", "department_id",
    }

    for field, value in payload.items():
        if value is not None or field in NULLABLE_FIELDS:
            setattr(space, field, value)

    # A live space is locked: reject any change to the pipeline config. (Access
    # list, name, description are not part of the config fingerprint, so those
    # still go through while deployed.)
    if _was_active and _config_fp(space) != _cfp_before:
        db.rollback()
        raise HTTPException(
            409,
            "This space is deployed and live. Click 'Stop to edit' before changing its configuration.",
        )

    # Flag a re-index only if an index-relevant value actually changed.
    if _index_fp(space) != _fp_before:
        space.reindex_required = True

    db.commit()
    db.refresh(space)
    return _space_dict(db, space, user)

def _safe_unlink(path: str, space_id: str):
    """Delete a file only if it lives under uploads/{space_id} (path-guard)."""
    if not path:
        return
    try:
        safe_root = os.path.abspath(os.path.join("uploads", space_id))
        full = os.path.abspath(path)
        if full.startswith(safe_root + os.sep) and os.path.isfile(full):
            os.unlink(full)
    except Exception as e:
        logger.warning(f"[CLEANUP] could not remove {path}: {e}")


def _safe_rmtree(path: str, space_id: str):
    """Recursively delete a directory only if it lives under uploads/{space_id}."""
    if not path:
        return
    try:
        safe_root = os.path.abspath(os.path.join("uploads", space_id))
        full = os.path.abspath(path)
        if full.startswith(safe_root + os.sep) and os.path.isdir(full):
            shutil.rmtree(full, ignore_errors=True)
    except Exception as e:
        logger.warning(f"[CLEANUP] could not remove dir {path}: {e}")


def _document_source_path(doc, space_id: str) -> str:
    """Absolute path to a document's original uploaded file, or '' if unknown."""
    if doc.loaded_content:
        try:
            fp = json.loads(doc.loaded_content).get("file_path", "")
            if fp:
                return fp
        except Exception:
            pass
    matches = glob.glob(os.path.join("uploads", space_id, f"{doc.id}.*"))
    return matches[0] if matches else ""


def _document_file_paths(doc, space_id: str) -> list[str]:
    """All on-disk files owned by a document: the source file + its images."""
    paths = []
    # 1) source file — from loaded_content, else uploads/{space_id}/{doc.id}.*
    if doc.loaded_content:
        try:
            fp = json.loads(doc.loaded_content).get("file_path", "")
            if fp:
                paths.append(fp)
        except Exception:
            pass
    paths += glob.glob(os.path.join("uploads", space_id, f"{doc.id}.*"))
    # 2) extracted images referenced by this document's parsed content
    if doc.extracted_content:
        try:
            pd = json.loads(doc.extracted_content)
            for img in pd.get("images", []):
                p = img.get("image_path")
                if p:
                    paths.append(p)
        except Exception:
            pass
    return paths


def delete_space(db: Session, space_id: str, org_id: str, user=None) -> dict:
    space = _find_space(db, space_id, org_id)
    if user is not None:
        # Only the owner (or an admin) may delete a space.
        if not _is_owner_or_admin(space, user):
            raise HTTPException(403, "Only the space owner can delete it")
    db.delete(space)
    db.commit()
    # Remove the whole uploads folder for this space (source files + images).
    try:
        space_dir = os.path.abspath(os.path.join("uploads", space_id))
        uploads_root = os.path.abspath("uploads")
        if space_dir.startswith(uploads_root + os.sep) and os.path.isdir(space_dir):
            shutil.rmtree(space_dir, ignore_errors=True)
    except Exception as e:
        logger.warning(f"[CLEANUP] could not remove space folder {space_id}: {e}")
    return {"message": f"Space '{space.name}' deleted"}

def list_documents(db: Session, space_id: str, org_id: str) -> list:
    _find_space(db, space_id, org_id)
    docs = db.query(Document).filter(Document.rag_space_id == space_id).order_by(Document.uploaded_at.desc()).all()
    return [_doc_dict(d) for d in docs]


def list_public_documents(db: Session, space_id: str, org_id: str, user) -> list:
    """End-user document list for a deployed space. Enforces the same access
    rules as querying (ACTIVE + published + department + allow-list), then
    returns only INDEXED documents (the ones actually powering answers)."""
    space = _find_space(db, space_id, org_id)
    check_space_access(db, space, user)
    docs = (
        db.query(Document)
        .filter(Document.rag_space_id == space_id, Document.status == DocStatus.INDEXED)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "file_name": d.file_name,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "num_chunks": d.num_chunks,
            "source_type": getattr(d, "source_type", "local") or "local",
            "source_url": getattr(d, "source_url", None),
        }
        for d in docs
    ]

def delete_document(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Remove the document's on-disk files (source + its extracted images).
    for path in _document_file_paths(doc, space_id):
        _safe_unlink(path, space_id)

    # Remove the document's dedicated images folder as well. This catches images
    # that were extracted to disk but are no longer listed in extracted_content
    # (e.g. image extraction was turned OFF after a first parse).
    try:
        from app.services.providers.parsers._docling import _get_images_dir
        src = _document_source_path(doc, space_id)
        if src:
            _safe_rmtree(_get_images_dir(src), space_id)
    except Exception as e:
        logger.warning(f"[CLEANUP] could not remove images folder for {doc_id}: {e}")

    name = doc.file_name
    db.delete(doc)
    db.commit()
    return {"message": f"Document '{name}' deleted"}


def get_document_file(db: Session, space_id: str, doc_id: str, org_id: str, user=None) -> dict:
    """Locate the original uploaded file for a document (to preview/download).
    End users are held to the same access rules as querying; IT/ADMIN keep the
    org-scoped behavior."""
    space = _find_space(db, space_id, org_id)
    if user is not None and _role_name(user) == "USER":
        check_space_access(db, space, user)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    path = None
    if doc.loaded_content:
        try:
            fp = json.loads(doc.loaded_content).get("file_path")
            if fp and os.path.exists(fp):
                path = fp
        except Exception:
            pass
    if not path:
        matches = [m for m in glob.glob(os.path.join("uploads", space_id, f"{doc_id}.*")) if os.path.isfile(m)]
        if matches:
            path = os.path.abspath(matches[0])
    if not path or not os.path.exists(path):
        raise HTTPException(404, "Original file not found on disk")
    return {"path": os.path.abspath(path), "file_name": doc.file_name}

def list_chunks(db: Session, space_id: str, doc_id: str, org_id: str) -> list:
    _find_space(db, space_id, org_id)
    chunks = db.query(Chunk).filter(Chunk.document_id == doc_id).order_by(Chunk.chunk_index).all()
    return [{"id": c.id, "content": c.content, "page": c.page, "chunk_index": c.chunk_index,
             "chunk_type": getattr(c, "chunk_type", "text") or "text",
             "strategy": getattr(c, "strategy", None),
             "parent_index": getattr(c, "parent_index", None),
             "image_path": getattr(c, "image_path", None)} for c in chunks]


# ══════════════════════════════════════════════════════
# PER-DOCUMENT STRATEGY
# ══════════════════════════════════════════════════════

def set_document_chunking(db: Session, space_id: str, doc_id: str,
                          strategy: str, params: dict, org_id: str) -> dict:
    """Set a document's per-document chunking strategy + params (PER_DOCUMENT mode).

    strategy is validated against the document's format catalog. An empty /
    "default" strategy clears the override so the doc falls back to the space.
    """
    from app.services.providers.chunking_factory import strategy_def, default_params

    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.rag_space_id == space_id,
    ).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    name = (strategy or "").strip().lower()
    if name in ("", "default", "none"):
        doc.chunk_strategy = None
        doc.chunk_params = None
    else:
        if not strategy_def(doc.file_type, name):
            raise HTTPException(400, f"Strategy '{name}' is not valid for .{doc.file_type}")
        merged = {**default_params(doc.file_type, name), **(params or {})}
        doc.chunk_strategy = name
        doc.chunk_params = json.dumps(merged)

    db.commit()
    db.refresh(doc)
    return _doc_dict(doc)


def set_document_extract_images(db: Session, space_id: str, doc_id: str, enabled: bool, org_id: str) -> dict:
    """Toggle image extraction for a single document (applied on next Load & Parse)."""
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.rag_space_id == space_id,
    ).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    doc.extract_images = bool(enabled)
    db.commit()
    db.refresh(doc)
    return _doc_dict(doc)


def add_document_image(db: Session, space_id: str, doc_id: str, org_id: str, file) -> dict:
    """
    Save an uploaded image into the document's images folder and return its
    absolute path (to be added as an image block in the parsed-content editor).
    """
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.rag_space_id == space_id,
    ).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    ext = os.path.splitext(file.filename or "")[1].lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
        raise HTTPException(400, "Unsupported image type. Use PNG, JPG, WEBP, GIF or BMP.")

    images_dir = os.path.abspath(os.path.join("uploads", space_id, "images"))
    os.makedirs(images_dir, exist_ok=True)
    filename = f"manual_{uuid.uuid4().hex[:10]}{ext}"
    save_path = os.path.join(images_dir, filename)

    with open(save_path, "wb") as f:
        f.write(file.file.read())

    return {"image_path": save_path, "file_name": file.filename}


# ══════════════════════════════════════════════════════
# STEP 1: UPLOAD
# ══════════════════════════════════════════════════════

def _document_identity(doc, org_id: str) -> dict:
    """Document-identity object stamped into the element schema (all formats)."""
    return {
        "id": doc.id,
        "name": doc.file_name,
        "version": "",
        "source": {
            "type": doc.source_type or "upload",
            "filename": doc.file_name,
            "url": doc.source_url or "",
        },
        "created_by": org_id,
    }


async def upload_document(db: Session, space_id: str, org_id: str, file: UploadFile) -> dict:
    space = _find_space(db, space_id, org_id)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        supported = ", ".join(SUPPORTED_FORMATS.keys())
        raise HTTPException(400, f"Format '{ext}' not supported. Accepted: {supported}")

    content = await file.read()

    doc = Document(
        file_name=file.filename,
        file_type=ext.replace(".", ""),
        file_size=len(content),
        source_type="local",
        status=DocStatus.UPLOADING,
        rag_space_id=space_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    upload_dir = os.path.join("uploads", space_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{doc.id}{ext}")

    with open(file_path, "wb") as f:
        f.write(content)

    # Batch 2: .pptx is deferred too (like .pdf/.docx) so image extraction +
    # Gemini summarization run in the shared load-parse step, not at upload.
    if ext in (".pdf", ".docx", ".pptx"):
        doc.loaded_content = json.dumps({"file_path": os.path.abspath(file_path)}, ensure_ascii=False)
        db.commit()
        db.refresh(doc)
        return _doc_dict(doc)

    try:
        loaded_data = li_load_document(file_path)

        from app.services.providers.cleaners import clean_loaded_data
        loaded_data = clean_loaded_data(loaded_data)

        if not loaded_data or not loaded_data.get("raw_text"):
            raise Exception("No content found in document")

        loaded_data["file_path"] = os.path.abspath(file_path)

        parsed_doc_data = loaded_data.pop("parsed_document", None)
        doc.loaded_content = json.dumps(loaded_data, ensure_ascii=False, default=str)

        if parsed_doc_data:
            parsed_doc_data["document_id"] = doc.id
            parsed_doc_data["document"] = _document_identity(doc, org_id)
            doc.extracted_content = json.dumps(parsed_doc_data, ensure_ascii=False)
            doc.status = DocStatus.EXTRACTED
        else:
            doc.status = DocStatus.LOADED

        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        if os.path.exists(file_path):
            os.unlink(file_path)
        raise HTTPException(500, f"Loading failed: {str(e)}")

    return _doc_dict(doc)


async def upload_from_drive(db, space_id, org_id, drive_file_id, access_token):
    import uuid
    from app.services.providers.google_drive import download_from_drive

    space = _find_space(db, space_id, org_id)

    doc_id = str(uuid.uuid4())
    save_dir = os.path.join("uploads", space_id)

    try:
        drive_result = download_from_drive(drive_file_id, access_token, save_dir)
    except Exception as e:
        raise HTTPException(500, f"Google Drive download failed: {e}")

    file_path = drive_result["file_path"]
    file_name = drive_result["file_name"]
    file_size = drive_result["file_size"]
    ext = os.path.splitext(file_name)[1].lower()

    doc = Document(
        id=doc_id,
        rag_space_id=space_id,
        file_name=file_name,
        file_type=ext.replace(".", ""),
        file_size=file_size,
        source_type="google_drive",
        status=DocStatus.UPLOADING,
    )
    db.add(doc)
    db.commit()

    doc.loaded_content = json.dumps({"file_path": os.path.abspath(file_path)}, ensure_ascii=False)
    db.commit()
    db.refresh(doc)

    return _doc_dict(doc)

# ══════════════════════════════════════════════════════
# STEP 2: LOAD + PARSE
# ══════════════════════════════════════════════════════

def load_and_parse_document(db, space_id, doc_id, org_id):
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
 
    file_path = None
    if doc.loaded_content:
        try:
            data = json.loads(doc.loaded_content)
            file_path = data.get("file_path")
        except Exception:
            pass
 
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(400, "File not found — re-upload the document")
 
    try:
        want_images = bool(getattr(doc, "extract_images", True))
        loaded_data = li_load_document(file_path, extract_images=want_images)

        from app.services.providers.cleaners import clean_loaded_data
        loaded_data = clean_loaded_data(loaded_data)

        if not loaded_data or not loaded_data.get("raw_text"):
            raise Exception("No content found in document")

        loaded_data["file_path"] = os.path.abspath(file_path)

        parsed_doc_data = loaded_data.pop("parsed_document", None)
 
        doc.loaded_content = json.dumps(loaded_data, ensure_ascii=False, default=str)
 
        if parsed_doc_data:
            # ── Étape 4 : résumer les images avec Gemini ──
            # Remplit text_for_embedding sur chaque image du ParsedDocument,
            # pour qu'il soit visible dans l'aperçu ET indexable ensuite.
            try:
                from app.services.providers.parsers.parsed_document import ParsedDocument
                from app.services.providers.parsers.image_summarizer import summarize_images_in_parsed
 
                pd = ParsedDocument.from_dict(parsed_doc_data)
                if not want_images:
                    # Image extraction OFF: the loader already skipped extraction,
                    # so pd.images/image elements are empty. Also purge any image
                    # files left on disk from a previous run with extraction ON.
                    pd.images = []
                    pd.elements = [e for e in (pd.elements or []) if e.get("type") != "image"]
                    parsed_doc_data = pd.to_dict()
                    from app.services.providers.parsers._docling import _get_images_dir
                    _safe_rmtree(_get_images_dir(file_path), space_id)
                elif pd.images:
                    n = summarize_images_in_parsed(pd)   # appelle Gemini par image
                    logger.info(f"[LOAD+PARSE] {doc.file_name}: summarized {n}/{len(pd.images)} image(s)")
                    parsed_doc_data = pd.to_dict()        # re-sérialise AVEC les résumés
            except Exception as img_err:
                # Ne bloque jamais le parsing si le résumé échoue
                logger.warning(f"[LOAD+PARSE] image summary skipped: {img_err}")

            # Stamp document identity into the element-schema output.
            if isinstance(parsed_doc_data, dict):
                parsed_doc_data["document_id"] = doc.id
                parsed_doc_data["document"] = _document_identity(doc, org_id)
            doc.extracted_content = json.dumps(parsed_doc_data, ensure_ascii=False)
            doc.status = DocStatus.EXTRACTED
        else:
            doc.status = DocStatus.LOADED
 
        db.commit()
        db.refresh(doc)
 
    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)[:500]
        db.commit()
        raise HTTPException(500, f"Loading failed: {str(e)}")
 
    return _doc_dict(doc)


def load_and_parse_all(db, space_id, org_id):
    _find_space(db, space_id, org_id)
    docs = db.query(Document).filter(
        Document.rag_space_id == space_id,
        Document.status == DocStatus.UPLOADING,
    ).all()

    results = []
    for doc in docs:
        try:
            result = load_and_parse_document(db, space_id, doc.id, org_id)
            results.append({"id": doc.id, "file_name": doc.file_name, "status": result["status"]})
        except Exception as e:
            results.append({"id": doc.id, "file_name": doc.file_name, "status": "ERROR", "error": str(e)})

    return {"processed": len(results), "results": results}

# ══════════════════════════════════════════════════════
# UPLOAD FROM URL
# ══════════════════════════════════════════════════════

def _ingest_url(db: Session, space_id: str, url: str, source_type: str = "url",
                render: bool = True) -> Document:
    """Fetch one URL → save raw HTML → LOADED. Returns the Document (raises on error)."""
    url = validate_url(url)
    doc = Document(
        file_name=get_url_filename(url), file_type="html", file_size=0,
        source_type=source_type, source_url=url,
        status=DocStatus.UPLOADING, rag_space_id=space_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    try:
        loaded_data = li_load_from_url(url, render=render)
        if not loaded_data or not loaded_data.get("raw_text"):
            raise Exception(f"No content found at {url}")

        upload_dir = os.path.join("uploads", space_id)
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{doc.id}.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(loaded_data.get("html") or loaded_data["raw_text"])

        loaded_data["file_path"] = os.path.abspath(file_path)
        loaded_data.pop("html", None)
        doc.loaded_content = json.dumps(loaded_data, ensure_ascii=False, default=str)
        doc.status = DocStatus.LOADED
        db.commit()
        db.refresh(doc)
        return doc
    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)[:500]
        db.commit()
        raise


async def upload_from_url(db: Session, space_id: str, org_id: str, url: str) -> dict:
    _find_space(db, space_id, org_id)
    try:
        doc = _ingest_url(db, space_id, url, "url", render=True)
    except Exception as e:
        raise HTTPException(500, f"Scraping failed: {str(e)}")
    return _doc_dict(doc)


def _ingest_urls(db: Session, space_id: str, org_id: str, urls: list,
                 source_type: str) -> dict:
    """Batch-ingest a list of URLs (fast requests fetch). Returns per-URL results."""
    _find_space(db, space_id, org_id)
    results = []
    for url in urls:
        try:
            doc = _ingest_url(db, space_id, url, source_type, render=False)
            results.append({"url": url, "document_id": doc.id, "status": "LOADED"})
        except Exception as e:
            results.append({"url": url, "status": "ERROR", "error": str(e)[:200]})
    ok = sum(1 for r in results if r.get("document_id"))
    return {"documents": results, "count": ok, "total": len(urls)}


def ingest_raw_html(db: Session, space_id: str, org_id: str, html: str,
                    name: str = None) -> dict:
    """Ingest pasted raw HTML → LOADED (parsed on the Parse step)."""
    _find_space(db, space_id, org_id)
    if not html or not html.strip():
        raise HTTPException(400, "Empty HTML")

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    fname = name or ((title[:60] + ".html") if title else "raw.html")

    doc = Document(file_name=fname, file_type="html", source_type="raw_html",
                   status=DocStatus.UPLOADING, rag_space_id=space_id)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    try:
        upload_dir = os.path.join("uploads", space_id)
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{doc.id}.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)
        for tag in soup(["script", "style", "nav", "footer", "aside", "header", "iframe"]):
            tag.decompose()
        preview = soup.get_text("\n", strip=True)
        loaded_data = {
            "raw_text": preview, "file_type": "HTML", "category": "web",
            "total_chars": len(preview), "file_path": os.path.abspath(file_path),
            "metadata": {"source": fname, "mime_type": "text/html", "title": title},
        }
        doc.loaded_content = json.dumps(loaded_data, ensure_ascii=False, default=str)
        doc.status = DocStatus.LOADED
        db.commit()
        db.refresh(doc)
        return _doc_dict(doc)
    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)[:500]
        db.commit()
        raise HTTPException(500, f"Raw HTML failed: {str(e)}")


def crawl_website(db: Session, space_id: str, org_id: str, url: str,
                  max_depth: int = 2, max_pages: int = 50) -> dict:
    _find_space(db, space_id, org_id)
    from app.services.providers.loaders.web.discovery import crawl_website as discover
    urls = discover(validate_url(url), max_depth=max_depth, max_pages=min(max_pages, 200))
    if not urls:
        raise HTTPException(400, "No pages discovered at that URL")
    return _ingest_urls(db, space_id, org_id, urls, "crawl")


def ingest_sitemap(db: Session, space_id: str, org_id: str, url: str,
                   max_pages: int = 100) -> dict:
    _find_space(db, space_id, org_id)
    from app.services.providers.loaders.web.discovery import discover_sitemap
    urls = discover_sitemap(validate_url(url), max_pages=min(max_pages, 500))
    if not urls:
        raise HTTPException(400, "No URLs found in sitemap")
    return _ingest_urls(db, space_id, org_id, urls, "sitemap")


def ingest_rss(db: Session, space_id: str, org_id: str, url: str,
               max_items: int = 50) -> dict:
    _find_space(db, space_id, org_id)
    from app.services.providers.loaders.web.discovery import discover_rss
    articles = discover_rss(validate_url(url), max_items=min(max_items, 200))
    if not articles:
        raise HTTPException(400, "No articles found in feed")
    res = _ingest_urls(db, space_id, org_id, [a["url"] for a in articles], "rss")
    res["articles"] = articles
    return res


# ══════════════════════════════════════════════════════
# GET LOADED CONTENT
# ══════════════════════════════════════════════════════

def get_loaded_content(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    loaded_data = {}
    if doc.loaded_content:
        loaded_data = json.loads(doc.loaded_content)

    return {
        "document_id": doc.id,
        "file_name": doc.file_name,
        "status": doc.status,
        "raw_text": loaded_data.get("raw_text", ""),
        "num_pages": loaded_data.get("num_pages", 0),
        "file_type": loaded_data.get("file_type", ""),
        "category": loaded_data.get("category", ""),
        "metadata": loaded_data.get("metadata", {}),
        "total_chars": loaded_data.get("total_chars", 0),
    }


# ══════════════════════════════════════════════════════
# STEP 2: PARSE
# ══════════════════════════════════════════════════════

def parse_document(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if not doc.loaded_content:
        raise HTTPException(400, "No loaded content — upload the document first")

    try:
        loaded_data = json.loads(doc.loaded_content)

        parsed_doc = li_parse_document(loaded_data)

        if not parsed_doc.total_sections and not parsed_doc.total_tables:
            raise Exception("Parser produced no sections or tables")

        parsed_doc.document_id = doc.id
        parsed_doc.document = _document_identity(doc, org_id)
        doc.extracted_content = parsed_doc.to_json()
        doc.status = DocStatus.EXTRACTED
        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        raise HTTPException(500, f"Parsing failed: {str(e)}")

    return _doc_dict(doc)


def parse_all_documents(db: Session, space_id: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    docs = db.query(Document).filter(
        Document.rag_space_id == space_id,
        Document.status == DocStatus.LOADED,
    ).all()

    results = []
    for doc in docs:
        try:
            result = parse_document(db, space_id, doc.id, org_id)
            results.append({"id": doc.id, "file_name": doc.file_name, "status": "EXTRACTED"})
        except Exception as e:
            results.append({"id": doc.id, "file_name": doc.file_name, "status": "ERROR", "error": str(e)})

    return {"parsed": len(results), "results": results}


# ══════════════════════════════════════════════════════
# GET EXTRACTED CONTENT
# ══════════════════════════════════════════════════════

def get_extracted_content(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    parsed_data = {}
    if doc.extracted_content:
        parsed_data = json.loads(doc.extracted_content)

    return {
        "document_id": doc.id,
        "file_name": doc.file_name,
        "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
        "parsed_document": parsed_data,
        "total_sections": parsed_data.get("total_sections", 0),
        "total_tables": parsed_data.get("total_tables", 0),
        "total_chars": parsed_data.get("total_chars", 0),
        "ocr_quality": parsed_data.get("ocr_quality", "unknown"),
        "ocr_issues": parsed_data.get("ocr_issues", []),
    }

def update_extracted_content(db: Session, space_id: str, doc_id: str, org_id: str, data) -> dict:
    from app.services.providers.parsers.parsed_document import ParsedDocument

    _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.extracted_content:
        raise HTTPException(400, "No parsed content to edit — parse the document first")

    existing = json.loads(doc.extracted_content)

    payload = data.dict(exclude_unset=True)
    if "title" in payload and payload["title"] is not None:
        existing["title"] = payload["title"]
    if "sections" in payload:
        existing["sections"] = payload["sections"]
    if "tables" in payload:
        existing["tables"] = payload["tables"]
    if "images" in payload:
        existing["images"] = payload["images"]
    if "metadata" in payload and payload["metadata"] is not None:
        existing["metadata"] = payload["metadata"]

    try:
        parsed_doc = ParsedDocument.from_dict(existing)
    except Exception as e:
        raise HTTPException(422, f"Invalid ParsedDocument structure: {str(e)}")

    doc.extracted_content = json.dumps(parsed_doc.to_dict(), ensure_ascii=False)
    doc.status = DocStatus.EXTRACTED
    db.commit()
    db.refresh(doc)

    return get_extracted_content(db, space_id, doc_id, org_id)

# ══════════════════════════════════════════════════════
# STEP 3: PROCESS — chunking + embedding
# ══════════════════════════════════════════════════════

def process_document(db: Session, space_id: str, doc_id: str, org_id: str) -> dict:
    space = _find_space(db, space_id, org_id)
    doc = db.query(Document).filter(Document.id == doc_id, Document.rag_space_id == space_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if not doc.extracted_content:
        raise HTTPException(400, "No parsed content — parse the document first")

    doc.status = DocStatus.PROCESSING
    db.commit()

    try:
        parsed_data = json.loads(doc.extracted_content)

        from app.services.providers.parsers.parsed_document import ParsedDocument
        parsed_doc = ParsedDocument.from_dict(parsed_data)

        if not (parsed_doc.elements or parsed_doc.sections):
            raise Exception("No parsed content to chunk")

        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        db.flush()

        # Per-format chunking: pick strategy+params (SINGLE vs PER_DOCUMENT),
        # chunk the rich element schema.
        cfg = resolve_config(space, doc)
        chunks = chunk_document(parsed_doc, cfg)
        if not chunks:
            raise Exception("No chunks generated")

        chunk_texts = [c["content"] for c in chunks]
        embeddings = embed_texts(db, space, chunk_texts)

        for i, chunk_data in enumerate(chunks):
            db_chunk = Chunk(
                content=chunk_data["content"],
                embedding=embeddings[i],
                page=chunk_data.get("page", 1),
                chunk_index=chunk_data["chunk_index"],
                # Batch 5: persist type + image path so the chat can render images
                chunk_type=chunk_data.get("type", "text"),
                image_path=chunk_data.get("image_path") or None,
                # traceability: which strategy made this chunk + parent link
                strategy=chunk_data.get("strategy"),
                parent_index=chunk_data.get("parent_index"),
                document_id=doc.id,
                rag_space_id=space_id,
            )
            db.add(db_chunk)

        doc.num_chunks = len(chunks)
        doc.status = DocStatus.INDEXED
        db.commit()
        db.refresh(doc)

    except Exception as e:
        doc.status = DocStatus.ERROR
        doc.error_msg = str(e)
        db.commit()
        raise HTTPException(500, f"Processing failed: {str(e)}")

    return _doc_dict(doc)


def process_all_documents(db: Session, space_id: str, org_id: str) -> dict:
    space = _find_space(db, space_id, org_id)
    docs = db.query(Document).filter(
        Document.rag_space_id == space_id,
        Document.status == DocStatus.EXTRACTED,
    ).all()

    results = []
    for doc in docs:
        try:
            result = process_document(db, space_id, doc.id, org_id)
            results.append({"id": doc.id, "file_name": doc.file_name, "status": "INDEXED"})
        except Exception as e:
            results.append({"id": doc.id, "file_name": doc.file_name, "status": "ERROR", "error": str(e)})

    # A full re-index brings the live index back in sync with the config → clear
    # the drift flag (set by config edits / apply / deploy).
    if not any(r.get("status") == "ERROR" for r in results):
        space.reindex_required = False
        db.commit()

    return {"processed": len(results), "results": results}


# ══════════════════════════════════════════════════════
# SEARCH (UNCHANGED)
# ══════════════════════════════════════════════════════

def pgvector_search(db, space_id, query_embedding, top_k):
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    # Batch 5: also return chunk_type + image_path so the chat can render images.
    sql = text("""
        SELECT id, content, page, document_id, chunk_index, chunk_type, image_path,
            1 - (embedding <=> :query_vec) AS similarity_score
        FROM chunks WHERE rag_space_id = :space_id AND embedding IS NOT NULL
        ORDER BY embedding <=> :query_vec LIMIT :top_k
    """)
    result = db.execute(sql, {"query_vec": embedding_str, "space_id": space_id, "top_k": top_k})
    rows = []
    for r in result.fetchall():
        chunk_type = getattr(r, "chunk_type", None) or "text"
        # keep the legacy "type" (used by table keyword-boosting in hybrid_search)
        if chunk_type == "image_summary":
            legacy_type = "image"
        elif r.content.startswith("[TABLE]"):
            legacy_type = "table"
        else:
            legacy_type = "text"
        rows.append({
            "content": r.content,
            "page": r.page,
            "document_id": r.document_id,
            "score": round(float(r.similarity_score), 4),
            "type": legacy_type,
            "chunk_type": chunk_type,
            "image_path": getattr(r, "image_path", None),
        })
    return rows


def keyword_score(query, content):
    query_words = set(query.lower().split())
    content_words = content.lower().split()
    content_counter = Counter(content_words)
    total = len(content_words) or 1
    score = sum(content_counter[w] / total for w in query_words if w in content_counter)
    return min(score * 10, 1.0)


def hybrid_search(db, space_id, query_text, query_embedding, top_k):
    candidates = pgvector_search(db, space_id, query_embedding, top_k * 2)
    if not candidates:
        return []
    for c in candidates:
        kw = keyword_score(query_text, c["content"])
        c["keyword_score"] = round(kw, 4)
        c["semantic_score"] = c["score"]
        combined = (0.7 * c["score"]) + (0.3 * kw)
        table_words = {"table", "tableau", "colonne", "ligne", "total", "montant", "chiffre", "données"}
        if c["content"].startswith("[TABLE]") and any(w in query_text.lower() for w in table_words):
            combined *= 1.15
        c["score"] = round(combined, 4)
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_k]


# ══════════════════════════════════════════════════════
# QUERY — now uses the LLM Factory (provider resolved per space)
# ══════════════════════════════════════════════════════

def query(db: Session, space_id: str, org_id: str, data: QueryRequest, user: User = None) -> dict:
    """Query the RAG space — hybrid search + configurable LLM (via factory).

    Batch 1: enforces per-user access control. ADMIN/IT bypass; a USER must be a
    department member and either unrestricted or in the space's allowed list.
    """
    space = _find_space(db, space_id, org_id)

    # ── Access control (Batch 1) ──
    if user is not None:
        check_space_access(db, space, user)

    query_embedding = embed_query(db, space, data.question)

    top_k = getattr(space, 'top_k', 5) or 5
    results = hybrid_search(db, space_id, data.question, query_embedding, top_k)

    if not results:
        return {"answer": "No relevant information found in the documents.", "sources": []}

    context_parts = []
    sources_info = []
    doc_cache = {}

    for i, r in enumerate(results):
        doc_id = r["document_id"]
        if doc_id not in doc_cache:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            doc_cache[doc_id] = doc.file_name if doc else "Unknown"

        doc_name = doc_cache[doc_id]
        context_parts.append(f"[Source {i+1}: {doc_name}, Page {r['page']}, Score: {r['score']}]\n{r['content']}")
        sources_info.append(f"Source {i+1}: {doc_name} (Page {r['page']}, Score: {r['score']})")

    context = "\n\n---\n\n".join(context_parts)
    sources_text = "\n".join(sources_info)

    # ── LLM Factory: resolves provider/model/key/prompt from the space ──
    answer = generate_answer(db, space, data.question, context, sources_text)

    from urllib.parse import quote

    sources = []
    for r in results:
        src = {
            "content": r["content"][:200],
            "document": doc_cache.get(r["document_id"], "Unknown"),
            "page": r["page"],
            "score": r["score"],
        }
        # Batch 5: if the retrieved chunk is an image, expose it so the chat can
        # render it inline. image_url is relative to the API base; the frontend
        # prepends VITE_API_URL (same pattern as the parsed-document preview).
        if r.get("chunk_type") == "image_summary" and r.get("image_path"):
            src["type"] = "image"
            src["image_url"] = f"/rag/spaces/{space_id}/image?path={quote(r['image_path'])}"
        sources.append(src)

    return {"answer": answer, "sources": sources}