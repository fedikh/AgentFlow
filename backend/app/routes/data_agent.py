"""
Data Agent Routes — Spaces + CSV/Excel queries with LangChain.
Same pattern as RAG: Spaces → Files → Chat
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.services import data_agent_service as svc
from app.services.auth_service import get_user_id_from_token
from app.models.user import User

router = APIRouter(prefix="/data-agent", tags=["Data Agent"])


class CreateSpaceRequest(BaseModel):
    name: str
    description: str = ""
    department_id: str = ""


class QueryRequest(BaseModel):
    question: str

class DatabaseConnectRequest(BaseModel):
    db_type: str = "postgresql"
    host: str = "localhost"
    port: str = "5432"
    database: str = ""
    username: str = ""
    password: str = ""
 
 
class DatabaseQueryRequest(BaseModel):
    question: str
    tables: list = None


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
def create_space(data: CreateSpaceRequest, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.create_space(user, data.name, data.description, data.department_id)


@router.get("/spaces")
def list_spaces(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.list_spaces(user)


@router.delete("/spaces/{space_id}")
def delete_space(space_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.delete_space(user, space_id)


# ── Files ──

@router.post("/spaces/{space_id}/upload")
async def upload_file(space_id: str, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return await svc.upload_file(user, space_id, file)


@router.get("/spaces/{space_id}/files")
def list_files(space_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.list_files(user, space_id)


@router.get("/spaces/{space_id}/files/{file_id}/preview")
def preview_file(space_id: str, file_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.preview_file(user, space_id, file_id)


@router.get("/spaces/{space_id}/files/{file_id}/schema")
def file_schema(space_id: str, file_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.get_schema(user, space_id, file_id)


@router.delete("/spaces/{space_id}/files/{file_id}")
def delete_file(space_id: str, file_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.delete_file(user, space_id, file_id)


# ── Query ──

@router.post("/spaces/{space_id}/query")
def query_data(space_id: str, data: QueryRequest, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.query_data(user, space_id, data.question)

@router.post("/spaces/{space_id}/database/connect")
def connect_database(space_id: str, data: DatabaseConnectRequest, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.connect_database(user, space_id, data.dict())
 
 
@router.get("/spaces/{space_id}/database")
def get_database_info(space_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.get_database_info(user, space_id)
 
 
@router.delete("/spaces/{space_id}/database")
def disconnect_database(space_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.disconnect_database(user, space_id)
 
 
@router.get("/spaces/{space_id}/database/tables/{table_name}/preview")
def table_preview(space_id: str, table_name: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.get_table_preview(user, space_id, table_name)
 
 
@router.get("/spaces/{space_id}/database/tables/{table_name}/schema")
def table_schema(space_id: str, table_name: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.get_table_schema(user, space_id, table_name)
 
 
@router.post("/spaces/{space_id}/database/query")
def query_database(space_id: str, data: DatabaseQueryRequest, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.query_database(user, space_id, data.question, data.tables)

@router.get("/spaces/{space_id}/database/full-schema")
def full_schema(space_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return svc.get_database_schema(user, space_id)