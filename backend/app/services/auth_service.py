"""
Authentication Helpers

Shared logic behind the auth routes (app/api/auth.py) and anywhere else a User needs to become
an authenticated session or an API response: registering/authenticating a user, converting a
User to its public UserOut shape, and issuing the signed auth cookie.

How to use:
    from app.services.auth_service import authenticate_user, set_auth_cookie

    user = authenticate_user(session, email, password)
    if user:
        set_auth_cookie(response, user)
"""

from fastapi import Response
from sqlmodel import Session, select

from app.core.config import settings
from app.core.deps import ACCESS_TOKEN_COOKIE
from app.core.security import create_access_token, hash_password, verify_password
from app.models.schemas.auth import UserOut
from app.models.user import User


def register_user(session: Session, name: str, email: str, password: str) -> User:
    """Create a new user with a hashed password."""
    user = User(name=name, email=email, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    """Verify email + password, returning the User on success or None otherwise."""
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def user_to_out(user: User) -> UserOut:
    """Convert a User to its public UserOut shape."""
    # avatarUrl isn't a DB column, it's derived from avatar_path/avatar_updated_at — that's why
    # every route returning a user builds it explicitly through this helper, instead of just
    # passing the SQLModel object straight through as the response_model.
    avatar_url = None
    if user.avatar_path and user.avatar_updated_at:
        avatar_url = f"/profile/picture?v={int(user.avatar_updated_at.timestamp())}"
    return UserOut(
        id=user.id,
        name=user.name,
        school=user.school,
        email=user.email,
        avatar_url=avatar_url,
    )


def issue_token_for(user: User) -> str:
    """Issue a signed JWT (JSON Web Token) for this user."""
    return create_access_token(user.id, user.token_version)


def set_auth_cookie(response: Response, user: User) -> None:
    """Issue a fresh auth token for `user` and set it as the response's httponly cookie."""
    token = issue_token_for(user)
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
