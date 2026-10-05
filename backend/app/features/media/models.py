"""
Avatar, Background And Voice Library Tables

Each user's reusable uploads: 3D avatar models (.glb), background images, and voice clips for
local voice cloning. The files themselves live on disk (see app/storage/files.py); these rows
only point at them.
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


class BackgroundImage(SQLModel, table=True):
    """One user's reusable background image; upload and selection work like the avatar library (see avatar_model.py)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    name: str
    file_path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VoiceClip(SQLModel, table=True):
    """One user's reference clip for cloning a voice with local TTS (see features/media/voices_router.py)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    name: str
    # Always a normalized mono WAV (see features/media/voice_audio.py), whatever was uploaded.
    file_path: str
    # Identifies the clip towards the local-TTS sidecar, which caches clips by content hash (see
    # features/ai/tts/local.py).
    sha256: str
    duration_seconds: float
    # When the uploader confirmed they may use this person's voice — required for every upload.
    consent_confirmed_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
