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
from app.models.schemas.settings import PublicSiteSettingsOut
from app.services.site_settings_service import get_or_create_site_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public", response_model=PublicSiteSettingsOut)
def get_public_settings(session: Session = Depends(get_session)):
    """The public-facing site settings: imprint details and whether self-registration is open."""
    # Deliberately PublicSiteSettingsOut, not SiteSettingsOut — operational settings like the
    # retention period are for admins only and must not leak through this unauthenticated route.
    return get_or_create_site_settings(session)
