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

import logging
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run the data-retention cleanup once per app start."""
    try:
        with Session(engine) as session:
            purge_expired_data(session)
    except Exception:
        # Never let a cleanup problem stop the API from coming up.
        logger.exception("Data-retention cleanup failed on startup.")
    yield


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