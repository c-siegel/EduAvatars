"""
Project Routes

CRUD (create/read/update/delete) for a user's projects, plus publishing, a live preview chat
used while configuring a project, and voice-message transcription for that preview.

What is a "project" here?
A project is one configured AI persona: an avatar, a system prompt, an LLM (large language
model), and optionally TTS (text-to-speech) / STT (speech-to-text). Publishing a project gives
it a public share link that anyone can chat with — see app/api/public_chat.py for those routes.

How to use:
    from app.api import projects

    app.include_router(projects.router)
"""

import base64

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlmodel import Session

from app.core.deps import get_current_user, get_owned_project, get_session
from app.core.error_codes import ErrorCode
from app.core.providers import KEY_TYPE_LLM, KEY_TYPE_TTS
from app.models.project import Project
from app.models.schemas.project import (
    PreviewMessageRequest,
    PreviewMessageResponse,
    ProjectOut,
    ProjectStats,
    ProjectUpdate,
)
from app.models.schemas.speech import TranscriptionOut
from app.models.user import User
from app.services.analytics_service import get_stats as get_analytics_stats
from app.services.api_key_service import (
    get_owned_key_of_type,
    resolve_llm_key,
    resolve_tts_key,
)
from app.services.llm_service import send_chat_message
from app.services.project_service import (
    delete_project,
    list_projects,
    set_or_clear_chat_password,
    sync_llm_model,
    update_project,
)
from app.services.publish_service import publish_project, unpublish_project
from app.services.stt_service import transcribe_audio
from app.services.tts_service import synthesize_speech

router = APIRouter(prefix="/projects", tags=["projects"])

# Distinguishes "chat_password wasn't in the request at all" (no change) from "it was sent as
# null" (clear/disable) in put_project below — both look like a missing key otherwise.
_NO_CHAT_PASSWORD_SENT = object()

_MAX_AUDIO_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — individual chat voice messages are short
_ALLOWED_AUDIO_CONTENT_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/mpeg"}


def _require_owned_key_of_type(session: Session, user_id: str, key_id: str, key_type: str) -> None:
    """Raise HTTP 400 unless `key_id` is one of `user_id`'s own API keys of the given type."""
    # Shared check for llm_api_key_id/tts_api_key_id: the key must exist, belong to the calling
    # user, AND be of the matching type — otherwise a TTS key could e.g. be entered as
    # llm_api_key_id (both fields point at the same table).
    if get_owned_key_of_type(session, user_id, key_id, key_type) is None:
        raise HTTPException(status_code=400, detail=ErrorCode.UNKNOWN_API_KEY)


def _synthesize_if_enabled(session: Session, project: Project, text: str) -> tuple[str | None, str | None]:
    """Generate speech for `text` if the project has TTS enabled and a usable key; never raises."""
    # Speech output is an addition to the text reply — if it fails (no key, provider error), the
    # user still gets the text back, instead of a 500/502 just because of the audio generation.
    if not project.tts_enabled:
        return None, None
    api_key = resolve_tts_key(session, project)
    if api_key is None:
        return None, None
    try:
        audio_bytes, content_type = synthesize_speech(text, project.tts_voice, api_key)
    except Exception:
        return None, None
    return base64.b64encode(audio_bytes).decode(), content_type


@router.post("", response_model=ProjectOut)
def create_project(
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Create a new project for the current user."""
    # Uses ProjectUpdate instead of a separate ProjectCreate schema: every field is optional
    # anyway and the DB model has a default for everything except title/user_id (see
    # models/project.py) — the frontend always sends a title on creation ("+ New project") anyway.
    if data.llm_api_key_id:
        _require_owned_key_of_type(session, current_user.id, data.llm_api_key_id, KEY_TYPE_LLM)
    if data.tts_api_key_id:
        _require_owned_key_of_type(session, current_user.id, data.tts_api_key_id, KEY_TYPE_TTS)
    create_data = data.model_dump(exclude_unset=True)
    chat_password = create_data.pop("chat_password", _NO_CHAT_PASSWORD_SENT)
    project = Project(user_id=current_user.id, **create_data)
    if chat_password is not _NO_CHAT_PASSWORD_SENT:
        set_or_clear_chat_password(project, chat_password)
    sync_llm_model(session, project)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def get_projects(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """List the current user's projects."""
    return list_projects(session, current_user.id)


@router.get("/stats", response_model=ProjectStats)
def get_stats(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Summary stats (project count, published count, sessions/messages this week) for the current user."""
    projects = list_projects(session, current_user.id)
    weekly = get_analytics_stats(session, current_user.id, days=7)
    return ProjectStats(
        total_projects=len(projects),
        published_projects=sum(1 for p in projects if p.published),
        sessions_last_7_days=weekly.sessions,
        messages_last_7_days=weekly.messages,
    )


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project: Project = Depends(get_owned_project)):
    """A single project owned by the current user."""
    return project


@router.put("/{project_id}", response_model=ProjectOut)
def put_project(
    data: ProjectUpdate,
    project: Project = Depends(get_owned_project),
    session: Session = Depends(get_session),
):
    """Update a project owned by the current user."""
    # A project may only point at one of the user's own keys — otherwise a user could enter
    # someone else's key ID (it could never actually be used, see resolve_llm_key, but the
    # reference wouldn't belong in the DB either way).
    if data.llm_api_key_id:
        _require_owned_key_of_type(session, project.user_id, data.llm_api_key_id, KEY_TYPE_LLM)
    if data.tts_api_key_id:
        _require_owned_key_of_type(session, project.user_id, data.tts_api_key_id, KEY_TYPE_TTS)
    update_data = data.model_dump(exclude_unset=True)
    chat_password = update_data.pop("chat_password", _NO_CHAT_PASSWORD_SENT)
    if chat_password is not _NO_CHAT_PASSWORD_SENT:
        set_or_clear_chat_password(project, chat_password)
    return update_project(session, project, update_data)


@router.delete("/{project_id}", status_code=204)
def remove_project(
    project: Project = Depends(get_owned_project),
    session: Session = Depends(get_session),
):
    """Permanently delete a project, including every saved conversation and access log for it."""
    delete_project(session, project)
    return None


@router.post("/{project_id}/publish", response_model=ProjectOut)
def publish(project: Project = Depends(get_owned_project), session: Session = Depends(get_session)):
    """Publish a project, making it reachable via its public share link."""
    return publish_project(session, project)


@router.post("/{project_id}/unpublish", response_model=ProjectOut)
def unpublish(project: Project = Depends(get_owned_project), session: Session = Depends(get_session)):
    """Unpublish a project, removing public access."""
    return unpublish_project(session, project)


@router.post("/{project_id}/preview-message", response_model=PreviewMessageResponse)
def preview_message(
    data: PreviewMessageRequest,
    project: Project = Depends(get_owned_project),
    session: Session = Depends(get_session),
):
    """Send a message to the project's configured LLM and return the reply, for the in-app preview chat."""
    # Live preview chat in the configurator (Screen 1e) — uses the user's own API key.
    api_key = resolve_llm_key(session, project)
    if api_key is None:
        raise HTTPException(status_code=400, detail=ErrorCode.NO_LLM_MODEL_SELECTED)
    try:
        history = [{"role": h.role, "content": h.content} for h in data.history]
        reply = send_chat_message(
            project.preprompt or "", data.message, api_key, project.creativity, project.start_prompt, history
        )
    except Exception as exc:
        # This is the user's own context (the configurator) — the concrete error message helps
        # with debugging (wrong/expired key, wrong model, ...), unlike in the public chat. `code`
        # gets translated on the frontend (see errorMessage() in api/client.ts); `message` is the
        # raw provider exception, appended untranslated since it's already technical/English.
        raise HTTPException(
            status_code=502, detail={"code": ErrorCode.LLM_REQUEST_FAILED, "message": str(exc)}
        ) from exc
    audio_base64, content_type = _synthesize_if_enabled(session, project, reply)
    return PreviewMessageResponse(reply=reply, audio_base64=audio_base64, content_type=content_type)


@router.post("/{project_id}/transcribe", response_model=TranscriptionOut)
async def transcribe(
    audio: UploadFile,
    project: Project = Depends(get_owned_project),
):
    """Transcribe a voice message for the in-app preview chat."""
    if not project.stt_enabled:
        raise HTTPException(status_code=400, detail=ErrorCode.VOICE_INPUT_DISABLED)
    if audio.content_type not in _ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=ErrorCode.UNSUPPORTED_AUDIO_FORMAT)
    content = await audio.read(_MAX_AUDIO_UPLOAD_BYTES + 1)
    if len(content) > _MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=ErrorCode.AUDIO_FILE_TOO_LARGE)

    try:
        text = transcribe_audio(content)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail={"code": ErrorCode.STT_REQUEST_FAILED, "message": str(exc)}
        ) from exc
    return TranscriptionOut(text=text)
