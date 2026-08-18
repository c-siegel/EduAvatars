"""
Background Image Response Shape

The response shape for app/api/background_library.py.

How to use:
    from app.models.schemas.background import BackgroundImageOut
"""

from datetime import datetime

from app.core.schema import CamelModel


class BackgroundImageOut(CamelModel):
    id: str
    name: str
    file_url: str  # route to fetch the file (see api/background_library.py::get_background_file)
    created_at: datetime
