"""
Background Image Routes

Lets a user upload, list, and delete background images shown behind the avatar in a project's
chat. Uploaded files are validated by their actual content (magic bytes), not just their file
extension, before being stored.

How to use:
    from app.api import background_library

    app.include_router(background_library.router)
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.core.config import settings
from app.core.deps import get_current_user, get_current_user_optional, get_session
from app.core.error_codes import ErrorCode
from app.models.background_image import BackgroundImage
from app.models.project import Project
from app.models.schemas.background import BackgroundImageOut
from app.models.user import User

router = APIRouter(prefix="/backgrounds", tags=["background-library"])

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — generous for a photo, but bounded

_CONTENT_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def _upload_dir(user_id: str) -> Path:
    return Path(settings.background_upload_dir) / user_id


def _detect_extension(content: bytes) -> str | None:
    """Detect PNG/JPEG from the file's magic bytes, or None if neither matches."""
    # Same approach as the .glb avatars: the file extension is just a hint, the real check looks
    # at the magic bytes at the start of the file — stops arbitrary files from being stored under
    # a false extension.
    if content[:8] == _PNG_MAGIC:
        return ".png"
    if content[:3] == _JPEG_MAGIC:
        return ".jpg"
    return None


def _to_out(background: BackgroundImage) -> BackgroundImageOut:
    return BackgroundImageOut(
        id=background.id,
        name=background.name,
        file_url=f"/backgrounds/{background.id}/file",
        created_at=background.created_at,
    )


@router.get("", response_model=list[BackgroundImageOut])
def list_backgrounds(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """List the current user's uploaded background images."""
    backgrounds = session.exec(select(BackgroundImage).where(BackgroundImage.user_id == current_user.id)).all()
    return [_to_out(b) for b in backgrounds]


@router.post("", response_model=BackgroundImageOut)
async def upload_background(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Upload a new background image."""
    if not file.filename or not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(status_code=400, detail=ErrorCode.BACKGROUND_INVALID_TYPE)

    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=ErrorCode.BACKGROUND_FILE_TOO_LARGE)

    extension = _detect_extension(content)
    if extension is None:
        raise HTTPException(status_code=400, detail=ErrorCode.BACKGROUND_INVALID_CONTENT)

    stored_filename = f"{uuid.uuid4()}{extension}"
    user_dir = _upload_dir(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / stored_filename
    file_path.write_bytes(content)

    name = Path(file.filename).stem
    background = BackgroundImage(user_id=current_user.id, name=name, file_path=str(file_path))
    session.add(background)
    session.commit()
    session.refresh(background)
    return _to_out(background)


@router.get("/{background_id}/file")
def get_background_file(
    background_id: str,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Serve a background image — to its owner, or anonymously if used in a published project."""
    # Same access pattern as avatar_library.py::get_avatar_file: the owning user (library /
    # preview in the configurator), or anonymous access if the image is actually used as a
    # background in a published project (the public chat needs it visible).
    background = session.get(BackgroundImage, background_id)
    if background is None:
        raise HTTPException(status_code=404, detail=ErrorCode.BACKGROUND_NOT_FOUND)

    is_owner = current_user is not None and background.user_id == current_user.id
    if not is_owner:
        file_url = f"/backgrounds/{background_id}/file"
        is_used_publicly = (
            session.exec(
                select(Project).where(Project.avatar_background_url == file_url, Project.published == True)  # noqa: E712
            ).first()
            is not None
        )
        if not is_used_publicly:
            raise HTTPException(status_code=404, detail=ErrorCode.BACKGROUND_NOT_FOUND)

    extension = Path(background.file_path).suffix.lower()
    media_type = _CONTENT_TYPES.get(extension, "application/octet-stream")
    return FileResponse(background.file_path, media_type=media_type)


@router.delete("/{background_id}", status_code=204)
def delete_background(
    background_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Delete a background image."""
    # No protection against "this image is currently selected in a project" — a project that
    # still points at it simply gets a 404 on load and falls back to the neutral default surface
    # (the background-color stays visible, see PublicChat.module.css/.avatarStage).
    background = session.get(BackgroundImage, background_id)
    if background is None or background.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=ErrorCode.BACKGROUND_NOT_FOUND)

    Path(background.file_path).unlink(missing_ok=True)
    session.delete(background)
    session.commit()
