"""
Profile Request Shapes

The request shapes for app/api/profile.py: editable profile fields and a password change.

How to use:
    from app.models.schemas.profile import ProfileUpdate
"""

from pydantic import EmailStr, field_validator

from app.core.schema import CamelModel
from app.models.schemas.auth import _validate_password_strength


class ProfileUpdate(CamelModel):
    name: str | None = None
    school: str | None = None
    email: EmailStr | None = None


class PasswordChange(CamelModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password_strength(value)
