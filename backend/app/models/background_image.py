"""
Background Image Table

A user's uploaded, reusable background image for the avatar stage (configurator preview and
public chat).

How to use:
    from app.models.background_image import BackgroundImage

    background = session.get(BackgroundImage, background_id)
"""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class BackgroundImage(SQLModel, table=True):
    """One user's reusable background image; upload and selection work like the avatar library (see avatar_model.py)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    name: str
    file_path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
