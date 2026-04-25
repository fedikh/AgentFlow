import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException
from fastapi_mail import FastMail, MessageSchema

from app.models.user import User, RoleType, UserStatus
from app.models.organization import Organization, OrgType
from app.models.department import Department
from app.schemas.user import (
    InviteUserRequest, ActivateUserRequest, UpdateUserRoleRequest,
    CreateDepartmentRequest
)
from app.services.auth_service import hash_password, mail_conf

# ══════════════════════════════════════════════════════
# DEPARTMENTS
# ══════════════════════════════════════════════════════

def create_department(db: Session, data: CreateDepartmentRequest, org_id: str) -> dict:
    existing = db.query(Department).filter(
        Department.name == data.name, Department.organization_id == org_id
    ).first()
    if existing:
        raise HTTPException(400, f"Department '{data.name}' already exists")

    dept = Department(name=data.name, organization_id=org_id)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return _dept_dict(dept, db)

def list_departments(db: Session, org_id: str) -> list[dict]:
    depts = db.query(Department).filter(Department.organization_id == org_id).all()
    return [_dept_dict(d, db) for d in depts]

def delete_department(db: Session, dept_id: str, org_id: str) -> dict:
    dept = db.query(Department).filter(Department.id == dept_id, Department.organization_id == org_id).first()
    if not dept:
        raise HTTPException(404, "Department not found")
    db.query(User).filter(User.department_id == dept_id).update({"department_id": None})
    db.delete(dept)
    db.commit()
    return {"message": f"Department '{dept.name}' deleted"}



# ══════════════════════════════════════════════════════
# INVITE
# ══════════════════════════════════════════════════════

async def invite_user(db: Session, data: InviteUserRequest, admin_user: User) -> dict:
    if admin_user.role != RoleType.ADMIN:
        raise HTTPException(403, "Only Admin can invite users")

    org = db.query(Organization).filter(Organization.id == admin_user.organization_id).first()
    if org and org.type == OrgType.PERSONAL:
        raise HTTPException(403, "Personal accounts cannot invite members")

    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(400, "This email is already registered")

    # IT users don't belong to departments
    dept_id = None
    if data.role == "IT":
        dept_id = None  # IT has no department
    elif data.department_id:
        dept_id = data.department_id
        dept = db.query(Department).filter(
            Department.id == dept_id, Department.organization_id == admin_user.organization_id
        ).first()
        if not dept:
            raise HTTPException(404, "Department not found")

    invite_token = str(uuid.uuid4())

    user = User(
        email=data.email,
        role=data.role,
        status=UserStatus.PENDING,
        invite_token=invite_token,
        organization_id=admin_user.organization_id,
        department_id=dept_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Get dept name for email
    dept_name = None
    if dept_id:
        dept = db.query(Department).filter(Department.id == dept_id).first()
        dept_name = dept.name if dept else None

    activate_url = f"http://localhost:5173/activate?token={invite_token}"
    dept_text = f" in the <strong>{dept_name}</strong> department" if dept_name else ""

    message = MessageSchema(
        subject="AgentFlow — You've been invited!",
        recipients=[data.email],
        body=f"""
        <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
            <h2 style="color: #0D1F35;">You've been invited to AgentFlow</h2>
            <p><strong>{admin_user.name}</strong> has invited you to join 
               <strong>{org.name}</strong> as <strong>{data.role.value}</strong>{dept_text}.</p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{activate_url}" 
                   style="background: #2563EB; color: #fff; padding: 14px 32px; 
                          border-radius: 8px; text-decoration: none; font-weight: 700;">
                    Activate my account
                </a>
            </div>
            <p style="color: #64748B; font-size: 14px;">If you didn't expect this, ignore this email.</p>
        </div>
        """,
        subtype="html",
    )
    fm = FastMail(mail_conf)
    await fm.send_message(message)

    return _user_dict(user, db)

# ══════════════════════════════════════════════════════
# ACTIVATE
# ══════════════════════════════════════════════════════

def activate_user(db: Session, data: ActivateUserRequest) -> dict:
    user = db.query(User).filter(User.invite_token == data.token).first()
    if not user:
        raise HTTPException(400, "Invalid or expired invitation link")
    if user.status != UserStatus.PENDING:
        raise HTTPException(400, "Account already activated")
    if len(data.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    user.name = data.name
    user.password_hash = hash_password(data.password)
    user.status = UserStatus.ACTIVE
    user.invite_token = None
    db.commit()

    return {
        "message": "Account activated successfully. You can now log in.",
        "role": user.role,    # frontend needs this to show correct message
    }

# ══════════════════════════════════════════════════════
# LIST / UPDATE / DELETE
# ══════════════════════════════════════════════════════

def list_users(db: Session, org_id: str) -> list[dict]:
    users = db.query(User).filter(User.organization_id == org_id).all()
    return [_user_dict(u, db) for u in users]

def update_user(db: Session, user_id: str, org_id: str, data: UpdateUserRoleRequest, admin_user: User) -> dict:
    if admin_user.role != RoleType.ADMIN:
        raise HTTPException(403, "Only Admin can update users")

    user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin_user.id:
        raise HTTPException(400, "Cannot change your own settings")
    if user.role == RoleType.ADMIN:
        raise HTTPException(400, "Cannot modify another Admin")

    if data.role is not None:
        user.role = data.role
        # If changed to IT → remove from department
        if data.role == "IT":
            user.department_id = None

    if data.department_id is not None:
        if data.department_id == "":
            user.department_id = None
        else:
            dept = db.query(Department).filter(Department.id == data.department_id, Department.organization_id == org_id).first()
            if not dept:
                raise HTTPException(404, "Department not found")
            user.department_id = data.department_id

    db.commit()
    db.refresh(user)
    return _user_dict(user, db)

def delete_user(db: Session, user_id: str, org_id: str, admin_user: User) -> dict:
    if admin_user.role != RoleType.ADMIN:
        raise HTTPException(403, "Only Admin can delete users")
    user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin_user.id:
        raise HTTPException(400, "Cannot delete yourself")
    if user.role == RoleType.ADMIN:
        raise HTTPException(400, "Cannot delete another Admin")

    name = user.name or user.email
    db.delete(user)
    db.commit()
    return {"message": f"User '{name}' removed"}

async def resend_invite(db: Session, user_id: str, org_id: str, admin_user: User) -> dict:
    if admin_user.role != RoleType.ADMIN:
        raise HTTPException(403, "Only Admin can resend invitations")
    user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.status != UserStatus.PENDING:
        raise HTTPException(400, "User already activated")

    user.invite_token = str(uuid.uuid4())
    db.commit()

    org = db.query(Organization).filter(Organization.id == org_id).first()
    activate_url = f"http://localhost:5173/activate?token={user.invite_token}"
    message = MessageSchema(
        subject="AgentFlow — Invitation reminder",
        recipients=[user.email],
        body=f"""<div style="font-family:Arial;max-width:480px;margin:0 auto;">
            <h2 style="color:#0D1F35;">Reminder: You've been invited!</h2>
            <p><strong>{admin_user.name}</strong> is waiting for you on <strong>{org.name if org else 'AgentFlow'}</strong>.</p>
            <div style="text-align:center;margin:32px 0;">
                <a href="{activate_url}" style="background:#2563EB;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:700;">Activate</a>
            </div></div>""",
        subtype="html",
    )
    fm = FastMail(mail_conf)
    await fm.send_message(message)
    return {"message": f"Invitation resent to {user.email}"}

# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def _user_dict(user: User, db: Session = None) -> dict:
    dept_name = None
    if user.department_id and db:
        dept = db.query(Department).filter(Department.id == user.department_id).first()
        dept_name = dept.name if dept else None

    return {
        "id":              user.id,
        "name":            user.name,
        "email":           user.email,
        "role":            user.role,
        "status":          user.status,
        "department_id":   user.department_id,
        "department_name": dept_name,
        "organization_id": user.organization_id,
        "created_at":      str(user.created_at),
    }

def _dept_dict(dept: Department, db: Session = None) -> dict:
    member_count = 0
    if db:
        member_count = db.query(User).filter(User.department_id == dept.id).count()
    return {
        "id":              dept.id,
        "name":            dept.name,
        "member_count":    member_count,
        "organization_id": dept.organization_id,
        "created_at":      str(dept.created_at),
    }