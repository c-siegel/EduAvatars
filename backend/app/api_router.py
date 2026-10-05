"""
API Router

Collects every feature's router into one APIRouter that app/main.py mounts. Registration order
matters wherever two routes could match the same path: a literal segment like /projects/stats or
/projects/import must be registered before /projects/{project_id}, or the earlier, generic route
swallows it.
"""

from fastapi import APIRouter

from app.features.analytics import conversations_router, stats_router
from app.features.api_keys import providers_router
from app.features.api_keys import router as api_keys_router
from app.features.auth import router as auth_router
from app.features.chat import preview_router, public_router
from app.features.media import avatars_router, backgrounds_router
from app.features.projects import publication_router, start_audio_router, transfer_router
from app.features.projects import router as projects_router
from app.features.site_settings import admin_router as site_settings_admin_router
from app.features.site_settings import public_router as site_settings_public_router
from app.features.users import admin_users_router, profile_router

api_router = APIRouter()

# Authentication and the user's own account
api_router.include_router(auth_router.router)  # /auth: register, login, logout, password reset
api_router.include_router(profile_router.router)  # /profile: own profile, picture, password, deletion

# Projects — the literal /projects/stats and /projects/import routes first (see module docstring)
api_router.include_router(stats_router.projects_router)  # /projects/stats: dashboard overview
api_router.include_router(transfer_router.router)  # /projects/import, /projects/{id}/export
api_router.include_router(projects_router.router)  # /projects: CRUD
api_router.include_router(publication_router.router)  # /projects/{id}/publish, /unpublish
api_router.include_router(start_audio_router.router)  # /projects/{id}/start-audio
api_router.include_router(preview_router.router)  # /projects/{id}/preview-message, /transcribe

# Libraries and keys
api_router.include_router(avatars_router.router)  # /avatar-models
api_router.include_router(backgrounds_router.router)  # /backgrounds
api_router.include_router(providers_router.router)  # /api-keys/providers: provider registry
api_router.include_router(api_keys_router.router)  # /api-keys: the user's stored keys

# Analytics
api_router.include_router(stats_router.router)  # /analytics/stats, /analytics/timeseries
api_router.include_router(conversations_router.router)  # /analytics/sessions, /export, /delete

# Public chat (no login)
api_router.include_router(public_router.router)  # /public/{slug}...

# Admin and site settings
api_router.include_router(admin_users_router.router)  # /admin/users
api_router.include_router(site_settings_admin_router.router)  # /admin/settings
api_router.include_router(site_settings_public_router.router)  # /settings/public
