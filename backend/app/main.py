"""
This is the main application file that creates and configures the FastAPI application.
It's the starting point for the backend server.

What is this file for?
This file:
- Creates the FastAPI application instance
- Configures CORS (Cross-Origin Resource Sharing)
- Registers all API route handlers
- Provides a health check endpoint

How it works:
1. When you run the server (e.g., `uvicorn app.main:app`), this file is executed
2. The FastAPI app instance is created
3. Middleware and routes are registered
4. The server starts listening for requests
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

import anyio.to_thread
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.api import (
    admin,
    analytics,
    api_keys,
    auth,
    avatar_library,
    background_library,
    profile,
    projects,
    public_chat,
    site_settings,
)
from app.core.config import settings
from app.db.session import engine
from app.services.retention_service import purge_expired_data

logger = logging.getLogger(__name__)

# How often the data-retention purge re-runs on a live process (see services/retention_service.py).
# A restart isn't the only time it should run — a school deployment can stay up for weeks — but
# retention itself is configured in whole days, so checking a few times a day is timely enough.
_RETENTION_CHECK_INTERVAL_SECONDS = 6 * 60 * 60


def _run_retention_purge() -> None:
    """Runs one retention purge; never lets a cleanup problem take down the caller."""
    try:
        with Session(engine) as session:
            purge_expired_data(session)
    except Exception:
        logger.exception("Data-retention cleanup failed.")


async def _retention_loop() -> None:
    """Re-runs the retention purge periodically for as long as the process stays up.

    Without this, data past the configured retention period only ever got deleted right after
    a restart (see the lifespan startup call below) and then never again — for a long-running
    container, that defeats the whole point of a retention period.
    """
    while True:
        await asyncio.sleep(_RETENTION_CHECK_INTERVAL_SECONDS)
        # The purge itself is blocking DB work — run it off the event loop, same reasoning as
        # every sync route (see request_thread_pool_size above).
        await anyio.to_thread.run_sync(_run_retention_purge)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks: raise the thread-pool ceiling, run the data-retention cleanup once
    immediately, then keep re-running it periodically for as long as the process is up."""
    # anyio's own default (40) caps how many worker threads every sync route (almost all of
    # them, see api/*.py) and every /message/stream response body may use at once, across the
    # whole process — sized for a handful of simultaneous users, not a class of ~30 each holding
    # a thread for their own request. Settable only from inside a running event loop, hence here.
    anyio.to_thread.current_default_thread_limiter().total_tokens = settings.request_thread_pool_size
    _run_retention_purge()
    retention_task = asyncio.create_task(_retention_loop())
    try:
        yield
    finally:
        retention_task.cancel()
        with suppress(asyncio.CancelledError):
            await retention_task


# Create the FastAPI application instance
# This is the main application object that handles all HTTP requests
app = FastAPI(title="EduAvatars API", lifespan=lifespan)

# Configure CORS (Cross-Origin Resource Sharing) middleware
# CORS allows the frontend (running on a different domain/port) to make requests to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,  # Which domains can make requests
    allow_credentials=True,  # Allow cookies to be sent with requests
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all HTTP headers
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Adds baseline security headers to every response.

    Defense-in-depth alongside the same headers set at the Caddy layer in production (see
    docker/Caddyfile) — this also covers Deploy A (uvicorn run directly, no Caddy in front) and
    any future non-Caddy topology. No Content-Security-Policy here, same reason as the
    Caddyfile: getting it right needs real browser testing against the three.js avatar, blob:
    audio playback, and the Tally survey iframe, not a guess that risks silently breaking them.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Harmless if this response is ever actually served over plain HTTP: browsers only honor
    # this header on a response they received over HTTPS (RFC 6797).
    response.headers["Strict-Transport-Security"] = "max-age=15552000"
    return response


# Register API routers
# Each router contains a group of related endpoints
app.include_router(auth.router)  # Authentication endpoints (login, register, logout)
app.include_router(projects.router)  # Project management endpoints
app.include_router(avatar_library.router)  # Avatar upload and management
app.include_router(background_library.router)  # Background image management
app.include_router(analytics.router)  # Analytics and usage statistics
app.include_router(api_keys.router)  # API key management for external services
app.include_router(profile.router)  # User profile management
app.include_router(public_chat.router)  # Public chat endpoints (no authentication required)
app.include_router(admin.router)  # Admin dashboard: account management, site settings
app.include_router(site_settings.router)  # Public-facing site settings (contact email, etc.)


@app.get("/health")
def health():
    """
    Health check endpoint.
    
    This endpoint is used to check if the server is running and responding.
    It's commonly used by:
    - Load balancers to check server health
    - Monitoring systems to detect outages
    - Deployment scripts to verify the server started successfully
    """
    return {"status": "ok"}