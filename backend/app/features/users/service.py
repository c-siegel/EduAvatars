"""
User Accounts

The logic behind the profile routes (features/users/profile_router.py) and the admin account
routes (features/users/admin_users_router.py): a user editing their own profile, password and
picture, and an admin listing/creating accounts, resetting a password on someone else's behalf,
and promoting/demoting/enabling/disabling accounts — with the guard rails that keep an admin from
locking themselves (or the whole instance) out.

How to use:
    from app.features.users.service import create_user_as_admin

    user = create_user_as_admin(session, name, email, password, is_admin=False)
"""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.errors import DomainError
from app.core.security import hash_password, verify_password
from app.features.users.models import User
from app.storage.files import save_file, unlink_quietly


class EmailAlreadyRegistered(DomainError):
    status_code = 409
    detail = ErrorCode.EMAIL_ALREADY_REGISTERED


class UserNotFound(DomainError):
    status_code = 404
    detail = ErrorCode.USER_NOT_FOUND


class CurrentPasswordIncorrect(DomainError):
    status_code = 400
    detail = ErrorCode.CURRENT_PASSWORD_INCORRECT


class CannotDisableSelf(DomainError):
    status_code = 400
    detail = ErrorCode.CANNOT_DISABLE_SELF


class LastAdminProtected(DomainError):
    status_code = 400
    detail = ErrorCode.LAST_ADMIN_PROTECTED


def count_active_admins(session: Session) -> int:
    """How many enabled admin accounts currently exist.

    Disabled admins don't count — they can't act as one anyway (see core/deps.py::
    get_current_user's enabled check), so they shouldn't block demoting/disabling the last one
    that actually can.
    """
    return len(list(session.exec(select(User).where(User.is_admin == True, User.enabled == True))))  # noqa: E712


def _commit_or_email_conflict(session: Session) -> None:
    """Commit; the only unique column a user write can collide on is the email address."""
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise EmailAlreadyRegistered() from exc


# ==================== ADMIN ====================


def list_users(session: Session) -> list[User]:
    """Every account on this instance."""
    return list(session.exec(select(User)).all())


def get_user(session: Session, user_id: str) -> User:
    """A user by id; raises UserNotFound (HTTP 404) if none exists."""
    user = session.get(User, user_id)
    if user is None:
        raise UserNotFound()
    return user


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
    _commit_or_email_conflict(session)
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
        raise CannotDisableSelf()

    # Would this change remove the last active admin? Only relevant if target is currently an
    # active admin and the change would make them not one (demoted, or disabled, or both).
    target_is_active_admin_now = target.is_admin and target.enabled
    target_would_stay_active_admin = is_admin and enabled
    if target_is_active_admin_now and not target_would_stay_active_admin and count_active_admins(session) <= 1:
        raise LastAdminProtected()

    target.is_admin = is_admin
    target.enabled = enabled
    session.add(target)
    session.commit()
    session.refresh(target)
    return target


# ==================== OWN PROFILE ====================


def update_profile(session: Session, user: User, data: dict) -> User:
    """Apply a partial profile update (only the fields present in `data`)."""
    for field, value in data.items():
        setattr(user, field, value)
    session.add(user)
    # Changing your own email to one already used by another account would otherwise surface as
    # an unhandled IntegrityError (a generic 500) — the same clean 409 as registration instead.
    _commit_or_email_conflict(session)
    session.refresh(user)
    return user


def change_password(session: Session, user: User, current_password: str, new_password: str) -> None:
    """Change `user`'s own password after checking the current one; signs out other sessions."""
    if not verify_password(current_password, user.password_hash):
        raise CurrentPasswordIncorrect()
    user.password_hash = hash_password(new_password)
    # A successful self-chosen password change clears any pending forced-change requirement
    # (see User.must_change_password) — the whole point of that flag was to get here.
    user.must_change_password = False
    # Invalidates all previously issued tokens (e.g. a stolen session cookie on another device) —
    # see User.token_version. The caller re-issues the current session's cookie with the new
    # version, so it stays seamlessly logged in; only *other* sessions get kicked out.
    user.token_version += 1
    session.add(user)
    session.commit()


def invalidate_sessions(session: Session, user: User) -> None:
    """Invalidate every token issued to `user` so far (see User.token_version)."""
    user.token_version += 1
    session.add(user)
    session.commit()


def set_profile_picture(session: Session, user: User, content: bytes, media_type: str, extension: str) -> User:
    """Store an already-validated image as `user`'s profile picture, replacing any previous one."""
    unlink_quietly(user.avatar_path)
    # Filename = user ID instead of a UUID (unlike the avatar library) — there's deliberately only
    # ever one profile picture per user, no directory of several named files.
    file_path = save_file(Path(settings.profile_picture_upload_dir), f"{user.id}{extension}", content)

    user.avatar_path = str(file_path)
    user.avatar_content_type = media_type
    user.avatar_updated_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def clear_profile_picture(session: Session, user: User) -> User:
    """Remove `user`'s profile picture."""
    unlink_quietly(user.avatar_path)
    user.avatar_path = None
    user.avatar_content_type = None
    user.avatar_updated_at = None
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
