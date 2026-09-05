"""
Dependency Functions for FastAPI Routes

This module provides reusable dependency functions for FastAPI route handlers.
These functions handle common tasks like authentication, authorization, and database access.

What are dependencies?
In FastAPI, dependencies are functions that run before your route handler. They can:
- Extract and validate data from requests
- Handle authentication and authorization
- Provide database sessions
- Perform common checks

How to use:
    from fastapi import APIRouter, Depends
    from app.core.deps import get_current_user, get_owned_project
    
    @router.get("/projects/{project_id}")
    def get_project(
        project: Project = Depends(get_owned_project),
        current_user: User = Depends(get_current_user)
    ):
        # current_user is automatically authenticated
        # project is automatically verified to belong to current_user
        return project
"""

import uuid

from fastapi import Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.project import Project
from app.models.user import User

# Cookie names used for authentication and visitor tracking
ACCESS_TOKEN_COOKIE = "access_token"
VISITOR_ID_COOKIE = "ah_visitor_id"

# How long a visitor's identity cookie persists. Matches the order of magnitude already assumed
# elsewhere for "one visit" to a public chat (_CHAT_UNLOCK_TOKEN_EXPIRE_MINUTES in core/security.py
# is 240 minutes too) — long enough that closing/reopening a browser tab mid-lesson doesn't hand
# out a fresh identity (losing rate-limit continuity and the ability to keep unlocking a
# password-protected chat), short enough that it isn't effectively permanent tracking.
_VISITOR_ID_COOKIE_MAX_AGE_SECONDS = 4 * 60 * 60


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    """
    Authenticate the current user from the access token cookie.
    
    This dependency ensures that the user is logged in and returns the User object.
    If authentication fails, it raises an HTTP 401 error.
    
    How it works:
    1. Reads the access_token cookie from the request
    2. Decodes the JWT token to get user_id and token_version
    3. Fetches the user from the database
    4. Verifies the user exists, is enabled, and the token version matches
    
    Security features:
    - Token version checking prevents token reuse after logout
    - User must be enabled (not disabled by admin)
    - Same error message for all failures (prevents information leakage)
    
    Args:
        request: The FastAPI request object (contains cookies)
        session: Database session (injected by FastAPI)
    
    Returns:
        User: The authenticated user object
    
    Raises:
        HTTPException: 401 if not authenticated, token expired, or user disabled
    
    Example:
        @router.get("/profile")
        def get_profile(user: User = Depends(get_current_user)):
            return {"email": user.email, "name": user.name}
    """
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail=ErrorCode.NOT_AUTHENTICATED)
    try:
        user_id, token_version = decode_access_token(token)
    except Exception as exc:  # invalid/expired JWT
        raise HTTPException(status_code=401, detail=ErrorCode.SESSION_EXPIRED) from exc
    user = session.get(User, user_id)
    if user is None or not user.enabled:
        raise HTTPException(status_code=401, detail=ErrorCode.NOT_AUTHENTICATED)
    # Same error code as above (instead of e.g. "Logged out elsewhere") — a client
    # should not be able to distinguish whether a token expired or was intentionally
    # invalidated (see User.token_version).
    if token_version != user.token_version:
        raise HTTPException(status_code=401, detail=ErrorCode.SESSION_EXPIRED)
    return user


def get_current_user_optional(
    request: Request,
    session: Session = Depends(get_session),
) -> User | None:
    """
    Optionally authenticate the current user.
    
    Like get_current_user, but never raises an error. Returns None if not authenticated.
    Used for routes that work for both authenticated (teacher) and anonymous (public chat)
    users, and need to decide what's allowed without a logged-in user.
    
    Use cases:
    - Public chat pages that show extra features for logged-in users
    - Avatar library that allows anonymous access but tracks usage for logged-in users
    
    Args:
        request: The FastAPI request object (contains cookies)
        session: Database session (injected by FastAPI)
    
    Returns:
        User | None: The authenticated user object, or None if not authenticated
    
    Example:
        @router.get("/avatar/{avatar_id}")
        def get_avatar(
            avatar_id: str,
            user: User | None = Depends(get_current_user_optional)
        ):
            if user:
                # Show extra features for logged-in users
                return get_avatar_with_usage_stats(avatar_id, user.id)
            else:
                # Basic avatar for anonymous users
                return get_basic_avatar(avatar_id)
    """
    # Like get_current_user, but never raises — for routes that can be called both
    # authenticated (teacher) and anonymous (public chat) and decide themselves what's
    # allowed without a logged-in user (see api/avatar_library.py::get_avatar_file).
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        return None
    try:
        user_id, token_version = decode_access_token(token)
    except Exception:
        return None
    user = session.get(User, user_id)
    if user is None or not user.enabled or token_version != user.token_version:
        return None
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Require the current user to be an admin.

    Same shape as get_current_user, layered on top of it: authentication happens first (401 if
    not logged in), then this adds the authorization check (403 if logged in but not an admin).

    Raises:
        HTTPException: 403 if the authenticated user isn't an admin

    Example:
        @router.get("/admin/users")
        def list_users(admin: User = Depends(get_current_admin)):
            ...
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail=ErrorCode.ADMIN_REQUIRED)
    return current_user


def get_owned_project(
    project_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Project:
    """
    Get a project that belongs to the current authenticated user.
    
    This dependency ensures that:
    1. The user is authenticated (via get_current_user)
    2. The project exists
    3. The project belongs to the authenticated user
    
    Security: Returns 404 instead of 403 for unauthorized access to prevent
    IDOR (Insecure Direct Object Reference) enumeration attacks. This prevents
    attackers from guessing project IDs to find out which projects exist.
    
    Args:
        project_id: The ID of the project to fetch
        session: Database session (injected by FastAPI)
        current_user: The authenticated user (injected by get_current_user)
    
    Returns:
        Project: The project object that belongs to the current user
    
    Raises:
        HTTPException: 404 if project doesn't exist or doesn't belong to user
    
    Example:
        @router.put("/projects/{project_id}")
        def update_project(
            project: Project = Depends(get_owned_project),
            updates: ProjectUpdate
        ):
            # project is guaranteed to belong to current_user
            project.name = updates.name
            session.add(project)
            session.commit()
            return project
    """
    # 404 instead of 403 for foreign projects to prevent IDOR enumeration
    project = session.get(Project, project_id)
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=ErrorCode.PROJECT_NOT_FOUND)
    return project


def get_published_project(
    slug: str,
    session: Session = Depends(get_session),
) -> Project:
    """
    Get a published project by its share slug.
    
    This dependency fetches a project that has been published and is accessible
    via a share URL. Used for public chat pages where users interact with
    published projects without logging in.
    
    Args:
        slug: The share slug of the project (e.g., "abc123")
        session: Database session (injected by FastAPI)
    
    Returns:
        Project: The published project object
    
    Raises:
        HTTPException: 404 if project doesn't exist or isn't published
    
    Example:
        @router.get("/public/{slug}")
        def get_public_chat(
            project: Project = Depends(get_published_project)
        ):
            # project is guaranteed to be published
            return {
                "name": project.name,
                "avatar": project.avatar_id,
                "prompt": project.start_prompt
            }
    """
    project = session.exec(
        select(Project).where(Project.share_slug == slug, Project.published == True)  # noqa: E712
    ).first()
    if project is None:
        raise HTTPException(status_code=404, detail=ErrorCode.PROJECT_NOT_FOUND_OR_UNPUBLISHED)
    return project


def get_or_set_visitor_id(request: Request, response: Response) -> str:
    """
    Get or create a visitor ID for anonymous users.
    
    This function provides anonymous visitor identification for the public chat page.
    It doesn't require login and has no relation to User accounts.
    
    How it works:
    1. Checks if the visitor_id cookie exists in the request
    2. If not, generates a new UUID and sets it as a cookie
    3. Returns the visitor ID
    
    Use cases:
    - Tracking anonymous usage statistics
    - Rate limiting anonymous users
    - Storing preferences for anonymous users
    
    Args:
        request: The FastAPI request object (contains cookies)
        response: The FastAPI response object (used to set cookies)
    
    Returns:
        str: The visitor ID (UUID string)
    
    Example:
        @router.post("/public/chat")
        def send_message(
            message: str,
            visitor_id: str = Depends(get_or_set_visitor_id)
        ):
            # Track this message for the anonymous visitor
            log_message(visitor_id, message)
            return {"response": "Hello!"}
    """
    # Anonymous visitor identification for the public chat page (no login, no relation to User)
    visitor_id = request.cookies.get(VISITOR_ID_COOKIE)
    if not visitor_id:
        visitor_id = str(uuid.uuid4())
        response.set_cookie(
            VISITOR_ID_COOKIE,
            visitor_id,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=_VISITOR_ID_COOKIE_MAX_AGE_SECONDS,
        )
    return visitor_id