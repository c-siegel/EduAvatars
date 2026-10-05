"""
Avatar, Background And Voice Library Request/Response Shapes

The shapes for features/media/avatars_router.py, backgrounds_router.py and voices_router.py.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.schema import CamelModel


class AvatarModelOut(CamelModel):
    id: str
    name: str
    file_url: str  # route to fetch the file (see features/media/avatars_router.py::get_avatar_file), not file_path
    thumbnail_url: str | None = None  # None as long as no thumbnail has been generated/uploaded (yet)
    created_at: datetime


class BackgroundImageOut(CamelModel):
    id: str
    name: str
    file_url: str  # route to fetch the file (see features/media/backgrounds_router.py::get_background_file)
    created_at: datetime


class VoiceClipOut(CamelModel):
    id: str
    name: str
    file_url: str  # route to fetch the clip (see features/media/voices_router.py::get_voice_clip_file)
    duration_seconds: float
    consent_confirmed_at: datetime
    created_at: datetime


class VoicePreviewIn(CamelModel):
    # A sentence or two is plenty to judge a voice — and keeps one preview from tying up the
    # single-slot sidecar for long.
    text: str = Field(min_length=1, max_length=300)
    # The languages a project can speak (see frontend/src/lib/speechOptions.ts).
    language: Literal["de", "en"] = "de"
