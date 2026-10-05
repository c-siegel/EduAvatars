"""
Admin Site Settings Routes

Read and update the instance-wide site settings (imprint details, self-registration toggle,
conversation retention period). Admin only — see public_router.py for the unauthenticated subset.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.deps import get_current_admin, get_session
from app.features.site_settings.schemas import SiteSettingsOut, SiteSettingsUpdate
from app.features.site_settings.service import get_or_create_site_settings, update_site_settings
from app.features.users.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


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
