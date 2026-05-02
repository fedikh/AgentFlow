from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.rag import CreateRAGSpaceRequest, UpdateRAGSpaceRequest, QueryRequest
from app.services import rag_service
from app.services.auth_service import get_user_id_from_token
from app.models.user import User

router = APIRouter(prefix="/rag", tags=["RAG"])

def _get_org_id(request: Request, db: Session) -> str:
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
    return user.organization_id

# Spaces
@router.post("/spaces", status_code=201)
def create_space(data: CreateRAGSpaceRequest, request: Request, db: Session = Depends(get_db)):
    return rag_service.create_space(db, data, _get_org_id(request, db))

@router.get("/spaces")
def list_spaces(request: Request, db: Session = Depends(get_db)):
    return rag_service.list_spaces(db, _get_org_id(request, db))

@router.get("/spaces/{space_id}")
def get_space(space_id: str, request: Request, db: Session = Depends(get_db)):
    return rag_service.get_space(db, space_id, _get_org_id(request, db))

@router.put("/spaces/{space_id}")
def update_space(space_id: str, data: UpdateRAGSpaceRequest, request: Request, db: Session = Depends(get_db)):
    return rag_service.update_space(db, space_id, _get_org_id(request, db), data)

@router.delete("/spaces/{space_id}")
def delete_space(space_id: str, request: Request, db: Session = Depends(get_db)):
    return rag_service.delete_space(db, space_id, _get_org_id(request, db))

# Documents
@router.post("/spaces/{space_id}/upload")
async def upload_document(space_id: str, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    import traceback
    try:
        return await rag_service.upload_document(db, space_id, _get_org_id(request, db), file)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Upload failed: {str(e)}")

@router.get("/spaces/{space_id}/documents")
def list_documents(space_id: str, request: Request, db: Session = Depends(get_db)):
    return rag_service.list_documents(db, space_id, _get_org_id(request, db))

@router.delete("/spaces/{space_id}/documents/{doc_id}")
def delete_document(space_id: str, doc_id: str, request: Request, db: Session = Depends(get_db)):
    return rag_service.delete_document(db, space_id, doc_id, _get_org_id(request, db))

# Query
@router.post("/spaces/{space_id}/query")
def query(space_id: str, data: QueryRequest, request: Request, db: Session = Depends(get_db)):
    import traceback
    try:
        return rag_service.query(db, space_id, _get_org_id(request, db), data)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Query failed: {str(e)}")