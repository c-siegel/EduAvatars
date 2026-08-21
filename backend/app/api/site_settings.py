"""
Public Site Settings Routes

The unauthenticated view of the instance-wide site settings — just the pieces public pages need
(contact email for the Impressum, whether self-registration is open for the Register page). See
app/api/admin.py for the admin-only read/write versions of the same data.

How to use:
    from app.api import site_settings

    app.include_router(site_settings.router)
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.deps import get_session
from app.models.schemas.settings import SiteSettingsOut
from app.services.site_settings_service import get_or_create_site_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public", response_model=SiteSettingsOut)
def get_public_settings(session: Session = Depends(get_session)):
    """The public-facing site settings: contact email and whether self-registration is open."""
    return get_or_create_site_settings(session)
