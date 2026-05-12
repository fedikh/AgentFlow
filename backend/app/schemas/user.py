"""
User schemas — updated for many-to-many departments.

CHANGES:
- InviteUserRequest: department_id → department_ids (list)
- UpdateUserRoleRequest: department_id → department_ids (list)
"""
from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional


class RoleType(str, Enum):
    IT   = "IT"
    USER = "USER"


# ── Department ────────────────────────────────────────
class CreateDepartmentRequest(BaseModel):
    name: str


# ── Invite ────────────────────────────────────────────
class InviteUserRequest(BaseModel):
    email:          EmailStr
    role:           RoleType
    department_ids: list[str] = []     # CHANGED: list instead of single ID


# ── Activate ──────────────────────────────────────────
class ActivateUserRequest(BaseModel):
    token:    str
    name:     str
    password: str


# ── Update ────────────────────────────────────────────
class UpdateUserRoleRequest(BaseModel):
    role:           Optional[RoleType] = None
    department_ids: Optional[list[str]] = None    # CHANGED: list instead of single ID
