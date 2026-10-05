"""
API Router

Collects every feature's router into one APIRouter that app/main.py mounts. Registration order
matters wherever two routes could match the same path (e.g. a literal segment like
/projects/stats next to /projects/{project_id}) — the earlier one wins.
"""

from fastapi import APIRouter

from app.features.analytics import router as analytics_router
from app.features.api_keys import router as api_keys_router
from app.features.auth import router as auth_router
from app.features.chat import preview_router, public_router
from app.features.media import avatars_router, backgrounds_router
from app.features.projects import router as projects_router
from app.features.site_settings import public_router as site_settings_public_router
from app.features.users import admin_router, profile_router

api_router = APIRouter()
api_router.include_router(auth_router.router)  # Authentication endpoints (login, register, logout)
api_router.include_router(projects_router.router)  # Project management endpoints
api_router.include_router(preview_router.router)  # Configurator preview chat + transcription
api_router.include_router(avatars_router.router)  # Avatar upload and management
api_router.include_router(backgrounds_router.router)  # Background image management
api_router.include_router(analytics_router.router)  # Analytics and usage statistics
api_router.include_router(api_keys_router.router)  # API key management for external services
api_router.include_router(profile_router.router)  # User profile management
api_router.include_router(public_router.router)  # Public chat endpoints (no authentication required)
api_router.include_router(admin_router.router)  # Admin dashboard: account management, site settings
api_router.include_router(site_settings_public_router.router)  # Public-facing site settings (contact email, etc.)
