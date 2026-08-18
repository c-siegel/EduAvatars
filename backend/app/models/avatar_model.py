"""
Avatar Model Table

A user's uploaded, reusable 3D avatar (.glb file) plus its rendered thumbnail image.

How to use:
    from app.models.avatar_model import AvatarModel

    avatar = session.get(AvatarModel, avatar_id)
"""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class AvatarModel(SQLModel, table=True):
    """One user's reusable .glb 3D avatar."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    name: str
    file_path: str
    # A PNG preview thumbnail (head close-up) rendered once, client-side, from the 3D model (see
    # frontend/src/lib/avatarThumbnail.ts) — None as long as generating it hasn't succeeded (yet),
    # in which case the avatar library keeps showing the initials fallback.
    thumbnail_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
