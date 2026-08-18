"""
Avatar Model Response Shape

The response shape for app/api/avatar_library.py.

How to use:
    from app.models.schemas.avatar import AvatarModelOut
"""

from datetime import datetime

from app.core.schema import CamelModel


class AvatarModelOut(CamelModel):
    id: str
    name: str
    file_url: str  # route to fetch the file (see api/avatar_library.py::get_avatar_file), not file_path
    thumbnail_url: str | None = None  # None as long as no thumbnail has been generated/uploaded (yet)
    created_at: datetime
