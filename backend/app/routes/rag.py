"""
RAG Routes — updated with professional split flow.

New endpoints:
  GET  /spaces/{id}/documents/{doc_id}/extracted   → see extracted text
  POST /spaces/{id}/documents/{doc_id}/process     → chunk + embed one doc
  POST /spaces/{id}/process-all                    → chunk + embed all EXTRACTED docs
  POST /spaces/{id}/scrape                         → scrape a URL
"""
from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.schemas.rag import CreateRAGSpaceRequest, UpdateRAGSpaceRequest, QueryRequest
from app.services import rag_service
from app.services.auth_service import get_user_id_from_token
from app.models.user import User

router = APIRouter(prefix="/rag", tags=["RAG"])


class ScrapeRequest(BaseModel):
    url: str


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


# ── Spaces ──

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


# ── Documents ──

@router.post("/spaces/{space_id}/upload")
async def upload_document(space_id: str, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload + extract text ONLY. No chunking yet."""
    user = _get_current_user(request, db)
    import traceback
    try:
        return await rag_service.upload_document(db, space_id, user.organization_id, file)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Upload failed: {str(e)}")

@router.post("/spaces/{space_id}/scrape")
async def scrape_url(space_id: str, data: ScrapeRequest, request: Request, db: Session = Depends(get_db)):
    """Scrape a URL and extract text. No chunking yet."""
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


# ── Extracted content (for review) ──

@router.get("/spaces/{space_id}/documents/{doc_id}/extracted")
def get_extracted(space_id: str, doc_id: str, request: Request, db: Session = Depends(get_db)):
    """See the raw extracted text before processing."""
    user = _get_current_user(request, db)
    return rag_service.get_extracted_content(db, space_id, doc_id, user.organization_id)


# ── Process (chunking + embedding) ──

@router.post("/spaces/{space_id}/documents/{doc_id}/process")
def process_document(space_id: str, doc_id: str, request: Request, db: Session = Depends(get_db)):
    """Process one document: chunking + embedding."""
    user = _get_current_user(request, db)
    return rag_service.process_document(db, space_id, doc_id, user.organization_id)

@router.post("/spaces/{space_id}/process-all")
def process_all(space_id: str, request: Request, db: Session = Depends(get_db)):
    """Process ALL extracted documents in this space."""
    user = _get_current_user(request, db)
    return rag_service.process_all_documents(db, space_id, user.organization_id)


# ── Chunks ──

@router.get("/spaces/{space_id}/documents/{doc_id}/chunks")
def get_chunks(space_id: str, doc_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return rag_service.list_chunks(db, space_id, doc_id, user.organization_id)


# ── Query ──

@router.post("/spaces/{space_id}/query")
def query_space(space_id: str, data: QueryRequest, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return rag_service.query(db, space_id, user.organization_id, data)
