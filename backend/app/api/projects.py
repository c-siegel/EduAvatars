"""
Project Routes

CRUD (create/read/update/delete) for a user's projects, plus publishing, YAML export/import,
and the cached start-prompt audio. The configurator's preview chat lives in
app/features/chat/preview_router.py.

What is a "project" here?
A project is one configured AI persona: an avatar, a system prompt, an LLM (large language
model), and optionally TTS (text-to-speech) / STT (speech-to-text). Publishing a project gives
it a public share link that anyone can chat with — see app/api/public_chat.py for those routes.

How to use:
    from app.api import projects

    app.include_router(projects.router)
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlmodel import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_current_user_optional, get_owned_project, get_session
from app.core.error_codes import ErrorCode
from app.core.providers import KEY_TYPE_LLM, KEY_TYPE_TTS
from app.models.project import Project
from app.models.schemas.project import ProjectOut, ProjectStats, ProjectUpdate
from app.models.user import User
from app.services.analytics_service import get_stats as get_analytics_stats
from app.features.api_keys.resolve import get_owned_key_of_type, resolve_tts_key
from app.features.ai.tts import synthesize_speech
from app.services.project_export_service import (
    MAX_IMPORT_UPLOAD_BYTES,
    ProjectImportError,
    export_filename,
    export_project_yaml,
    import_project,
    parse_project_yaml,
)
from app.services.project_service import (
    delete_project,
    list_projects,
    set_or_clear_chat_password,
    sync_llm_model,
    update_project,
)
from app.services.crypto_service import scrub_key_from_text
from app.services.publish_service import publish_project, unpublish_project
from app.storage.files import save_file

router = APIRouter(prefix="/projects", tags=["projects"])

# Distinguishes "chat_password wasn't in the request at all" (no change) from "it was sent as
# null" (clear/disable) in put_project below — both look like a missing key otherwise.
_NO_CHAT_PASSWORD_SENT = object()


def _require_owned_key_of_type(session: Session, user_id: str, key_id: str, key_type: str) -> None:
    """Raise HTTP 400 unless `key_id` is one of `user_id`'s own API keys of the given type."""
    # Shared check for llm_api_key_id/tts_api_key_id: the key must exist, belong to the calling
    # user, AND be of the matching type — otherwise a TTS key could e.g. be entered as
    # llm_api_key_id (both fields point at the same table).
    if get_owned_key_of_type(session, user_id, key_id, key_type) is None:
        raise HTTPException(status_code=400, detail=ErrorCode.UNKNOWN_API_KEY)


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


@router.post("/import", response_model=ProjectOut)
def import_project_route(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Create a new (draft) project from a previously exported YAML file.

    Registered before GET /{project_id} so "import" is never swallowed as a project id.
    """
    content = file.file.read(MAX_IMPORT_UPLOAD_BYTES + 1)
    if len(content) > MAX_IMPORT_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=ErrorCode.PROJECT_IMPORT_FILE_TOO_LARGE)
    try:
        data = parse_project_yaml(content)
    except ProjectImportError as exc:
        raise HTTPException(status_code=400, detail=ErrorCode.PROJECT_IMPORT_INVALID) from exc
    return import_project(session, current_user.id, data)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project: Project = Depends(get_owned_project)):
    """A single project owned by the current user."""
    return project


@router.get("/{project_id}/export")
def export_project(project: Project = Depends(get_owned_project)):
    """Download a project's configuration as a YAML file, for backup or moving it to another
    eduavatars account. Never includes API keys, the publish state, or the chat password."""
    return Response(
        content=export_project_yaml(project),
        media_type="application/yaml",
        headers={"Content-Disposition": f'attachment; filename="{export_filename(project)}"'},
    )


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


@router.post("/{project_id}/start-audio", response_model=ProjectOut)
def generate_start_audio(
    project: Project = Depends(get_owned_project),
    session: Session = Depends(get_session),
):
    """Synthesize the project's start_prompt once and store it, so it doesn't need to be
    re-synthesized on every visitor's chat load (see public_chat.py::load_tutor)."""
    if not project.start_prompt or not project.start_prompt.strip():
        raise HTTPException(status_code=400, detail=ErrorCode.START_PROMPT_REQUIRED)
    api_key = resolve_tts_key(session, project) if project.tts_enabled else None
    if api_key is None:
        raise HTTPException(status_code=400, detail=ErrorCode.TTS_NOT_CONFIGURED)
    try:
        audio_bytes, _content_type = synthesize_speech(
            project.start_prompt, project.tts_voice, api_key, project.spoken_language
        )
    except Exception as exc:
        raise HTTPException(
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


@router.get("/{project_id}/start-audio")
def get_start_audio(
    project_id: str,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Serve a project's pre-generated start-prompt audio — to its owner, or anonymously if published."""
    # 404 (not 403) for foreign/inaccessible projects, same IDOR (Insecure Direct Object
    # Reference) posture as get_avatar_file in features/media/avatars_router.py.
    project = session.get(Project, project_id)
    if project is None or not project.start_audio_path:
        raise HTTPException(status_code=404, detail=ErrorCode.START_AUDIO_NOT_FOUND)

    is_owner = current_user is not None and project.user_id == current_user.id
    if not is_owner and not project.published:
        raise HTTPException(status_code=404, detail=ErrorCode.START_AUDIO_NOT_FOUND)

    return FileResponse(project.start_audio_path, media_type="audio/mpeg")
