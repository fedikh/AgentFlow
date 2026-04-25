from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional

class RoleType(str, Enum):
    IT   = "IT"
    USER = "USER"

# ── Department ────────────────────────────────────────
class CreateDepartmentRequest(BaseModel):
    name: str                              # Commerce, RH, Finance...

# ── Invite ────────────────────────────────────────────
class InviteUserRequest(BaseModel):
    email:         EmailStr
    role:          RoleType
    department_id: Optional[str] = None    # optional — Admin picks from list

# ── Activate ──────────────────────────────────────────
class ActivateUserRequest(BaseModel):
    token:    str
    name:     str
    password: str

# ── Update ────────────────────────────────────────────
class UpdateUserRoleRequest(BaseModel):
    role:          Optional[RoleType] = None
    department_id: Optional[str]      = None