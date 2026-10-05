"""
API Router

Collects every feature's router into one APIRouter that app/main.py mounts. Registration order
matters wherever two routes could match the same path (e.g. a literal segment like
/projects/stats next to /projects/{project_id}) — the earlier one wins.
"""

from fastapi import APIRouter

from app.features.chat import preview_router, public_router
from app.api import (
    admin,
    analytics,
    api_keys,
    auth,
    avatar_library,
    background_library,
    profile,
    projects,
    site_settings,
)

api_router = APIRouter()
api_router.include_router(auth.router)  # Authentication endpoints (login, register, logout)
api_router.include_router(projects.router)  # Project management endpoints
api_router.include_router(preview_router.router)  # Configurator preview chat + transcription
api_router.include_router(avatar_library.router)  # Avatar upload and management
api_router.include_router(background_library.router)  # Background image management
api_router.include_router(analytics.router)  # Analytics and usage statistics
api_router.include_router(api_keys.router)  # API key management for external services
api_router.include_router(profile.router)  # User profile management
api_router.include_router(public_router.router)  # Public chat endpoints (no authentication required)
api_router.include_router(admin.router)  # Admin dashboard: account management, site settings
api_router.include_router(site_settings.router)  # Public-facing site settings (contact email, etc.)
