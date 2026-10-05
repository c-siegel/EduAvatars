"""
API Prefix And Public URLs

Every route is mounted under API_PREFIX (see app/main.py), and every URL the API hands out for a
browser to load directly — an avatar's .glb file, a background image, the start-prompt audio, a
profile picture — is a ready-to-use absolute path built here, prefix included. The frontend uses
these as-is (<img src>, fetch) instead of stitching a prefix onto router-relative paths.

The bundled default avatars are the exception: they're static files the frontend serves itself
(frontend/public/avatars/), so their URLs carry no API prefix.
"""

API_PREFIX = "/api/v1"


def api_url(path: str) -> str:
    """The browser path for a route path like "/avatars/{id}/file"."""
    return f"{API_PREFIX}{path}"


def avatar_file_url(avatar_id: str) -> str:
    return api_url(f"/avatars/{avatar_id}/file")


def avatar_thumbnail_url(avatar_id: str) -> str:
    return api_url(f"/avatars/{avatar_id}/thumbnail")


def builtin_avatar_url(name: str) -> str:
    """A bundled default avatar (e.g. "julia"), served by the frontend from public/avatars/."""
    return f"/avatars/{name}.glb"


def background_file_url(background_id: str) -> str:
    return api_url(f"/backgrounds/{background_id}/file")


def voice_clip_file_url(clip_id: str) -> str:
    return api_url(f"/voice-clips/{clip_id}/file")


def start_audio_url(project_id: str) -> str:
    return api_url(f"/projects/{project_id}/start-audio")


def profile_picture_url(version: int) -> str:
    """The current user's picture; `version` busts the browser cache after a new upload."""
    return api_url(f"/me/picture?v={version}")
