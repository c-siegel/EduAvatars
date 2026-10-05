"""
Avatar And Background Libraries

Each user's reusable uploads: 3D avatar models (.glb, with an optional client-rendered PNG
thumbnail) and background images shown behind the avatar. Stores the files (see
app/storage/files.py) and their DB rows, and decides who may download them.
"""

import uuid
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import settings
from app.models.avatar_model import AvatarModel
from app.models.background_image import BackgroundImage
from app.models.project import Project
from app.storage.files import save_file, unlink_quietly


def avatar_file_url(avatar_id: str) -> str:
    return f"/avatar-models/{avatar_id}/file"


def avatar_thumbnail_url(avatar_id: str) -> str:
    return f"/avatar-models/{avatar_id}/thumbnail"


def background_file_url(background_id: str) -> str:
    return f"/backgrounds/{background_id}/file"


def is_used_by_published_project(session: Session, column, url: str) -> bool:
    """Whether any published project references `url` in `column` (Project.avatar_model_url or
    Project.avatar_background_url) — the condition for serving a library file anonymously, since
    the public chat needs the avatar/background visible to students."""
    return (
        session.exec(select(Project).where(column == url, Project.published == True)).first()  # noqa: E712
        is not None
    )


# ==================== AVATARS ====================


def list_avatars(session: Session, user_id: str) -> list[AvatarModel]:
    return list(session.exec(select(AvatarModel).where(AvatarModel.user_id == user_id)).all())


def get_owned_avatar(session: Session, user_id: str, avatar_id: str) -> AvatarModel | None:
    """The avatar if it exists and belongs to `user_id`, else None."""
    avatar = session.get(AvatarModel, avatar_id)
    if avatar is None or avatar.user_id != user_id:
        return None
    return avatar


def create_avatar(session: Session, user_id: str, name: str, content: bytes) -> AvatarModel:
    """Store an already-validated .glb file and its library entry."""
    # UUID filename instead of the original filename — avoids collisions and path traversal via
    # the filename.
    file_path = save_file(Path(settings.avatar_upload_dir) / user_id, f"{uuid.uuid4()}.glb", content)
    avatar = AvatarModel(user_id=user_id, name=name, file_path=str(file_path))
    session.add(avatar)
    session.commit()
    session.refresh(avatar)
    return avatar


def set_avatar_thumbnail(session: Session, avatar: AvatarModel, content: bytes) -> AvatarModel:
    """Store an already-validated PNG thumbnail for `avatar`."""
    thumbnail_path = save_file(
        Path(settings.avatar_thumbnail_upload_dir) / avatar.user_id, f"{uuid.uuid4()}.png", content
    )
    avatar.thumbnail_path = str(thumbnail_path)
    session.add(avatar)
    session.commit()
    session.refresh(avatar)
    return avatar


def delete_avatar(session: Session, avatar: AvatarModel) -> None:
    """Delete an avatar's files and its library entry."""
    # No protection against "this avatar is currently selected in a project" — a project that
    # still points at the deleted file simply gets a 404 when it tries to load it (already
    # handled by TalkingHeadAvatar, which shows an initials fallback — see
    # components/TalkingHeadAvatar.tsx).
    unlink_quietly(avatar.file_path)
    unlink_quietly(avatar.thumbnail_path)
    session.delete(avatar)
    session.commit()


# ==================== BACKGROUNDS ====================


def list_backgrounds(session: Session, user_id: str) -> list[BackgroundImage]:
    return list(session.exec(select(BackgroundImage).where(BackgroundImage.user_id == user_id)).all())


def get_owned_background(session: Session, user_id: str, background_id: str) -> BackgroundImage | None:
    """The background if it exists and belongs to `user_id`, else None."""
    background = session.get(BackgroundImage, background_id)
    if background is None or background.user_id != user_id:
        return None
    return background


def create_background(session: Session, user_id: str, name: str, content: bytes, extension: str) -> BackgroundImage:
    """Store an already-validated image (extension taken from its sniffed content) and its library entry."""
    file_path = save_file(Path(settings.background_upload_dir) / user_id, f"{uuid.uuid4()}{extension}", content)
    background = BackgroundImage(user_id=user_id, name=name, file_path=str(file_path))
    session.add(background)
    session.commit()
    session.refresh(background)
    return background


def delete_background(session: Session, background: BackgroundImage) -> None:
    """Delete a background's file and its library entry."""
    # No protection against "this image is currently selected in a project" — a project that
    # still points at it simply gets a 404 on load and falls back to the neutral default surface
    # (the background-color stays visible, see PublicChat.module.css/.avatarStage).
    unlink_quietly(background.file_path)
    session.delete(background)
    session.commit()
