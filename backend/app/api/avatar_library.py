"""
Avatar Model Routes

Lets a user upload, list, and delete their own 3D avatar models and thumbnails, used by the
frontend's TalkingHeadAvatar renderer. Uploaded files are validated by their actual content
(magic bytes), not just their file extension, before being stored.

What is a .glb file?
A .glb file is a single binary file containing a 3D model in the glTF format — this is what
the frontend's three.js-based avatar renderer loads to display and animate the avatar.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.core.config import settings
from app.core.deps import get_current_user, get_current_user_optional, get_session
from app.core.error_codes import ErrorCode
from app.models.avatar_model import AvatarModel
from app.models.project import Project
from app.models.schemas.avatar import AvatarModelOut
from app.models.user import User

router = APIRouter(prefix="/avatar-models", tags=["avatar-library"])

_GLTF_MAGIC = b"glTF"  # first 4 bytes of a real .glb file (binary glTF), per the glTF spec
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB — generous but bounded (HeadTTS avatars are ~4.5 MB)
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024  # 2 MB is plenty for a 256x256 PNG snapshot


def _upload_dir(user_id: str) -> Path:
    return Path(settings.avatar_upload_dir) / user_id


def _thumbnail_dir(user_id: str) -> Path:
    return Path(settings.avatar_thumbnail_upload_dir) / user_id


def _to_out(avatar: AvatarModel) -> AvatarModelOut:
    return AvatarModelOut(
        id=avatar.id,
        name=avatar.name,
        file_url=f"/avatar-models/{avatar.id}/file",
        thumbnail_url=f"/avatar-models/{avatar.id}/thumbnail" if avatar.thumbnail_path else None,
        created_at=avatar.created_at,
    )


@router.get("", response_model=list[AvatarModelOut])
def list_avatar_models(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """List the current user's uploaded avatar models."""
    avatars = session.exec(select(AvatarModel).where(AvatarModel.user_id == current_user.id)).all()
    return [_to_out(a) for a in avatars]


@router.post("", response_model=AvatarModelOut)
async def upload_avatar_model(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Upload a new .glb avatar model file."""
    if not file.filename or not file.filename.lower().endswith(".glb"):
        raise HTTPException(status_code=400, detail=ErrorCode.AVATAR_FILE_INVALID_TYPE)

    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=ErrorCode.AVATAR_FILE_TOO_LARGE)
    # The file extension alone is just a hint from the user, not proof — real glTF binary files
    # start with the 4-byte signature "glTF". This stops arbitrary (possibly malicious) files
    # from being stored and later served back out under a false extension.
    if content[:4] != _GLTF_MAGIC:
        raise HTTPException(status_code=400, detail=ErrorCode.AVATAR_FILE_INVALID_CONTENT)

    # UUID-prefixed filename instead of the original filename (as in the source repo) — avoids
    # collisions and path traversal via the filename.
    stored_filename = f"{uuid.uuid4()}.glb"
    user_dir = _upload_dir(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / stored_filename
    file_path.write_bytes(content)

    avatar = AvatarModel(user_id=current_user.id, name=file.filename.removesuffix(".glb"), file_path=str(file_path))
    session.add(avatar)
    session.commit()
    session.refresh(avatar)
    return _to_out(avatar)


@router.get("/{avatar_id}/file")
def get_avatar_file(
    avatar_id: str,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Serve an avatar's .glb file — to its owner, or anonymously if used in a published project."""
    # Like get_owned_project (deps.py): returns 404 instead of 403 for foreign/inaccessible
    # avatars, to prevent IDOR (Insecure Direct Object Reference) enumeration. Two legitimate
    # access paths: the owning user (avatar library / preview in the configurator, Screen 1e) —
    # or anonymous access, if the avatar is actually used in a published project (public chat,
    # Screen 1i, needs the avatar visible to students, see PublicChat/index.tsx). Unpublished or
    # someone else's avatars stay inaccessible to everyone else.
    avatar = session.get(AvatarModel, avatar_id)
    if avatar is None:
        raise HTTPException(status_code=404, detail=ErrorCode.AVATAR_NOT_FOUND)

    is_owner = current_user is not None and avatar.user_id == current_user.id
    if not is_owner:
        file_url = f"/avatar-models/{avatar_id}/file"
        is_used_publicly = (
            session.exec(
                select(Project).where(Project.avatar_model_url == file_url, Project.published == True)  # noqa: E712
            ).first()
            is not None
        )
        if not is_used_publicly:
            raise HTTPException(status_code=404, detail=ErrorCode.AVATAR_NOT_FOUND)

    return FileResponse(
        avatar.file_path,
        media_type="model/gltf-binary",
        filename=f"{avatar.name}.glb",
        # Safe to cache forever: avatar_id is a UUID and re-uploading always creates a new one
        # (see upload_avatar_model above) — this exact URL's content never changes.
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.post("/{avatar_id}/thumbnail", response_model=AvatarModelOut)
async def set_avatar_thumbnail(
    avatar_id: str,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Attach a thumbnail image to an avatar model."""
    # A PNG rendered client-side from the 3D model, once, by the frontend (see
    # frontend/src/lib/avatarThumbnail.ts) — not an arbitrary user-uploaded image, so the same
    # owner-only check as the model upload itself is enough (no public access needed here, the
    # avatar library is a user-only context).
    avatar = session.get(AvatarModel, avatar_id)
    if avatar is None or avatar.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=ErrorCode.AVATAR_NOT_FOUND)

    content = await file.read(_MAX_THUMBNAIL_BYTES + 1)
    if len(content) > _MAX_THUMBNAIL_BYTES:
        raise HTTPException(status_code=400, detail=ErrorCode.AVATAR_THUMBNAIL_TOO_LARGE)
    if content[:8] != _PNG_MAGIC:
        raise HTTPException(status_code=400, detail=ErrorCode.AVATAR_THUMBNAIL_INVALID)

    stored_filename = f"{uuid.uuid4()}.png"
    thumb_dir = _thumbnail_dir(current_user.id)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumbnail_path = thumb_dir / stored_filename
    thumbnail_path.write_bytes(content)

    avatar.thumbnail_path = str(thumbnail_path)
    session.add(avatar)
    session.commit()
    session.refresh(avatar)
    return _to_out(avatar)


@router.get("/{avatar_id}/thumbnail")
def get_avatar_thumbnail(
    avatar_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Serve an avatar's thumbnail image."""
    avatar = session.get(AvatarModel, avatar_id)
    if avatar is None or avatar.user_id != current_user.id or not avatar.thumbnail_path:
        raise HTTPException(status_code=404, detail=ErrorCode.AVATAR_THUMBNAIL_NOT_FOUND)
    return FileResponse(
        avatar.thumbnail_path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.delete("/{avatar_id}", status_code=204)
def delete_avatar_model(
    avatar_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Delete an avatar model and its thumbnail file."""
    # No protection against "this avatar is currently selected in a project" — a project that
    # still points at the deleted file simply gets a 404 when it tries to load it (already
    # handled by TalkingHeadAvatar, which shows an initials fallback — see
    # components/TalkingHeadAvatar.tsx).
    avatar = session.get(AvatarModel, avatar_id)
    if avatar is None or avatar.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=ErrorCode.AVATAR_NOT_FOUND)

    Path(avatar.file_path).unlink(missing_ok=True)
    if avatar.thumbnail_path:
        Path(avatar.thumbnail_path).unlink(missing_ok=True)

    session.delete(avatar)
    session.commit()
