"""
Cookies

The two cookies the backend sets: the httponly auth cookie (a signed JWT, see core/security.py)
and the anonymous visitor-id cookie used by the public chat. Kept here, in the HTTP layer, so
services never need a Response object.

How to use:
    from app.core.cookies import set_auth_cookie, get_or_set_visitor_id

    set_auth_cookie(response, user)
    visitor_id = get_or_set_visitor_id(request, response)
"""

import uuid

from fastapi import Request, Response

from app.core.config import settings
from app.core.security import create_access_token
from app.features.users.models import User

# Cookie names used for authentication and visitor tracking
ACCESS_TOKEN_COOKIE = "access_token"
VISITOR_ID_COOKIE = "ah_visitor_id"

# How long a visitor's identity cookie persists. Matches the order of magnitude already assumed
# elsewhere for "one visit" to a public chat (_CHAT_UNLOCK_TOKEN_EXPIRE_MINUTES in core/security.py
# is 240 minutes too) — long enough that closing/reopening a browser tab mid-lesson doesn't hand
# out a fresh identity (losing rate-limit continuity and the ability to keep unlocking a
# password-protected chat), short enough that it isn't effectively permanent tracking.
_VISITOR_ID_COOKIE_MAX_AGE_SECONDS = 4 * 60 * 60


def set_auth_cookie(response: Response, user: User) -> None:
    """Issue a fresh auth token for `user` and set it as the response's httponly cookie."""
    token = create_access_token(user.id, user.token_version)
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )


def clear_auth_cookie(response: Response) -> None:
    """Remove the auth cookie (logout, account deletion)."""
    response.delete_cookie(ACCESS_TOKEN_COOKIE)


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
