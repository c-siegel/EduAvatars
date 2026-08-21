"""
Site Settings Request/Response Shapes

The request/response shapes for the admin-editable, DB-backed instance settings (see
app/api/admin.py and app/api/site_settings.py): the public contact email and whether
self-registration is open.

How to use:
    from app.models.schemas.settings import SiteSettingsOut
"""

from app.core.schema import CamelModel


class SiteSettingsOut(CamelModel):
    contact_email: str | None
    registration_enabled: bool


class SiteSettingsUpdate(CamelModel):
    contact_email: str | None = None
    registration_enabled: bool | None = None
