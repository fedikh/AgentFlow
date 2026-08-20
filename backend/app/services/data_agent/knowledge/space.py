"""
The knowledge space — a HIDDEN RAG space that holds the agent's business
documents.

Why: uploading, loading, parsing, chunking, indexing and retrieving
documents is already solved in this platform, once, in
services/providers + services/retrieval. Re-implementing any of it for the
Data Agent would mean two pipelines drifting apart. So a Data Agent's
documents ARE a RAG space — created and owned by the agent, marked
system_kind="data_agent_knowledge" so it never shows up as a RAG space to
anyone, and driven by the exact same endpoints and UI components.

This module only PROVISIONS and keeps that space in sync. Everything else
(upload/parse/chunk/index) goes through rag_service, and retrieval through
services/retrieval.
"""
from __future__ import annotations

import json
import logging

from app.models.rag_space import RAGSpace

logger = logging.getLogger(__name__)

SYSTEM_KIND = "data_agent_knowledge"

# The knowledge space never answers on its own — it is a retrieval index for
# the SQL agent, so the LLM-based query transform (an extra call per
# question) is off and top_k follows the agent's n_business.
_DEFAULT_RETRIEVAL = {"transform_enabled": False}


def _embedding_fields(source) -> dict:
    """The agent's embedding choice, copied verbatim — documents must be
    embedded with the same model as the rest of its knowledge."""
    return {
        "embedding_provider": source.embedding_provider or "LOCAL",
        "embedding_model": source.embedding_model or "BAAI/bge-m3",
        "embedding_provider_id": source.embedding_provider_id,
        "embedding_api_key_enc": source.embedding_api_key_enc,
        "embedding_base_url": source.embedding_base_url,
        "embedding_dim": source.embedding_dim,
    }


def get_space(db, source) -> RAGSpace | None:
    if not source.knowledge_space_id:
        return None
    return (db.query(RAGSpace)
            .filter(RAGSpace.id == source.knowledge_space_id).first())


def ensure_space(db, source) -> RAGSpace:
    """Create the hidden space on first use; keep its models in sync after."""
    space = get_space(db, source)
    if space is None:
        space = RAGSpace(
            name=f"[Data Agent] {source.name}",
            description=f"Knowledge documents of the data agent “{source.name}”",
            status="DRAFT", system_kind=SYSTEM_KIND,
            organization_id=source.organization_id,
            department_id=source.department_id,
            owner_id=source.owner_id,
            is_private=True,
            top_k=8,
            retrieval_params=json.dumps(_DEFAULT_RETRIEVAL),
            **_embedding_fields(source),
        )
        db.add(space)
        db.flush()
        source.knowledge_space_id = space.id
        db.commit()
        db.refresh(space)
        logger.info(f"[DATA-AGENT] knowledge space created for {source.name}")
        return space

    # keep it aligned with the agent (embedding model, department, name)
    changed = False
    for k, v in _embedding_fields(source).items():
        if getattr(space, k, None) != v:
            setattr(space, k, v)
            changed = True
    if space.department_id != source.department_id:
        space.department_id = source.department_id
        changed = True
    expected_name = f"[Data Agent] {source.name}"
    if space.name != expected_name:
        space.name = expected_name
        changed = True
    if changed:
        db.commit()
        db.refresh(space)
    return space


def _purge_files(space_id: str, source_id: str | None = None) -> None:
    """Everything this agent ever wrote to disk: the knowledge space's upload
    folder (uploads/<space_id>) and the legacy uploads/data_agent/<source_id>
    tree from the pre-RAG-space implementation."""
    import os

    from app.services.rag_service import UPLOADS_ROOT, _rmtree_force, _uploads_path

    targets = [_uploads_path(space_id)] if space_id else []
    if source_id:
        targets.append(os.path.join(UPLOADS_ROOT, "data_agent", source_id))
    for path in targets:
        if not os.path.isdir(path):        # rmtree raises on a missing dir
            continue
        _rmtree_force(path)
        if os.path.isdir(path):
            logger.warning(f"[DATA-AGENT] upload folder still present: {path} "
                           "— the startup sweep will retry")
        else:
            logger.info(f"[DATA-AGENT] removed upload folder {path}")


def delete_space(db, source) -> None:
    """Called when the agent is deleted — reuses the RAG deletion so files,
    chunks and vectors are cleaned up by the code that owns them.

    Non-fatal by design: a locked file must not block the agent's deletion.
    Anything left behind is picked up by cleanup_orphan_spaces() at startup,
    the same self-healing contract as the RAG upload sweep.
    """
    space_id, source_id = source.knowledge_space_id, source.id
    if not space_id:
        _purge_files("", source_id)        # legacy tree may still exist
        return
    try:
        space = get_space(db, source)
        if space:
            db.delete(space)               # documents/chunks/vectors cascade
            db.commit()
    except Exception as e:
        # Roll back, or the caller's own commit inherits a poisoned session
        # and the agent itself fails to delete.
        db.rollback()
        logger.warning(f"[DATA-AGENT] knowledge space {space_id} not deleted: {e!r}")
    try:
        _purge_files(space_id, source_id)
    except Exception as e:
        logger.warning(f"[DATA-AGENT] upload cleanup: {e!r}")


def cleanup_orphan_spaces(db) -> int:
    """Startup self-healing, the twin of rag_service.cleanup_orphan_upload_folders:
    drop knowledge spaces whose data agent no longer exists.

    They are invisible in every UI (system_kind), so nothing else would ever
    reclaim them — and while the row lives, the RAG folder sweep considers its
    upload folder legitimate and keeps the files forever.
    """
    import os

    from app.models.data_agent import DataSource
    from app.services.rag_service import UPLOADS_ROOT

    removed = 0
    try:
        live = {sid for (sid,) in db.query(DataSource.knowledge_space_id)
                .filter(DataSource.knowledge_space_id.isnot(None)).all()}
        q = db.query(RAGSpace).filter(RAGSpace.system_kind == SYSTEM_KIND)
        if live:
            q = q.filter(RAGSpace.id.notin_(live))
        orphans = q.all()
        for sp in orphans:
            sid = sp.id
            db.delete(sp)
            db.commit()
            _purge_files(sid)
            removed += 1
            logger.info(f"[DATA-AGENT] removed orphan knowledge space {sid} "
                        f"({sp.name})")
    except Exception as e:
        db.rollback()
        logger.warning(f"[DATA-AGENT] orphan space sweep: {e!r}")

    # legacy uploads/data_agent/<source_id> folders of deleted agents
    try:
        legacy_root = os.path.join(UPLOADS_ROOT, "data_agent")
        if os.path.isdir(legacy_root):
            alive = {s.id for s in db.query(DataSource.id).all()}
            for name in os.listdir(legacy_root):
                if name not in alive and os.path.isdir(os.path.join(legacy_root, name)):
                    _purge_files("", name)
    except Exception as e:
        logger.warning(f"[DATA-AGENT] legacy upload sweep: {e!r}")
    return removed


def stats(db, source) -> dict:
    """Documents + indexed chunks — shown in the Business knowledge panel."""
    from app.models.document import Document
    space = get_space(db, source)
    if not space:
        return {"space_id": None, "documents": 0, "chunks": 0}
    docs = (db.query(Document)
            .filter(Document.rag_space_id == space.id).all())
    return {"space_id": space.id, "documents": len(docs),
            "chunks": sum(d.num_chunks or 0 for d in docs)}
