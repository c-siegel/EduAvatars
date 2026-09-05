"""
Password Reset Flow

Requesting and completing a password reset: issues a single-use, expiring token (only its hash
is stored) and emails a reset link, then verifies that token and sets the new password.

How to use:
    from app.services.password_reset_service import request_password_reset, reset_password

    request_password_reset(session, email)
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.email_service import send_password_reset_email


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def request_password_reset(session: Session, email: str) -> None:
    """Issue a password-reset token and email the reset link, if an account with `email` exists."""
    # Always responds the same way to the caller (see api/auth.py), whether or not the email
    # exists — this prevents using it to enumerate registered accounts.
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not user.enabled:
        return

    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_token_expire_minutes),
    )
    session.add(reset_token)
    session.commit()

    if not settings.smtp_configured:
        # Local development without a mail server: the token still exists in the DB as normal
        # (e.g. for manual testing), it just isn't emailed, instead of failing with a connection
        # error.
        return

    reset_link = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
    send_password_reset_email(user.email, reset_link)


def reset_password(session: Session, raw_token: str, new_password: str) -> User | None:
    """Complete a password reset: verify the token and set the new password."""
    token_hash = _hash_token(raw_token)
    reset_token = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).first()

    now = datetime.now(timezone.utc)
    if (
        reset_token is None
        or reset_token.used_at is not None
        or reset_token.expires_at.replace(tzinfo=timezone.utc) < now
    ):
        return None

    user = session.get(User, reset_token.user_id)
    if user is None:
        return None

    user.password_hash = hash_password(new_password)
    # Also invalidates all existing sessions — a reset password suggests a compromised account,
    # so old tokens shouldn't just keep working (see token_version).
    user.token_version += 1
    reset_token.used_at = now
    session.add(user)
    session.add(reset_token)
    session.commit()
    return user
