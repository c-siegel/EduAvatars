"""
Site Settings Helpers

Reads and updates the single SiteSettings row (see models/site_settings.py) — the admin-editable,
DB-backed instance settings like the public contact email and whether self-registration is open.

How to use:
    from app.services.site_settings_service import get_or_create_site_settings

    site_settings = get_or_create_site_settings(session)
"""

from sqlmodel import Session

from app.core.config import settings
from app.models.site_settings import SiteSettings

_SITE_SETTINGS_ID = 1


def get_or_create_site_settings(session: Session) -> SiteSettings:
    """The singleton settings row, creating it (seeded from the env var default) on first use."""
    row = session.get(SiteSettings, _SITE_SETTINGS_ID)
    if row is None:
        row = SiteSettings(id=_SITE_SETTINGS_ID, registration_enabled=settings.registration_enabled)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def update_site_settings(session: Session, data: dict) -> SiteSettings:
    """Apply a partial update to the site settings row (only the fields present in `data`)."""
    row = get_or_create_site_settings(session)
    for field, value in data.items():
        setattr(row, field, value)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
