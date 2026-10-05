"""
Cached Start-Prompt Audio

A project's start_prompt (the avatar's opening line) is synthesized once, on the educator's
request, and stored — so it doesn't need to be re-synthesized on every visitor's chat load.
Invalidated whenever the prompt, voice, or TTS key changes (see service.py::update_project).
"""

from pathlib import Path

from sqlmodel import Session

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.errors import DomainError
from app.features.ai.tts import synthesize_speech
from app.features.api_keys.crypto import scrub_key_from_text
from app.features.api_keys.resolve import resolve_tts_key
from app.features.projects.models import Project
from app.features.users.models import User
from app.storage.files import save_file


class StartPromptRequired(DomainError):
    status_code = 400
    detail = ErrorCode.START_PROMPT_REQUIRED


class TtsNotConfigured(DomainError):
    status_code = 400
    detail = ErrorCode.TTS_NOT_CONFIGURED


def generate_start_audio(session: Session, project: Project) -> Project:
    """Synthesize the project's start_prompt and store it as the project's start audio."""
    if not project.start_prompt or not project.start_prompt.strip():
        raise StartPromptRequired()
    api_key = resolve_tts_key(session, project) if project.tts_enabled else None
    if api_key is None:
        raise TtsNotConfigured()
    try:
        audio_bytes, _content_type = synthesize_speech(
            project.start_prompt, project.tts_voice, api_key, project.spoken_language
        )
    except Exception as exc:
        # The educator's own context — the concrete (key-scrubbed) provider message helps them
        # debug, same as the preview chat.
        raise DomainError(
            status_code=502,
            detail={
                "code": ErrorCode.START_AUDIO_GENERATION_FAILED,
                "message": scrub_key_from_text(str(exc), api_key.encrypted_api_key),
            },
        ) from exc

    # Deterministic filename (not a fresh UUID per generation, unlike the avatar library) —
    # regenerating just overwrites the same file, so there's never a stale one left behind.
    file_path = save_file(Path(settings.start_audio_upload_dir) / project.user_id, f"{project.id}.mp3", audio_bytes)

    project.start_audio_path = str(file_path)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def servable_start_audio_path(session: Session, project_id: str, current_user: User | None) -> str | None:
    """The stored start audio's path if `current_user` may hear it — its owner, or anyone once the
    project is published — else None."""
    project = session.get(Project, project_id)
    if project is None or not project.start_audio_path:
        return None
    is_owner = current_user is not None and project.user_id == current_user.id
    if not is_owner and not project.published:
        return None
    return project.start_audio_path
