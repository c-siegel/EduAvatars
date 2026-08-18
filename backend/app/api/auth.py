"""
Authentication Routes

Handles account registration, login, logout, the current-user check, and the password-reset
flow. Every route here is rate-limited (see app/core/rate_limit.py) to protect against
brute-force login attempts, credential stuffing, and mass account creation.

How does login work here?
On success, login/register set an httponly cookie (see app/core/deps.py) containing a signed
JWT (JSON Web Token) — the browser sends it automatically on later requests, and JavaScript
can't read it. There's no bearer token in request headers to manage on the frontend.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.config import settings
from app.core.deps import ACCESS_TOKEN_COOKIE, get_current_user, get_session
from app.core.rate_limit import (
    enforce_login_rate_limit,
    enforce_password_reset_rate_limit,
    enforce_register_rate_limit,
)
from app.models.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    RegistrationStatusOut,
    ResetPasswordRequest,
    UserOut,
)
from app.models.user import User
from app.services.auth_service import authenticate_user, register_user, set_auth_cookie, user_to_out
from app.services.password_reset_service import request_password_reset, reset_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/registration-status", response_model=RegistrationStatusOut)
def registration_status():
    """Whether self-registration is currently enabled."""
    # Public (no login needed) — the registration page checks this before rendering the form,
    # see pages/Register. The actual enforcement happens below, in register().
    return RegistrationStatusOut(enabled=settings.registration_enabled)


@router.post("/register", response_model=UserOut)
def register(data: RegisterRequest, request: Request, response: Response, session: Session = Depends(get_session)):
    """Create a new account and log the user in, unless registration is disabled."""
    if not settings.registration_enabled:
        # Checked before the rate limit — no reason to spend that budget when registration is
        # switched off entirely anyway (at launch: internal use only).
        raise HTTPException(status_code=403, detail="Registrierung ist aktuell nicht möglich.")
    enforce_register_rate_limit(request)
    try:
        user = register_user(session, data.name, data.email, data.password)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Diese E-Mail-Adresse wird bereits verwendet.") from exc
    set_auth_cookie(response, user)
    return user_to_out(user)


@router.post("/login", response_model=UserOut)
def login(data: LoginRequest, request: Request, response: Response, session: Session = Depends(get_session)):
    """Authenticate with email + password and set the auth cookie."""
    enforce_login_rate_limit(request, data.email)
    user = authenticate_user(session, data.email, data.password)
    if user is None:
        raise HTTPException(status_code=401, detail="E-Mail oder Passwort ist falsch.")
    set_auth_cookie(response, user)
    return user_to_out(user)


@router.post("/logout")
def logout(response: Response):
    """Clear the auth cookie."""
    response.delete_cookie(ACCESS_TOKEN_COOKIE)
    return None


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """The currently authenticated user."""
    return user_to_out(current_user)


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, request: Request, session: Session = Depends(get_session)):
    """Start a password reset for the given email, if an account with it exists."""
    enforce_password_reset_rate_limit(request, data.email)
    request_password_reset(session, data.email)
    # Always the same response, whether or not the email exists or SMTP is configured — this
    # prevents enumerating which accounts are registered (see password_reset_service.py).
    return {"detail": "Falls ein Konto mit dieser E-Mail existiert, wurde eine Nachricht verschickt."}


@router.post("/reset-password")
def reset_password_route(data: ResetPasswordRequest, session: Session = Depends(get_session)):
    """Complete a password reset using the token from the reset email."""
    user = reset_password(session, data.token, data.new_password)
    if user is None:
        raise HTTPException(status_code=400, detail="Link ist ungültig oder abgelaufen.")
    return {"detail": "Passwort wurde zurückgesetzt."}
