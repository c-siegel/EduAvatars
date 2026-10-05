"""
User Profile Routes

Lets the logged-in user view and edit their own profile: basic fields, a profile picture,
password changes, signing out of all sessions, and deleting the account. The logic lives in
service.py and account.py; these routes handle uploads and the auth cookie.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.core.cookies import clear_auth_cookie, set_auth_cookie
from app.core.deps import get_current_user, get_session
from app.core.error_codes import ErrorCode
from app.features.auth.schemas import UserOut
from app.features.auth.service import user_to_out
from app.features.users import service
from app.features.users.account import delete_user_account
from app.features.users.models import User
from app.features.users.schemas import PasswordChange, ProfileUpdate
from app.storage.files import sniff_image

router = APIRouter(prefix="/profile", tags=["profile"])

_MAX_PICTURE_BYTES = 5 * 1024 * 1024  # 5 MB — a profile photo, not a 3D model


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
    return user_to_out(service.update_profile(session, current_user, data.model_dump(exclude_unset=True)))


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
    # Image signature (first bytes) instead of file extension — see storage/files.py::sniff_image.
    sniffed = sniff_image(content, {"png", "jpeg", "webp"})
    if sniffed is None:
        raise HTTPException(status_code=400, detail=ErrorCode.PROFILE_PICTURE_INVALID_TYPE)
    media_type, ext = sniffed
    return user_to_out(service.set_profile_picture(session, current_user, content, media_type, ext))


@router.delete("/picture", response_model=UserOut)
def delete_profile_picture(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Remove the current user's profile picture."""
    return user_to_out(service.clear_profile_picture(session, current_user))


@router.get("/picture")
def get_profile_picture(current_user: User = Depends(get_current_user)):
    """Serve the current user's own profile picture."""
    # Unlike the avatar models (features/media/avatars_router.py), no ID/IDOR (Insecure Direct
    # Object Reference) check is needed here: this route always serves only the
    # cookie-authenticated user's own picture, there's no ID parameter to spoof.
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
    service.change_password(session, current_user, data.current_password, data.new_password)
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
    service.invalidate_sessions(session, current_user)
    set_auth_cookie(response, current_user)
    return None


@router.delete("")
def delete_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Permanently delete the current user's account and everything belonging to it."""
    # The cascade lives in account.py because it has to reach far past the user row —
    # projects (including their published public chats), stored provider keys, saved
    # conversations, and uploaded files. Deleting only the user row leaves all of that behind
    # and working, since SQLite doesn't enforce the foreign keys.
    delete_user_account(session, current_user)
    # The auth cookie outlives the account otherwise: the JWT stays validly signed for its full
    # lifetime, and only fails once a request looks the (now missing) user up.
    clear_auth_cookie(response)
    return None
