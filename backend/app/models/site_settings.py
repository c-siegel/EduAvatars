"""
Site Settings Table

Instance-wide settings an admin can change from the dashboard without a redeploy: the public
contact email shown on the Impressum page, and whether self-registration is open.

What is a singleton row?
This table only ever holds one row, with id fixed to 1 — there's exactly one instance-wide
settings record, not one per user. See services/site_settings_service.py for how it's read/
created/updated; nothing else should query or write this table directly.

How to use:
    from app.models.site_settings import SiteSettings

    settings_row = session.get(SiteSettings, 1)
"""

from sqlmodel import Field, SQLModel


class SiteSettings(SQLModel, table=True):
    """Instance-wide settings, stored as a single row with id=1."""

    id: int = Field(default=1, primary_key=True)
    contact_email: str | None = None
    # Mirrors Settings.registration_enabled (core/config.py) as the initial value the first time
    # this row is created — after that, this DB value is authoritative and the env var only
    # matters for a fresh install (see services/site_settings_service.py).
    registration_enabled: bool = True
