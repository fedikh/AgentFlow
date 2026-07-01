from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import (
        RegisterRequest, LoginRequest,
        ForgotPasswordRequest, VerifyOtpRequest, ResetPasswordRequest,
        UpdateProfileRequest, UpdatePasswordRequest, UpdateOrganizationRequest,
    )
from app.services import auth_service
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])

COOKIE_NAME = "access_token"

def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,                        # JS cannot read it
        secure=True,                          # HTTPS only in production
        samesite="lax",                       # CSRF protection
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

def _get_token(request: Request) -> str:
    """Extract the JWT from cookie first, then Authorization header."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Not authenticated")
        token = authorization.split(" ")[1]
    return token

@router.post("/register", status_code=201)
def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    result = auth_service.register(db, data)
    set_auth_cookie(response, result["access_token"])
    return result

@router.post("/login")
def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    client_ip = request.client.host
    result = auth_service.login(db, data, client_ip)
    set_auth_cookie(response, result["access_token"])
    return result

@router.post("/logout", status_code=200)
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, httponly=True, secure=True, samesite="lax")
    return {"message": "Logged out successfully"}

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return await auth_service.forgot_password(db, data)

@router.post("/verify-otp")
def verify_otp(data: VerifyOtpRequest):
    return auth_service.verify_otp(data)

@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    return auth_service.reset_password(db, data)

@router.get("/me")
def get_me(request: Request, db: Session = Depends(get_db)):
    token = _get_token(request)
    return auth_service.get_me(db, token)

@router.put("/me")
def update_me(data: UpdateProfileRequest, request: Request, db: Session = Depends(get_db)):
    """Update the current user's profile (name)."""
    token = _get_token(request)
    return auth_service.update_profile(db, token, data)

@router.put("/me/password")
def update_my_password(data: UpdatePasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Change the current user's password (verifies the current one)."""
    token = _get_token(request)
    return auth_service.update_password(db, token, data)

@router.put("/organization")
def update_org(data: UpdateOrganizationRequest, request: Request, db: Session = Depends(get_db)):
    """Update the organization name (ADMIN only)."""
    token = _get_token(request)
    return auth_service.update_organization(db, token, data)

