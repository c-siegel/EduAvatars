"""
Admin Request/Response Shapes

The request/response shapes for app/api/admin.py: managing other users' accounts from the admin
dashboard.

How to use:
    from app.models.schemas.admin import AdminUserOut
"""

from datetime import datetime

from pydantic import EmailStr, field_validator

from app.core.schema import CamelModel
from app.models.schemas.auth import _validate_password_strength


class AdminUserOut(CamelModel):
    id: str
    name: str
    email: str
    school: str | None
    is_admin: bool
    enabled: bool
    # Shown so the admin can see who still hasn't changed a password that was set for them (see
    # User.must_change_password).
    must_change_password: bool
    created_at: datetime


class AdminUserCreate(CamelModel):
    name: str
    email: EmailStr
    password: str
    is_admin: bool = False

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class AdminPasswordReset(CamelModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class AdminUserUpdate(CamelModel):
    is_admin: bool | None = None
    enabled: bool | None = None
