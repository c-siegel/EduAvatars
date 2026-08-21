"""
Admin Routes

Account management for the admin dashboard: list/create accounts, reset someone's password,
promote/demote and enable/disable accounts, and the instance-wide site settings (contact email,
self-registration toggle). Every route here requires an admin account (see core/deps.py::
get_current_admin).

Why disable instead of delete?
There's deliberately no admin-initiated delete endpoint — disabling (User.enabled) is the
primary way an admin removes someone's access. The only way an account is actually deleted is
the existing self-service DELETE /profile, which cascades a user's own data. See
services/admin_service.py for the guard rails (can't disable yourself, can't remove the last
active admin).

How to use:
    from app.api import admin

    app.include_router(admin.router)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.deps import get_current_admin, get_session
from app.core.error_codes import ErrorCode
from app.models.schemas.admin import AdminPasswordReset, AdminUserCreate, AdminUserOut, AdminUserUpdate
from app.models.schemas.settings import SiteSettingsOut, SiteSettingsUpdate
from app.models.user import User
from app.services.admin_service import admin_reset_password, admin_update_user, create_user_as_admin
from app.services.site_settings_service import get_or_create_site_settings, update_site_settings

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_target_user(session: Session, user_id: str) -> User:
    """A user by id, or 404 if none exists."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=ErrorCode.USER_NOT_FOUND)
    return user


@router.get("/users", response_model=list[AdminUserOut])
def list_users(admin: User = Depends(get_current_admin), session: Session = Depends(get_session)):
    """List every account on this instance."""
    return session.exec(select(User)).all()


@router.post("/users", response_model=AdminUserOut)
def create_user(
    data: AdminUserCreate,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """Create a new account with a temporary password the new user must change on first login."""
    try:
        user = create_user_as_admin(session, data.name, data.email, data.password, data.is_admin)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=ErrorCode.EMAIL_ALREADY_REGISTERED) from exc
    return user


@router.put("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: str,
    data: AdminUserUpdate,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """Promote/demote or enable/disable an account."""
    target = _get_target_user(session, user_id)
    return admin_update_user(session, admin, target, data.model_dump(exclude_unset=True))


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: str,
    data: AdminPasswordReset,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """Set a user's password on their behalf; they must change it on next login."""
    target = _get_target_user(session, user_id)
    admin_reset_password(session, target, data.new_password)
    return None


@router.get("/settings", response_model=SiteSettingsOut)
def get_settings(admin: User = Depends(get_current_admin), session: Session = Depends(get_session)):
    """The instance-wide site settings (contact email, self-registration toggle)."""
    return get_or_create_site_settings(session)


@router.put("/settings", response_model=SiteSettingsOut)
def put_settings(
    data: SiteSettingsUpdate,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """Update the instance-wide site settings."""
    return update_site_settings(session, data.model_dump(exclude_unset=True))
