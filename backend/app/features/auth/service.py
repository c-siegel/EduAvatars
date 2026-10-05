"""
Authentication Helpers

Shared logic behind the auth routes (app/features/auth/router.py) and anywhere else a User needs to become
an authenticated session or an API response: registering/authenticating a user, converting a
User to its public UserOut shape. The auth cookie itself is set in the HTTP layer (see
app/core/cookies.py::set_auth_cookie).

How to use:
    from app.features.auth.service import authenticate_user

    user = authenticate_user(session, email, password)
"""

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.security import hash_password, verify_password
from app.core.urls import profile_picture_url
from app.features.auth.schemas import UserOut
from app.features.users.models import User
from app.features.users.service import EmailAlreadyRegistered


def register_user(session: Session, name: str, email: str, password: str) -> User:
    """Create a new user with a hashed password; raises EmailAlreadyRegistered (HTTP 409) for a taken email."""
    user = User(name=name, email=email, password_hash=hash_password(password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise EmailAlreadyRegistered() from exc
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
        avatar_url = profile_picture_url(int(user.avatar_updated_at.timestamp()))
    return UserOut(
        id=user.id,
        name=user.name,
        school=user.school,
        email=user.email,
        avatar_url=avatar_url,
        is_admin=user.is_admin,
        must_change_password=user.must_change_password,
    )
