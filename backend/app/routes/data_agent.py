"""
Data Agent routes — two routers, mounted under /api in main.py.

    /data-sources   the agent itself: connection, models, schema, training,
                    documents, authorization, lifecycle  (owner/admin)
    /data-agent     consumption: ask, execute an edited SQL, sessions
                    (any authorized user)

Auth is the platform JWT (_get_current_user). Management is owner-or-admin
(sources.require_manager); consumption goes through
orchestrator.check_source_access. Secrets are write-only: encrypted on the
way in, never returned.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.routes.rag import _get_current_user
from app.services.data_agent import jobs, sources

router = APIRouter(prefix="/data-sources", tags=["Data Agent"])
ask_router = APIRouter(prefix="/data-agent", tags=["Data Agent"])


# ══════════════════════════════════════════════════════════════
#  Schemas
# ══════════════════════════════════════════════════════════════

class CreateSourceRequest(BaseModel):
    name: str
    description: Optional[str] = None
    department_id: Optional[str] = None
    is_private: Optional[bool] = True
    dialect: str = "postgres"
    host: Optional[str] = ""
    port: Optional[int] = None
    database: Optional[str] = ""
    username: Optional[str] = ""
    password: Optional[str] = None
    extra_params: Optional[dict] = None
    schema_whitelist: Optional[list] = None


class UpdateSourceRequest(BaseModel):
    # identity & access
    name: Optional[str] = None
    description: Optional[str] = None
    department_id: Optional[str] = None
    is_private: Optional[bool] = None
    # connection
    dialect: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None            # write-only
    extra_params: Optional[dict] = None
    schema_whitelist: Optional[list] = None
    # execution safety
    row_limit: Optional[int] = None
    timeout_ms: Optional[int] = None
    mode_override: Optional[str] = None
    send_results_to_llm: Optional[bool] = None
    # generation
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_provider_id: Optional[str] = None
    llm_api_key: Optional[str] = None         # write-only
    llm_base_url: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    prompt_mode: Optional[str] = None         # default | custom
    system_prompt: Optional[str] = None
    # embedding
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_provider_id: Optional[str] = None
    embedding_api_key: Optional[str] = None   # write-only
    embedding_base_url: Optional[str] = None
    # JSON configs
    retrieval_params: Optional[dict] = None
    chunk_params: Optional[dict] = None


class AuthorizationRequest(BaseModel):
    user_ids: list = []


class UpdateTableRequest(BaseModel):
    description: Optional[str] = None
    is_enabled: Optional[bool] = None


class GlossaryRequest(BaseModel):
    term: str
    definition: str


class ExampleRequest(BaseModel):
    question: str
    sql: str
    is_verified: Optional[bool] = False


class AskRequest(BaseModel):
    question: str
    data_source_id: str
    session_id: Optional[str] = None


class ExecuteRequest(BaseModel):
    data_source_id: str
    sql: str


# ══════════════════════════════════════════════════════════════
#  Sources — CRUD, connection, lifecycle
# ══════════════════════════════════════════════════════════════

# ── STATIC paths first: FastAPI matches in definition order, so anything
#    declared after /{source_id} would be swallowed by it ──

@router.get("/dialects")
def list_dialects(request: Request, db: Session = Depends(get_db)):
    _get_current_user(request, db)
    return sources.dialects()


@router.get("/chunking-catalog")
def chunking_catalog(request: Request, file_type: str = None,
                     db: Session = Depends(get_db)):
    """The SAME per-format strategy catalog as the RAG spaces."""
    from app.services.providers.chunking_factory import catalog_for
    _get_current_user(request, db)
    return catalog_for(file_type)


@router.get("/csv-template/{kind}")
def csv_template(kind: str, request: Request, db: Session = Depends(get_db)):
    """A ready-to-fill CSV for the bulk imports below."""
    from fastapi.responses import PlainTextResponse

    from app.services.data_agent.knowledge import TEMPLATES
    _get_current_user(request, db)
    if kind not in TEMPLATES:
        raise HTTPException(404, "Unknown template")
    return PlainTextResponse(
        TEMPLATES[kind], media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})


@router.get("/jobs/{job_id}")
def job_status(job_id: str, request: Request, db: Session = Depends(get_db)):
    _get_current_user(request, db)
    return jobs.job_status(job_id)


@router.get("")
def list_sources(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return sources.list_sources(db, user)


@router.post("", status_code=201)
def create_source(data: CreateSourceRequest, request: Request,
                  db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return sources.create_source(db, user, data.model_dump(exclude_none=True))


@router.get("/{source_id}")
def get_source(source_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    s = sources.find_source(db, source_id, user.organization_id)
    return sources.source_dict(db, s)


@router.patch("/{source_id}")
def update_source(source_id: str, data: UpdateSourceRequest, request: Request,
                  db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return sources.update_source(db, source_id, user,
                                 data.model_dump(exclude_none=True))


@router.delete("/{source_id}")
def delete_source(source_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return sources.delete_source(db, source_id, user)


@router.post("/{source_id}/test")
def test_connection(source_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return sources.test_connection(db, source_id, user)


@router.put("/{source_id}/authorization")
def set_authorization(source_id: str, data: AuthorizationRequest,
                      request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return sources.set_authorization(db, source_id, user, data.user_ids)


@router.post("/{source_id}/deploy")
def deploy(source_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return sources.deploy_source(db, source_id, user)


@router.post("/{source_id}/pause")
def pause(source_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return sources.pause_source(db, source_id, user)


# ══════════════════════════════════════════════════════════════
#  Schema & training
# ══════════════════════════════════════════════════════════════

@router.post("/{source_id}/introspect")
def introspect(source_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    sources.require_manager(db, source_id, user.organization_id, user)
    from app.services.data_agent.knowledge import start_introspection
    return start_introspection(source_id)


@router.post("/{source_id}/index")
def train(source_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    sources.require_manager(db, source_id, user.organization_id, user)
    from app.services.data_agent.vanna import start_training
    return start_training(source_id)


@router.get("/{source_id}/schema")
def get_schema(source_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    sources.require_manager(db, source_id, user.organization_id, user)
    from app.services.data_agent.knowledge import schema_payload
    return schema_payload(db, source_id)


@router.patch("/{source_id}/tables/{table_id}")
def update_table(source_id: str, table_id: str, data: UpdateTableRequest,
                 request: Request, db: Session = Depends(get_db)):
    from app.models.data_agent import DataSourceTable
    user = _get_current_user(request, db)
    source = sources.require_manager(db, source_id, user.organization_id, user)
    t = (db.query(DataSourceTable)
         .filter(DataSourceTable.id == table_id,
                 DataSourceTable.data_source_id == source_id).first())
    if not t:
        raise HTTPException(404, "Table not found")
    if data.description is not None:
        t.description = data.description
    if data.is_enabled is not None:
        t.is_enabled = data.is_enabled
    if source.status in ("trained", "deployed"):
        source.status = "stale"              # curation changed → re-train
    db.commit()
    return {"ok": True, "source_status": source.status}


@router.get("/{source_id}/knowledge")
def knowledge_stats(source_id: str, request: Request, db: Session = Depends(get_db)):
    """How much is indexed per knowledge index (DDLs / SQL pairs / Business)."""
    user = _get_current_user(request, db)
    source = sources.require_manager(db, source_id, user.organization_id, user)
    from app.services.data_agent.retrieval import count_by_kind
    try:
        return count_by_kind(db, source)
    except Exception:
        return {"ddl": 0, "sql": 0, "business": 0}


# ══════════════════════════════════════════════════════════════
#  Business knowledge — glossary, examples, documents
# ══════════════════════════════════════════════════════════════

@router.get("/{source_id}/glossary")
def list_glossary(source_id: str, request: Request, db: Session = Depends(get_db)):
    from app.models.data_agent import DataSourceGlossary
    user = _get_current_user(request, db)
    sources.require_manager(db, source_id, user.organization_id, user)
    rows = (db.query(DataSourceGlossary)
            .filter(DataSourceGlossary.data_source_id == source_id)
            .order_by(DataSourceGlossary.term).all())
    return [{"id": g.id, "term": g.term, "definition": g.definition} for g in rows]


@router.post("/{source_id}/glossary", status_code=201)
def add_glossary(source_id: str, data: GlossaryRequest, request: Request,
                 db: Session = Depends(get_db)):
    from app.models.data_agent import DataSourceGlossary
    user = _get_current_user(request, db)
    source = sources.require_manager(db, source_id, user.organization_id, user)
    g = DataSourceGlossary(data_source_id=source_id, term=data.term.strip(),
                           definition=data.definition.strip())
    db.add(g)
    if source.status in ("trained", "deployed"):
        source.status = "stale"
    db.commit()
    return {"id": g.id, "term": g.term, "definition": g.definition}


@router.delete("/{source_id}/glossary/{term_id}")
def delete_glossary(source_id: str, term_id: str, request: Request,
                    db: Session = Depends(get_db)):
    from app.models.data_agent import DataSourceGlossary
    user = _get_current_user(request, db)
    sources.require_manager(db, source_id, user.organization_id, user)
    db.query(DataSourceGlossary).filter(
        DataSourceGlossary.id == term_id,
        DataSourceGlossary.data_source_id == source_id).delete()
    db.commit()
    return {"deleted": True}


@router.get("/{source_id}/examples")
def list_examples(source_id: str, request: Request, db: Session = Depends(get_db)):
    from app.models.data_agent import DataSourceExample
    user = _get_current_user(request, db)
    sources.require_manager(db, source_id, user.organization_id, user)
    rows = (db.query(DataSourceExample)
            .filter(DataSourceExample.data_source_id == source_id)
            .order_by(DataSourceExample.created_at.desc()).all())
    return [{"id": e.id, "question": e.question, "sql": e.sql,
             "is_verified": bool(e.is_verified)} for e in rows]


@router.post("/{source_id}/examples", status_code=201)
def add_example(source_id: str, data: ExampleRequest, request: Request,
                db: Session = Depends(get_db)):
    from app.models.data_agent import DataSourceExample
    user = _get_current_user(request, db)
    source = sources.require_manager(db, source_id, user.organization_id, user)
    e = DataSourceExample(data_source_id=source_id, question=data.question.strip(),
                          sql=data.sql.strip(), is_verified=bool(data.is_verified),
                          created_by=user.id)
    db.add(e)
    if data.is_verified and source.status in ("trained", "deployed"):
        source.status = "stale"
    db.commit()
    return {"id": e.id, "question": e.question, "sql": e.sql,
            "is_verified": bool(e.is_verified)}


@router.post("/{source_id}/examples/{example_id}/verify")
def verify_example(source_id: str, example_id: str, request: Request,
                   db: Session = Depends(get_db)):
    """Only VERIFIED pairs are ever trained — this is the human gate."""
    from app.models.data_agent import DataSourceExample
    user = _get_current_user(request, db)
    source = sources.require_manager(db, source_id, user.organization_id, user)
    e = (db.query(DataSourceExample)
         .filter(DataSourceExample.id == example_id,
                 DataSourceExample.data_source_id == source_id).first())
    if not e:
        raise HTTPException(404, "Example not found")
    e.is_verified = not e.is_verified
    if source.status in ("trained", "deployed"):
        source.status = "stale"
    db.commit()
    return {"id": e.id, "is_verified": bool(e.is_verified)}


@router.delete("/{source_id}/examples/{example_id}")
def delete_example(source_id: str, example_id: str, request: Request,
                   db: Session = Depends(get_db)):
    from app.models.data_agent import DataSourceExample
    user = _get_current_user(request, db)
    sources.require_manager(db, source_id, user.organization_id, user)
    db.query(DataSourceExample).filter(
        DataSourceExample.id == example_id,
        DataSourceExample.data_source_id == source_id).delete()
    db.commit()
    return {"deleted": True}


@router.post("/{source_id}/examples/import")
async def import_examples(source_id: str, request: Request,
                          db: Session = Depends(get_db)):
    """CSV → prompt→SQL pairs (question,sql[,verified])."""
    user = _get_current_user(request, db)
    source = sources.require_manager(db, source_id, user.organization_id, user)
    form = await request.form()
    up = form.get("file")
    if up is None:
        raise HTTPException(400, "No file")
    from app.services.data_agent.knowledge import import_examples as imp
    return imp(db, source, await up.read(), user.id)


@router.post("/{source_id}/glossary/import")
async def import_glossary(source_id: str, request: Request,
                          db: Session = Depends(get_db)):
    """CSV → glossary (term,definition)."""
    user = _get_current_user(request, db)
    source = sources.require_manager(db, source_id, user.organization_id, user)
    form = await request.form()
    up = form.get("file")
    if up is None:
        raise HTTPException(400, "No file")
    from app.services.data_agent.knowledge import import_glossary as imp
    return imp(db, source, await up.read())


# ── knowledge documents ───────────────────────────────────────
# There are no document endpoints here BY DESIGN: an agent's documents live
# in a hidden RAG space, so the frontend drives them with the existing
# /rag/spaces/{id}/... endpoints (upload · load-parse · extracted · process ·
# chunks). This endpoint just provisions that space and returns its id.

@router.post("/{source_id}/knowledge-space")
def knowledge_space(source_id: str, request: Request,
                    db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    source = sources.require_manager(db, source_id, user.organization_id, user)
    from app.services.data_agent.knowledge import ensure_space, stats
    ensure_space(db, source)
    return stats(db, source)


# ══════════════════════════════════════════════════════════════
#  Consumption — ask / execute / sessions
# ══════════════════════════════════════════════════════════════

@ask_router.post("/ask")
def ask(data: AskRequest, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    from app.services.data_agent import orchestrator
    return orchestrator.ask(db, user, data.data_source_id, data.question,
                            data.session_id)


@ask_router.post("/execute")
def execute(data: ExecuteRequest, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    from app.services.data_agent import orchestrator
    return orchestrator.execute_edited(db, user, data.data_source_id, data.sql)


@ask_router.get("/sessions")
def list_sessions(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    from app.services.data_agent import orchestrator
    return orchestrator.list_sessions(db, user)


@ask_router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    from app.services.data_agent import orchestrator
    return orchestrator.get_session(db, user, session_id)


@ask_router.delete("/sessions/{session_id}")
def delete_session(session_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    from app.services.data_agent import orchestrator
    return orchestrator.delete_session(db, user, session_id)
