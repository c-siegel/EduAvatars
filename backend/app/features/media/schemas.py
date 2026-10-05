"""
Avatar And Background Library Response Shapes

The response shapes for features/media/avatars_router.py and backgrounds_router.py.
"""

from datetime import datetime

from app.core.schema import CamelModel


class AvatarModelOut(CamelModel):
    id: str
    name: str
    file_url: str  # route to fetch the file (see api/avatar_library.py::get_avatar_file), not file_path
    thumbnail_url: str | None = None  # None as long as no thumbnail has been generated/uploaded (yet)
    created_at: datetime


class BackgroundImageOut(CamelModel):
    id: str
    name: str
    file_url: str  # route to fetch the file (see api/background_library.py::get_background_file)
    created_at: datetime
