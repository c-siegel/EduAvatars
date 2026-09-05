"""
Password Reset Token Table

A single-use, expiring token issued when a user requests a password reset — see
app/services/password_reset_service.py.

How to use:
    from app.models.password_reset_token import PasswordResetToken

    token = session.exec(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)).first()
"""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class PasswordResetToken(SQLModel, table=True):
    """A single-use password-reset token, stored only as its hash."""

    # Only the SHA-256 hash of the token is stored (never the plaintext) — the same principle as
    # passwords never being stored in plaintext. The plaintext token only exists in the email
    # link and the short-lived response when it's created, never in the DB. Kept safe by a plain
    # 30-minute validity window plus single use (used_at), instead of risky reusability.
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(index=True, unique=True)
    expires_at: datetime
    used_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
