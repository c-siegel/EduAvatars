"""
User Profile Routes

Lets the logged-in user view and edit their own profile: basic fields, a profile picture,
password changes, signing out of all sessions, and deleting the account.

How to use:
    from app.api import profile

    app.include_router(profile.router)
"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.config import settings
from app.core.deps import ACCESS_TOKEN_COOKIE, get_current_user, get_session
from app.core.error_codes import ErrorCode
from app.core.security import hash_password, verify_password
from app.models.schemas.auth import UserOut
from app.models.schemas.profile import PasswordChange, ProfileUpdate
from app.models.user import User
from app.services.account_service import delete_user_account
from app.services.auth_service import set_auth_cookie, user_to_out

router = APIRouter(prefix="/profile", tags=["profile"])

# Image signatures (first bytes) instead of file extension — same approach as avatar_library.py,
# stops arbitrary files from being stored and later served back out under a false extension.
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_MAX_PICTURE_BYTES = 5 * 1024 * 1024  # 5 MB — a profile photo, not a 3D model


def _sniff_image(content: bytes) -> tuple[str, str] | None:
    """Detect PNG/JPEG/WebP from the file's magic bytes, or None if none match."""
    if content[:8] == _PNG_MAGIC:
        return "image/png", ".png"
    if content[:3] == _JPEG_MAGIC:
        return "image/jpeg", ".jpg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def _delete_picture_file(user: User) -> None:
    if user.avatar_path:
        Path(user.avatar_path).unlink(missing_ok=True)


@router.get("", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    """The current user's profile."""
    return user_to_out(current_user)


@router.put("", response_model=UserOut)
def update_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Update profile fields (only the ones actually provided)."""
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    session.add(current_user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=ErrorCode.EMAIL_ALREADY_REGISTERED) from exc
    session.refresh(current_user)
    return user_to_out(current_user)


@router.post("/picture", response_model=UserOut)
async def upload_profile_picture(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Upload or replace the current user's profile picture."""
    content = await file.read(_MAX_PICTURE_BYTES + 1)
    if len(content) > _MAX_PICTURE_BYTES:
        raise HTTPException(status_code=400, detail=ErrorCode.PROFILE_PICTURE_TOO_LARGE)
    sniffed = _sniff_image(content)
    if sniffed is None:
        raise HTTPException(status_code=400, detail=ErrorCode.PROFILE_PICTURE_INVALID_TYPE)
    media_type, ext = sniffed

    _delete_picture_file(current_user)
    picture_dir = Path(settings.profile_picture_upload_dir)
    picture_dir.mkdir(parents=True, exist_ok=True)
    # Filename = user ID instead of a UUID (unlike avatar_library.py) — there's deliberately only
    # ever one profile picture per user, no directory of several named files.
    file_path = picture_dir / f"{current_user.id}{ext}"
    file_path.write_bytes(content)

    current_user.avatar_path = str(file_path)
    current_user.avatar_content_type = media_type
    current_user.avatar_updated_at = datetime.now(timezone.utc)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return user_to_out(current_user)


@router.delete("/picture", response_model=UserOut)
def delete_profile_picture(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Remove the current user's profile picture."""
    _delete_picture_file(current_user)
    current_user.avatar_path = None
    current_user.avatar_content_type = None
    current_user.avatar_updated_at = None
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return user_to_out(current_user)


@router.get("/picture")
def get_profile_picture(current_user: User = Depends(get_current_user)):
    """Serve the current user's own profile picture."""
    # Unlike the avatar models (avatar_library.py), no ID/IDOR (Insecure Direct Object Reference)
    # check is needed here: this route always serves only the cookie-authenticated user's own
    # picture, there's no ID parameter to spoof.
    if not current_user.avatar_path:
        raise HTTPException(status_code=404, detail=ErrorCode.PROFILE_PICTURE_NOT_FOUND)
    return FileResponse(current_user.avatar_path, media_type=current_user.avatar_content_type or "application/octet-stream")


@router.put("/password")
def change_password(
    data: PasswordChange,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Change the current user's password; other sessions are signed out, this one stays signed in."""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail=ErrorCode.CURRENT_PASSWORD_INCORRECT)
    current_user.password_hash = hash_password(data.new_password)
    # A successful self-chosen password change clears any pending forced-change requirement
    # (see User.must_change_password) — the whole point of that flag was to get here.
    current_user.must_change_password = False
    # Invalidates all previously issued tokens (e.g. a stolen session cookie on another device) —
    # see User.token_version. The current session immediately gets a fresh cookie with the new
    # version below, so it stays seamlessly logged in; only *other* sessions get kicked out.
    current_user.token_version += 1
    session.add(current_user)
    session.commit()
    set_auth_cookie(response, current_user)
    return None


@router.post("/logout-everywhere")
def logout_everywhere(
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Sign out of every session (e.g. after a suspected compromise), while keeping this one signed in."""
    # A self-service emergency exit when an account may be compromised, independent of a password
    # change: invalidates all tokens, but immediately issues the current session a fresh one.
    current_user.token_version += 1
    session.add(current_user)
    session.commit()
    set_auth_cookie(response, current_user)
    return None


@router.delete("")
def delete_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Permanently delete the current user's account and everything belonging to it."""
    # The cascade lives in account_service because it has to reach far past the user row —
    # projects (including their published public chats), stored provider keys, saved
    # conversations, and uploaded files. Deleting only the user row leaves all of that behind
    # and working, since SQLite doesn't enforce the foreign keys.
    delete_user_account(session, current_user)
    # The auth cookie outlives the account otherwise: the JWT stays validly signed for its full
    # lifetime, and only fails once a request looks the (now missing) user up.
    response.delete_cookie(ACCESS_TOKEN_COOKIE)
    return None
