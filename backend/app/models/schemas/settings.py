"""
Site Settings Request/Response Shapes

The request/response shapes for the admin-editable, DB-backed instance settings (see
app/api/admin.py and app/api/site_settings.py): the imprint details, whether self-registration
is open, and how long student chat data is kept.

How to use:
    from app.models.schemas.settings import SiteSettingsOut
"""

from pydantic import field_validator

from app.core.schema import CamelModel


class PublicSiteSettingsOut(CamelModel):
    """The parts of the site settings that public pages (Impressum, Register) may read."""

    # Imprint details are public by definition — §5 DDG requires them to be shown to everyone.
    contact_email: str | None
    contact_phone: str | None
    provider_name: str | None
    provider_street: str | None
    provider_city: str | None
    provider_country: str | None
    registration_enabled: bool


class SiteSettingsOut(PublicSiteSettingsOut):
    """Everything an admin sees — the public fields plus operational settings."""

    conversation_retention_days: int


class SiteSettingsUpdate(CamelModel):
    contact_email: str | None = None
    contact_phone: str | None = None
    provider_name: str | None = None
    provider_street: str | None = None
    provider_city: str | None = None
    provider_country: str | None = None
    registration_enabled: bool | None = None
    conversation_retention_days: int | None = None

    @field_validator("conversation_retention_days")
    @classmethod
    def validate_retention(cls, value: int | None) -> int | None:
        # Negative would silently mean "cutoff in the future", i.e. delete everything — reject it
        # rather than let a typo wipe the saved conversations.
        if value is not None and value < 0:
            raise ValueError("conversation_retention_days must be 0 or greater")
        return value
