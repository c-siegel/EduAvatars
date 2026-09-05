"""
Deleting a User Account

Removes a user and everything that belongs to them. Kept as its own service because the
deletion has to reach a lot further than the `user` row itself: the app runs on SQLite with
foreign-key enforcement off (the default), so nothing in the database stops dependent rows
from being left behind — a plain `session.delete(user)` succeeds and silently orphans them.

Why that matters (this is what the cascade below fixes)
An orphaned project keeps its `published` flag and its share slug, and `get_published_project`
only ever checks that flag — so the public chat page of a deleted account stays reachable.
Worse, `resolve_llm_key` looks its key up by the project's `user_id`, which still matches the
orphaned `userapikey` row, so that chat keeps decrypting and spending the deleted user's
provider API key. Deleting an account therefore has to take the projects, keys, saved
conversations, access logs, reset tokens, and uploaded files with it.

How to use:
    from app.services.account_service import delete_user_account

    delete_user_account(session, current_user)
"""

from pathlib import Path

from sqlalchemy import delete
from sqlmodel import Session, select

from app.models.api_key import UserApiKey
from app.models.avatar_model import AvatarModel
from app.models.background_image import BackgroundImage
from app.models.conversation import Conversation
from app.models.password_reset_token import PasswordResetToken
from app.models.project import Project
from app.models.project_access import ProjectAccess
from app.models.user import User


def _unlink(path: str | None) -> None:
    """Delete an uploaded file if it's still there."""
    # missing_ok: a file already gone (manually cleaned up, or a failed earlier delete) must not
    # abort the account deletion half-way through.
    if path:
        Path(path).unlink(missing_ok=True)


def delete_user_account(session: Session, user: User) -> None:
    """Permanently delete `user` together with all of their data and uploaded files."""
    # Rows that hang off a project go first, then the projects themselves, then everything that
    # references the user directly — the same order a real ON DELETE CASCADE would use, so the
    # data stays consistent even though SQLite isn't enforcing it (see the module docstring).
    project_ids = [p.id for p in session.exec(select(Project).where(Project.user_id == user.id))]
    if project_ids:
        session.execute(delete(Conversation).where(Conversation.project_id.in_(project_ids)))
        session.execute(delete(ProjectAccess).where(ProjectAccess.project_id.in_(project_ids)))
        session.execute(delete(Project).where(Project.id.in_(project_ids)))

    # The avatar and background rows own files on disk, so these two are looped rather than bulk
    # deleted — the row is only worth removing once its file is gone too.
    for avatar in session.exec(select(AvatarModel).where(AvatarModel.user_id == user.id)):
        _unlink(avatar.file_path)
        _unlink(avatar.thumbnail_path)
        session.delete(avatar)
    for background in session.exec(select(BackgroundImage).where(BackgroundImage.user_id == user.id)):
        _unlink(background.file_path)
        session.delete(background)

    # The stored provider secrets. Encrypted at rest, but leaving them behind would mean an
    # account deletion never actually retires the key it was entrusted with.
    session.execute(delete(UserApiKey).where(UserApiKey.user_id == user.id))
    # Outstanding reset tokens — otherwise a link already sent by email would still resolve to a
    # user id that no longer exists.
    session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))

    _unlink(user.avatar_path)
    session.delete(user)
    session.commit()
