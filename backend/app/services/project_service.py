"""
Project CRUD Helpers

Shared logic behind the project routes (app/api/projects.py): listing a user's projects,
deriving the denormalized litellm model string from a project's chosen API key, and applying
partial updates.

How to use:
    from app.services.project_service import list_projects, update_project

    projects = list_projects(session, user_id)
"""

from pathlib import Path

from sqlalchemy import delete
from sqlmodel import Session, select

from app.core.providers import build_model_string
from app.core.security import hash_password
from app.models.api_key import UserApiKey
from app.models.conversation import Conversation
from app.models.project import Project
from app.models.project_access import ProjectAccess


def list_projects(session: Session, user_id: str) -> list[Project]:
    """List all of a user's projects."""
    return list(session.exec(select(Project).where(Project.user_id == user_id)))


def sync_llm_model(session: Session, project: Project) -> None:
    """Derive llm_model from the project's referenced API key.

    The project stores its model choice as a key reference; the litellm model string is
    additionally kept denormalized because analytics (analytics_service.py) and the project
    cards can then avoid a join. Done centrally here so the two never drift apart.
    """
    key = session.get(UserApiKey, project.llm_api_key_id) if project.llm_api_key_id else None
    if key is None or key.user_id != project.user_id or not key.model_id:
        project.llm_model = None
        return
    project.llm_model = build_model_string(key.provider, key.model_id)


# Fields where an explicitly sent null is a deliberate clear (e.g. deselecting a model or
# removing an avatar). For every other field, null is ignored: ProjectUpdate declares every
# field as optional, but a null on title/temperature/... would be a malformed request and would
# fail the DB's NOT NULL constraint anyway.
_CLEARABLE_FIELDS = {
    "llm_api_key_id",
    "avatar_model_url",
    "avatar_background_url",
    "grade_level",
    "tts_voice",
    "tts_api_key_id",
    "stt_api_key_id",
}

# Changing any of these makes a previously generated start-prompt audio file (see api/projects.py's
# start-audio routes) no longer match what it should say/sound like — see update_project below.
_START_AUDIO_INVALIDATING_FIELDS = {"start_prompt", "tts_voice", "tts_api_key_id"}


def delete_project(session: Session, project: Project) -> None:
    """Permanently delete a project together with its saved conversations, access logs, and its
    generated start-prompt audio file.

    The dependent rows have to go explicitly: SQLite runs with foreign-key enforcement off (see
    services/account_service.py), so deleting only the project row would silently orphan every
    student conversation and page view belonging to it. avatar_model_url/avatar_background_url
    aren't touched here — unlike start_audio_path, those point at reusable library assets
    (AvatarModel/BackgroundImage) other projects may still reference, so only their own
    library-delete endpoints (with their own reference checks) may remove those files.
    """
    if project.start_audio_path:
        Path(project.start_audio_path).unlink(missing_ok=True)
    session.execute(delete(Conversation).where(Conversation.project_id == project.id))
    session.execute(delete(ProjectAccess).where(ProjectAccess.project_id == project.id))
    session.delete(project)
    session.commit()


def set_or_clear_chat_password(project: Project, password: str | None) -> None:
    """Set/change (non-empty string) or remove (None) the project's public chat password."""
    project.chat_password_hash = hash_password(password) if password else None


def update_project(session: Session, project: Project, data: dict) -> Project:
    """Apply a partial update to a project (only the fields present in `data`)."""
    # A cached start-prompt audio file is only valid for the exact text/voice/key it was
    # generated with — once any of those changes, the file on disk would say the wrong thing (or
    # in the wrong voice), so drop it and let the "generated?" status in the Configurator go back
    # to "not generated" until the educator regenerates it.
    if project.start_audio_path and any(
        field in data and data[field] != getattr(project, field) for field in _START_AUDIO_INVALIDATING_FIELDS
    ):
        Path(project.start_audio_path).unlink(missing_ok=True)
        project.start_audio_path = None
    for field, value in data.items():
        if value is not None or field in _CLEARABLE_FIELDS:
            setattr(project, field, value)
    if "llm_api_key_id" in data:
        sync_llm_model(session, project)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project
