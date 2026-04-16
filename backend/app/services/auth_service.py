import random
import string
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Request
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig

from app.models.organization import Organization, OrgType
from app.models.user import User, RoleType
from app.schemas.auth import (
    RegisterRequest, LoginRequest,
    ForgotPasswordRequest, VerifyOtpRequest, ResetPasswordRequest
)
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── OTP store ─────────────────────────────────────────
otp_store: dict = {}

# ── Rate limiting store ───────────────────────────────
# { ip: { "count": int, "first_attempt": datetime, "locked_until": datetime } }
login_attempts: dict = defaultdict(lambda: {"count": 0, "first_attempt": None, "locked_until": None})

MAX_ATTEMPTS  = 5          # max failed attempts
WINDOW_SECS   = 300        # 5 min window
LOCKOUT_SECS  = 900        # 15 min lockout

# ── Mail config ───────────────────────────────────────
mail_conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
)

# ── Password ──────────────────────────────────────────
def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)

# ── JWT ───────────────────────────────────────────────
def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

def get_user_id_from_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# ── Rate limit check ──────────────────────────────────
def check_rate_limit(ip: str):
    now    = datetime.now(timezone.utc)
    record = login_attempts[ip]

    # Still locked out?
    if record["locked_until"] and now < record["locked_until"]:
        remaining = int((record["locked_until"] - now).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {remaining} minute(s)."
        )

    # Reset window if expired
    if record["first_attempt"]:
        elapsed = (now - record["first_attempt"]).total_seconds()
        if elapsed > WINDOW_SECS:
            login_attempts[ip] = {"count": 0, "first_attempt": None, "locked_until": None}

def record_failed_attempt(ip: str):
    now    = datetime.now(timezone.utc)
    record = login_attempts[ip]

    if record["count"] == 0:
        record["first_attempt"] = now

    record["count"] += 1

    if record["count"] >= MAX_ATTEMPTS:
        record["locked_until"] = now + timedelta(seconds=LOCKOUT_SECS)

def reset_attempts(ip: str):
    login_attempts[ip] = {"count": 0, "first_attempt": None, "locked_until": None}

# ── Register ──────────────────────────────────────────
def register(db: Session, data: RegisterRequest) -> dict:
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if data.org_type == OrgType.BUSINESS and not data.org_name:
        raise HTTPException(status_code=400, detail="Organization name required for Business accounts")

    org_name = data.org_name if data.org_type == OrgType.BUSINESS else f"{data.first_name}'s workspace"
    org = Organization(name=org_name, type=data.org_type)
    db.add(org)
    db.flush()

    user = User(
        name=f"{data.first_name} {data.last_name}",
        email=data.email,
        password_hash=hash_password(data.password),
        role=RoleType.ADMIN,
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(org)

    return {
        "access_token": create_access_token(user.id),
        "token_type":   "bearer",
        "user": _user_dict(user, org),
    }

# ── Login (with rate limiting) ────────────────────────
def login(db: Session, data: LoginRequest, client_ip: str) -> dict:

    # 1. Check rate limit before anything
    check_rate_limit(client_ip)

    # 2. Find user
    user = db.query(User).filter(User.email == data.email).first()

    # 3. Verify password
    if not user or not verify_password(data.password, user.password_hash):
        record_failed_attempt(client_ip)

        # Warn user how many attempts remain
        attempts_left = MAX_ATTEMPTS - login_attempts[client_ip]["count"]
        if attempts_left > 0:
            raise HTTPException(
                status_code=401,
                detail=f"Invalid email or password. {attempts_left} attempt(s) remaining."
            )
        else:
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Account temporarily locked for 15 minutes."
            )

    # 4. Success — reset counter
    reset_attempts(client_ip)

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()

    return {
        "access_token": create_access_token(user.id),
        "token_type":   "bearer",
        "user": _user_dict(user, org),
    }

# ── GET /me ───────────────────────────────────────────
def get_me(db: Session, token: str) -> dict:
    user_id = get_user_id_from_token(token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    return _user_dict(user, org)

# ── Forgot Password ───────────────────────────────────
async def forgot_password(db: Session, data: ForgotPasswordRequest) -> dict:
    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        return {"message": "If this email exists, a reset code has been sent"}

    otp = "".join(random.choices(string.digits, k=6))
    otp_store[data.email] = {
        "otp":     otp,
        "expires": datetime.now(timezone.utc) + timedelta(minutes=15),
    }

    message = MessageSchema(
        subject="AgentFlow — Reset your password",
        recipients=[data.email],
        body=f"""
        <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
            <h2 style="color: #0D1F35;">Reset your password</h2>
            <p>Hello {user.name},</p>
            <p>Your password reset code is:</p>
            <div style="background: #EFF6FF; border-radius: 8px; padding: 24px; text-align: center; margin: 24px 0;">
                <span style="font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #2563EB;">{otp}</span>
            </div>
            <p style="color: #64748B; font-size: 14px;">This code expires in 15 minutes.</p>
            <p style="color: #64748B; font-size: 14px;">If you did not request this, ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #E2E8F0; margin: 24px 0;">
            <p style="color: #94A3B8; font-size: 12px;">AgentFlow — A product by Welyne Software Engineering</p>
        </div>
        """,
        subtype="html",
    )

    fm = FastMail(mail_conf)
    await fm.send_message(message)

    return {"message": "If this email exists, a reset code has been sent"}

# ── Verify OTP ────────────────────────────────────────
def verify_otp(data: VerifyOtpRequest) -> dict:
    record = otp_store.get(data.email)

    if not record:
        raise HTTPException(status_code=400, detail="No reset code found for this email")

    if datetime.now(timezone.utc) > record["expires"]:
        del otp_store[data.email]
        raise HTTPException(status_code=400, detail="Reset code has expired")

    if record["otp"] != data.otp:
        raise HTTPException(status_code=400, detail="Invalid reset code")

    return {"message": "Code verified successfully"}

# ── Reset Password ────────────────────────────────────
def reset_password(db: Session, data: ResetPasswordRequest) -> dict:
    record = otp_store.get(data.email)

    if not record:
        raise HTTPException(status_code=400, detail="No reset code found")

    if datetime.now(timezone.utc) > record["expires"]:
        del otp_store[data.email]
        raise HTTPException(status_code=400, detail="Reset code has expired")

    if record["otp"] != data.otp:
        raise HTTPException(status_code=400, detail="Invalid reset code")

    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(data.new_password)
    db.commit()
    del otp_store[data.email]

    return {"message": "Password reset successfully"}

# ── Helper ────────────────────────────────────────────
def _user_dict(user: User, org: Organization | None) -> dict:
    return {
        "id":              user.id,
        "name":            user.name,
        "email":           user.email,
        "role":            user.role,
        "organization_id": user.organization_id,
        "org_type":        org.type if org else None,
        "org_name":        org.name if org else None,
        "created_at":      str(user.created_at),
    }