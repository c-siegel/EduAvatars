"""
User Table

A registered account. Auth is stateless-JWT-based (see app/core/deps.py) rather than a
database-backed session table.

How to use:
    from app.models.user import User

    user = session.get(User, user_id)
"""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """A registered account."""

    # Replaces LocalUser from the source repo; LocalAuthSession is gone (stateless JWT instead
    # of a session table).
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    school: str | None = None
    email: str = Field(unique=True, index=True)
    password_hash: str
    enabled: bool = True
    # Incremented on password change/reset, and on the explicit "sign out everywhere else".
    # Since JWTs are deliberately stateless (no session table, see above), this is the only way
    # to invalidate already-issued tokens early — every token carries the version at issue time
    # as a claim, and get_current_user compares it against the current value.
    token_version: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Profile picture (Screen 1h). avatar_content_type is determined on upload from the actual
    # magic bytes (see api/profile.py), not the file extension — this avoids re-sniffing on every
    # GET. avatar_updated_at is only used for cache-busting the served image URL.
    avatar_path: str | None = None
    avatar_content_type: str | None = None
    avatar_updated_at: datetime | None = None
