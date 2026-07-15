from fastapi import APIRouter, Depends, Request, HTTPException, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user import (
    InviteUserRequest, ActivateUserRequest, UpdateUserRoleRequest,
    CreateDepartmentRequest, DeleteUserRequest,
)
from app.services import user_service
from app.services.auth_service import get_user_id_from_token
from app.models.user import User

router = APIRouter(prefix="/users", tags=["Users"])

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

# ══════════════════════════════════════════════════════
# FIXED ROUTES FIRST (before {user_id} catch-all)
# ══════════════════════════════════════════════════════

@router.post("/departments", status_code=201)
def create_department(data: CreateDepartmentRequest, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return user_service.create_department(db, data, user.organization_id)

@router.get("/departments")
def list_departments(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return user_service.list_departments(db, user.organization_id)

@router.delete("/departments/{dept_id}")
def delete_department(dept_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return user_service.delete_department(db, dept_id, user.organization_id)

@router.post("/invite", status_code=201)
async def invite_user(data: InviteUserRequest, request: Request, db: Session = Depends(get_db)):
    admin = _get_current_user(request, db)
    return await user_service.invite_user(db, data, admin)

@router.post("/activate")
def activate_user(data: ActivateUserRequest, db: Session = Depends(get_db)):
    return user_service.activate_user(db, data)

# ══════════════════════════════════════════════════════
# LIST ALL (no path param)
# ══════════════════════════════════════════════════════

@router.get("/")
def list_users(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return user_service.list_users(db, user.organization_id)

# ══════════════════════════════════════════════════════
# DYNAMIC {user_id} ROUTES LAST
# ══════════════════════════════════════════════════════

@router.get("/{user_id}/transfer-info")
def user_transfer_info(user_id: str, request: Request, db: Session = Depends(get_db)):
    """Preview a user's owned RAG spaces + eligible IT targets before deletion."""
    admin = _get_current_user(request, db)
    return user_service.get_user_transfer_info(db, user_id, admin.organization_id, admin)

@router.put("/{user_id}")
def update_user(user_id: str, data: UpdateUserRoleRequest, request: Request, db: Session = Depends(get_db)):
    admin = _get_current_user(request, db)
    return user_service.update_user(db, user_id, admin.organization_id, data, admin)

@router.delete("/{user_id}")
def delete_user(user_id: str, request: Request, db: Session = Depends(get_db),
                data: DeleteUserRequest = Body(default=None)):
    admin = _get_current_user(request, db)
    transfers = data.transfers if data else None
    delete_spaces = bool(data.delete_spaces) if data else False
    return user_service.delete_user(
        db, user_id, admin.organization_id, admin, transfers, delete_spaces
    )

@router.post("/{user_id}/resend")
async def resend_invite(user_id: str, request: Request, db: Session = Depends(get_db)):
    admin = _get_current_user(request, db)
    return await user_service.resend_invite(db, user_id, admin.organization_id, admin)