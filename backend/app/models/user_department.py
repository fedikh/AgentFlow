"""
UserDepartment — many-to-many liaison table
Links Users (IT and End User) to multiple Departments.
Admin doesn't use this table — Admin sees everything.
"""
import uuid
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from app.database import Base


class UserDepartment(Base):
    __tablename__ = "user_departments"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id       = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    department_id = Column(String, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "department_id", name="uq_user_department"),
    )
