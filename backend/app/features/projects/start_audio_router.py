"""
Start-Prompt Audio Routes

Generate (owner only) and serve (owner, or anyone once published) a project's cached
start-prompt audio — see start_audio.py.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.core.deps import get_current_user_optional, get_owned_project, get_session
from app.core.error_codes import ErrorCode
from app.features.projects import start_audio
from app.features.projects.models import Project
from app.features.projects.schemas import ProjectOut
from app.features.users.models import User

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/{project_id}/start-audio", response_model=ProjectOut)
def generate_start_audio(
    project: Project = Depends(get_owned_project),
    session: Session = Depends(get_session),
):
    """Synthesize the project's start_prompt once and store it, so it doesn't need to be
    re-synthesized on every visitor's chat load (see features/chat/public_router.py::load_tutor)."""
    return start_audio.generate_start_audio(session, project)


@router.get("/{project_id}/start-audio")
def get_start_audio(
    project_id: str,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Serve a project's pre-generated start-prompt audio — to its owner, or anonymously if published."""
    # 404 (not 403) for foreign/inaccessible projects, same IDOR (Insecure Direct Object
    # Reference) posture as get_avatar_file in features/media/avatars_router.py.
    servable = start_audio.servable_start_audio(session, project_id, current_user)
    if servable is None:
        raise HTTPException(status_code=404, detail=ErrorCode.START_AUDIO_NOT_FOUND)
    path, media_type = servable
    return FileResponse(path, media_type=media_type)
