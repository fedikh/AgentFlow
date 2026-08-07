"""Dashboard routes — read-only aggregates, one payload per role."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.routes.rag import _get_current_user
from app.services import dashboard

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _role(user) -> str:
    r = str(getattr(user, "role", "") or "")
    return r.split(".")[-1] if "." in r else r


@router.get("/it")
def it_dashboard(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if _role(user) not in ("IT", "ADMIN"):
        raise HTTPException(403, "IT dashboard is for IT members")
    return dashboard.it_dashboard(db, user)


@router.get("/user")
def user_dashboard(request: Request, db: Session = Depends(get_db)):
    """Any authenticated user — personal stats + accessible agents only."""
    user = _get_current_user(request, db)
    return dashboard.user_dashboard(db, user)


@router.get("/admin")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    if _role(user) != "ADMIN":
        raise HTTPException(403, "Admin dashboard is for admins")
    return dashboard.admin_dashboard(db, user)
