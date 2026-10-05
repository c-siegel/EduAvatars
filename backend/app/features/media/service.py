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
from app.features.media.models import AvatarModel, BackgroundImage
from app.features.projects.models import Project
from app.storage.files import save_file, unlink_quietly


def is_used_by_published_project(session: Session, column, item_id: str, owner_id: str) -> bool:
    """Whether a published project of `owner_id` references `item_id` in `column` (Project.avatar_model_id
    or Project.avatar_background_id) — the condition for serving a library file anonymously, since
    the public chat needs the avatar/background visible to students."""
    # Only the asset owner's own projects count: otherwise anyone could publish a project pointing
    # at a guessed or leaked ID and so make someone else's private upload public.
    query = select(Project).where(column == item_id, Project.published == True, Project.user_id == owner_id)  # noqa: E712
    return session.exec(query).first() is not None


# ==================== AVATARS ====================


def list_avatars(session: Session, user_id: str) -> list[AvatarModel]:
    return list(session.exec(select(AvatarModel).where(AvatarModel.user_id == user_id)).all())


def get_avatar(session: Session, avatar_id: str) -> AvatarModel | None:
    return session.get(AvatarModel, avatar_id)


def get_owned_avatar(session: Session, user_id: str, avatar_id: str) -> AvatarModel | None:
    """The avatar if it exists and belongs to `user_id`, else None."""
    avatar = get_avatar(session, avatar_id)
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


def get_background(session: Session, background_id: str) -> BackgroundImage | None:
    return session.get(BackgroundImage, background_id)


def get_owned_background(session: Session, user_id: str, background_id: str) -> BackgroundImage | None:
    """The background if it exists and belongs to `user_id`, else None."""
    background = get_background(session, background_id)
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
