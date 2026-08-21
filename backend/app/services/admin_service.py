"""
Admin Account Management Helpers

Shared logic behind the admin routes (app/api/admin.py): listing/creating accounts, resetting a
password on someone else's behalf, and promoting/demoting/enabling/disabling accounts — with the
guard rails that keep an admin from locking themselves (or the whole instance) out.

How to use:
    from app.services.admin_service import create_user_as_admin

    user = create_user_as_admin(session, name, email, password, is_admin=False)
"""

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.error_codes import ErrorCode
from app.core.security import hash_password
from app.models.user import User


def count_active_admins(session: Session) -> int:
    """How many enabled admin accounts currently exist.

    Disabled admins don't count — they can't act as one anyway (see core/deps.py::
    get_current_user's enabled check), so they shouldn't block demoting/disabling the last one
    that actually can.
    """
    return len(list(session.exec(select(User).where(User.is_admin == True, User.enabled == True))))  # noqa: E712


def create_user_as_admin(session: Session, name: str, email: str, password: str, is_admin: bool) -> User:
    """Create a new account with an admin-set password — the new user must change it on first login."""
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        is_admin=is_admin,
        must_change_password=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def admin_reset_password(session: Session, user: User, new_password: str) -> None:
    """Set `user`'s password on their behalf; they must change it on next login."""
    user.password_hash = hash_password(new_password)
    user.must_change_password = True
    # Invalidates any already-issued tokens, same as a self-service password change
    # (see api/profile.py::change_password) — an admin-forced reset should sign out old sessions.
    user.token_version += 1
    session.add(user)
    session.commit()


def admin_update_user(session: Session, admin: User, target: User, data: dict) -> User:
    """Apply is_admin/enabled changes to `target`, guarding against self-lockout and losing the last admin."""
    is_admin = data.get("is_admin", target.is_admin)
    enabled = data.get("enabled", target.enabled)

    if target.id == admin.id and "enabled" in data and not enabled:
        raise HTTPException(status_code=400, detail=ErrorCode.CANNOT_DISABLE_SELF)

    # Would this change remove the last active admin? Only relevant if target is currently an
    # active admin and the change would make them not one (demoted, or disabled, or both).
    target_is_active_admin_now = target.is_admin and target.enabled
    target_would_stay_active_admin = is_admin and enabled
    if target_is_active_admin_now and not target_would_stay_active_admin and count_active_admins(session) <= 1:
        raise HTTPException(status_code=400, detail=ErrorCode.LAST_ADMIN_PROTECTED)

    target.is_admin = is_admin
    target.enabled = enabled
    session.add(target)
    session.commit()
    session.refresh(target)
    return target
