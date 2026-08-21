"""
Auth Request/Response Shapes

The request/response shapes for app/api/auth.py, plus the shared password-strength check used
by both registration and password reset/change (see also schemas/profile.py).

How to use:
    from app.models.schemas.auth import LoginRequest
"""

import re

from pydantic import EmailStr, field_validator

from app.core.error_codes import ErrorCode
from app.core.schema import CamelModel

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_BYTES = 72  # bcrypt's limit — above this, bcrypt raises an error instead of truncating


def _validate_password_strength(password: str) -> str:
    """Enforce "at least 10 characters, one digit", raising ValueError if the password is too weak."""
    # Same rule as changing a password in the profile (Screen 1h: "Min. 10 characters, one
    # digit") — previously only checked client-side, now also enforced server-side on
    # registration (Phase 2.1, a safety net in case the client doesn't check, e.g. direct API calls).
    if len(password) < MIN_PASSWORD_LENGTH or not re.search(r"\d", password):
        raise ValueError(ErrorCode.PASSWORD_TOO_SHORT)
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(ErrorCode.PASSWORD_TOO_LONG)
    return password


class LoginRequest(CamelModel):
    email: EmailStr
    password: str


class RegisterRequest(CamelModel):
    name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class UserOut(CamelModel):
    id: str
    name: str
    school: str | None
    email: str
    avatar_url: str | None = None


class RegistrationStatusOut(CamelModel):
    enabled: bool


class ForgotPasswordRequest(CamelModel):
    email: EmailStr


class ResetPasswordRequest(CamelModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password_strength(value)
