"""
Admin Account Routes

Account management for the admin dashboard: list/create accounts, reset someone's password, and
promote/demote and enable/disable accounts. Every route here requires an admin account (see
core/deps.py::get_current_admin). The instance-wide site settings have their own admin routes in
app/features/site_settings/admin_router.py.

Why disable instead of delete?
There's deliberately no admin-initiated delete endpoint — disabling (User.enabled) is the
primary way an admin removes someone's access. The only way an account is actually deleted is
the existing self-service DELETE /me, which cascades a user's own data. See service.py for
the guard rails (can't disable yourself, can't remove the last active admin).
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.deps import get_current_admin, get_session
from app.features.users import service
from app.features.users.models import User
from app.features.users.schemas import AdminPasswordReset, AdminUserCreate, AdminUserOut, AdminUserUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserOut])
def list_users(admin: User = Depends(get_current_admin), session: Session = Depends(get_session)):
    """List every account on this instance."""
    return service.list_users(session)


@router.post("/users", response_model=AdminUserOut)
def create_user(
    data: AdminUserCreate,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """Create a new account with a temporary password the new user must change on first login."""
    return service.create_user_as_admin(session, data.name, data.email, data.password, data.is_admin)


@router.put("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: str,
    data: AdminUserUpdate,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """Promote/demote or enable/disable an account."""
    target = service.get_user(session, user_id)
    return service.admin_update_user(session, admin, target, data.model_dump(exclude_unset=True))


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: str,
    data: AdminPasswordReset,
    admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """Set a user's password on their behalf; they must change it on next login."""
    target = service.get_user(session, user_id)
    service.admin_reset_password(session, target, data.new_password)
    return None
