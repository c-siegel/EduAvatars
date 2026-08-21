"""
Site Settings Table

Instance-wide settings an admin can change from the dashboard without a redeploy: the imprint
("Impressum") details shown on the legal-notice page, whether self-registration is open, and how
long student chat data is kept.

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
    # Imprint fields (§5 DDG). All optional: an instance that hasn't filled them in yet shows the
    # "[noch ändern]" placeholder instead, rather than a blank or broken line.
    contact_email: str | None = None
    contact_phone: str | None = None
    provider_name: str | None = None
    provider_street: str | None = None
    provider_city: str | None = None
    provider_country: str | None = None
    # Mirrors Settings.registration_enabled (core/config.py) as the initial value the first time
    # this row is created — after that, this DB value is authoritative and the env var only
    # matters for a fresh install (see services/site_settings_service.py).
    registration_enabled: bool = True
    # How long saved student conversations and page-view logs are kept, in days. 0 = keep forever
    # (the previous behaviour). Enforced by services/retention_service.py on every app start.
    conversation_retention_days: int = 0
