from pydantic import BaseModel, EmailStr
from enum import Enum

class OrgType(str, Enum):
    PERSONAL = "PERSONAL"
    BUSINESS = "BUSINESS"

class RoleType(str, Enum):
    ADMIN = "ADMIN"
    IT    = "IT"
    USER  = "USER"

# ── Register ──────────────────────────────────────────
class RegisterRequest(BaseModel):
    first_name: str
    last_name:  str
    email:      EmailStr
    password:   str
    org_type:   OrgType
    org_name:   str | None = None

# ── Login ─────────────────────────────────────────────
class LoginRequest(BaseModel):
    email:    EmailStr
    password: str

# ── Forgot Password ───────────────────────────────────
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

# ── Verify OTP ────────────────────────────────────────
class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp:   str

# ── Reset Password ────────────────────────────────────
class ResetPasswordRequest(BaseModel):
    email:        EmailStr
    otp:          str
    new_password: str