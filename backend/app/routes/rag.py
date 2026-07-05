"""
RAG Routes — Ingestion Layer with Loader/Parser split.

Document lifecycle:
  POST   /upload              → LlamaIndex Loader  → status: LOADED
  GET    /documents/{id}/loaded   → raw loaded text review
  POST   /documents/{id}/parse    → LlamaIndex Parser → status: EXTRACTED
  POST   /parse-all               → parse all LOADED docs
  GET    /documents/{id}/extracted → parsed blocks review
  POST   /documents/{id}/process  → chunk + embed   → status: INDEXED
  POST   /process-all             → process all EXTRACTED docs
"""
from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os

from app.database import get_db
from app.schemas.rag import (
    CreateRAGSpaceRequest, UpdateRAGSpaceRequest, QueryRequest, UpdateExtractedRequest
)
from app.services import rag_service
from app.services.auth_service import get_user_id_from_token
from app.models.user import User

router = APIRouter(prefix="/rag", tags=["RAG"])


class ScrapeRequest(BaseModel):
    url: str

class DriveUploadRequest(BaseModel):
    file_id: str
    access_token: str
    file_name: str = ""

class SetStrategyRequest(BaseModel):
    strategy: str   # "FIXED" | "SEMANTIC" | "HIERARCHICAL"

def _get_current_user(request: Request, db: Session) -> User:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            raise HTTPException(401, "Not authenticated")
        token = auth.split(" ")[1]
    user_id = get_user_id_from_token(token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user


# ══════════════════════════════════════════
# SPACES CRUD
# ══════════════════════════════════════════

@router.post("/spaces", status_code=201)
def create_space(data: CreateRAGSpaceRequest, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return rag_service.create_space(db, data, user.organization_id, user)


@router.get("/spaces")
def list_spaces(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return rag_service.list_spaces(db, user.organization_id, user)


@router.get("/spaces/{space_id}")
def get_space(space_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return rag_service.get_space(db, space_id, user.organization_id)


@router.put("/spaces/{space_id}")
def update_space(space_id: str, data: UpdateRAGSpaceRequest, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return rag_service.update_space(db, space_id, user.organization_id, data)


@router.delete("/spaces/{space_id}")
def delete_space(space_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return rag_service.delete_space(db, space_id, user.organization_id)


# ══════════════════════════════════════════
# ACCESS CONTROL (Batch 1) — department user pool
# ══════════════════════════════════════════

@router.get("/departments/{dept_id}/users")
def list_department_users(dept_id: str, request: Request, db: Session = Depends(get_db)):
    """List the USER-role members of a department (pool for 'who can use this space')."""
    user = _get_current_user(request, db)
    return rag_service.list_department_users(db, dept_id, user.organization_id)


# ══════════════════════════════════════════
# DOCUMENTS — Upload / List / Delete
# ══════════════════════════════════════════

@router.post("/spaces/{space_id}/upload")
async def upload_document(
    space_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload file → LlamaIndex Loader → raw text. No parsing yet."""
    user = _get_current_user(request, db)
    return await rag_service.upload_document(db, space_id, user.organization_id, file)


@router.post("/spaces/{space_id}/scrape")
async def scrape_url(space_id: str, data: ScrapeRequest, request: Request, db: Session = Depends(get_db)):
    """Scrape URL → raw text. No parsing yet."""
    user = _get_current_user(request, db)
    return await rag_service.upload_from_url(db, space_id, user.organization_id, data.url)


@router.get("/spaces/{space_id}/documents")
def list_documents(space_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return rag_service.list_documents(db, space_id, user.organization_id)


@router.delete("/spaces/{space_id}/documents/{doc_id}")
def delete_document(space_id: str, doc_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return rag_service.delete_document(db, space_id, doc_id, user.organization_id)

@router.post("/spaces/{space_id}/upload-drive")
async def upload_from_drive(
    space_id: str,
    data: DriveUploadRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Upload a file from Google Drive → same pipeline as local upload."""
    user = _get_current_user(request, db)
    return await rag_service.upload_from_drive(
        db, space_id, user.organization_id,
        data.file_id, data.access_token
    )


# ══════════════════════════════════════════
# PER-DOCUMENT STRATEGY (mode PER_DOCUMENT)
# ══════════════════════════════════════════

@router.put("/spaces/{space_id}/documents/{doc_id}/strategy")
def set_document_strategy(
    space_id: str, doc_id: str, data: SetStrategyRequest,
    request: Request, db: Session = Depends(get_db),
):
    """Set the chunking strategy of a single document (PER_DOCUMENT mode)."""
    user = _get_current_user(request, db)
    return rag_service.set_document_strategy(
        db, space_id, doc_id, data.strategy, user.organization_id
    )


# ══════════════════════════════════════════
# LOADED CONTENT — raw text from Loader
# ══════════════════════════════════════════

@router.get("/spaces/{space_id}/documents/{doc_id}/loaded")
def get_loaded_content(space_id: str, doc_id: str, request: Request, db: Session = Depends(get_db)):
    """Return raw loaded text for IT review."""
    user = _get_current_user(request, db)
    return rag_service.get_loaded_content(db, space_id, doc_id, user.organization_id)


# ══════════════════════════════════════════
# PARSE — Loader → Parser → blocks
# ══════════════════════════════════════════

@router.post("/spaces/{space_id}/documents/{doc_id}/parse")
def parse_document(space_id: str, doc_id: str, request: Request, db: Session = Depends(get_db)):
    """Parse one document: raw text → structured blocks."""
    user = _get_current_user(request, db)
    return rag_service.parse_document(db, space_id, doc_id, user.organization_id)


@router.post("/spaces/{space_id}/parse-all")
def parse_all(space_id: str, request: Request, db: Session = Depends(get_db)):
    """Parse ALL documents with status LOADED."""
    user = _get_current_user(request, db)
    return rag_service.parse_all_documents(db, space_id, user.organization_id)


# ══════════════════════════════════════════
# EXTRACTED CONTENT — parsed blocks
# ══════════════════════════════════════════

@router.get("/spaces/{space_id}/documents/{doc_id}/extracted")
def get_extracted_content(space_id: str, doc_id: str, request: Request, db: Session = Depends(get_db)):
    """Return parsed/structured blocks for IT review."""
    user = _get_current_user(request, db)
    return rag_service.get_extracted_content(db, space_id, doc_id, user.organization_id)

@router.put("/spaces/{space_id}/documents/{doc_id}/extracted")
def update_extracted_content(
    space_id: str, doc_id: str, data: UpdateExtractedRequest,
    request: Request, db: Session = Depends(get_db),
):
    """Save IT's manual edits to the parsed ParsedDocument. Status stays EXTRACTED."""
    user = _get_current_user(request, db)
    return rag_service.update_extracted_content(db, space_id, doc_id, user.organization_id, data)

# ══════════════════════════════════════════
# PROCESS — Chunking + Embedding
# ══════════════════════════════════════════

@router.post("/spaces/{space_id}/documents/{doc_id}/process")
def process_document(space_id: str, doc_id: str, request: Request, db: Session = Depends(get_db)):
    """Process one document: chunking + embedding → pgvector."""
    user = _get_current_user(request, db)
    return rag_service.process_document(db, space_id, doc_id, user.organization_id)


@router.post("/spaces/{space_id}/process-all")
def process_all(space_id: str, request: Request, db: Session = Depends(get_db)):
    """Process ALL documents with status EXTRACTED."""
    user = _get_current_user(request, db)
    return rag_service.process_all_documents(db, space_id, user.organization_id)


# ══════════════════════════════════════════
# CHUNKS + QUERY
# ══════════════════════════════════════════

@router.get("/spaces/{space_id}/documents/{doc_id}/chunks")
def get_chunks(space_id: str, doc_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return rag_service.list_chunks(db, space_id, doc_id, user.organization_id)


@router.post("/spaces/{space_id}/query")
def query_space(space_id: str, data: QueryRequest, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    # Batch 1: pass the user so per-user access control is enforced
    return rag_service.query(db, space_id, user.organization_id, data, user)


@router.post("/spaces/{space_id}/documents/{doc_id}/load-parse")
def load_and_parse(space_id: str, doc_id: str, request: Request, db: Session = Depends(get_db)):
    """Load + Parse a single document (runs loader + cleaner + parser)."""
    user = _get_current_user(request, db)
    return rag_service.load_and_parse_document(db, space_id, doc_id, user.organization_id)


@router.post("/spaces/{space_id}/load-parse-all")
def load_and_parse_all(space_id: str, request: Request, db: Session = Depends(get_db)):
    """Load + Parse ALL documents with status UPLOADING."""
    user = _get_current_user(request, db)
    return rag_service.load_and_parse_all(db, space_id, user.organization_id)

@router.get("/spaces/{space_id}/image")
def serve_image(space_id: str, path: str, db: Session = Depends(get_db)):
    """Serve an extracted image. `path` must be under uploads/{space_id}."""
    safe_root = os.path.abspath(os.path.join("uploads", space_id))
    full = os.path.abspath(path)
    if not full.startswith(safe_root):
        raise HTTPException(403, "Forbidden path")
    if not os.path.exists(full):
        raise HTTPException(404, "Image not found")
    return FileResponse(full)