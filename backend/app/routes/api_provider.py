"""
API Provider routes — admin manages company providers.
Adds GET /providers/{id}/models so the IT can list a provider's models.
"""
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import api_provider_service
from app.services.auth_service import get_user_id_from_token
from app.models.user import User
from app.schemas.api_provider import CreateProviderRequest, UpdateProviderRequest

router = APIRouter(prefix="/providers", tags=["API Providers"])

COOKIE_NAME = "access_token"


def _current_user(request: Request, db: Session) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Not authenticated")
        token = authorization.split(" ")[1]
    user_id = get_user_id_from_token(token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user


@router.get("")
def list_providers(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    return api_provider_service.list_providers(db, user.organization_id)


@router.post("", status_code=201)
def create_provider(data: CreateProviderRequest, request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    return api_provider_service.create_provider(db, user.organization_id, data, user)


@router.put("/{provider_id}")
def update_provider(provider_id: str, data: UpdateProviderRequest, request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    return api_provider_service.update_provider(db, user.organization_id, provider_id, data, user)


@router.delete("/{provider_id}")
def delete_provider(provider_id: str, request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    return api_provider_service.delete_provider(db, user.organization_id, provider_id, user)


@router.get("/{provider_id}/models")
def provider_models(provider_id: str, request: Request, kind: str = None, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    return api_provider_service.get_provider_models(db, user.organization_id, provider_id, kind)