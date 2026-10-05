"""
Project Routes

CRUD (create/read/update/delete) for a user's projects. Publishing, YAML export/import and the
cached start-prompt audio have their own routers next to this one; the configurator's preview
chat lives in app/features/chat/preview_router.py.

What is a "project" here?
A project is one configured AI persona: an avatar, a system prompt, an LLM (large language
model), and optionally TTS (text-to-speech) / STT (speech-to-text). Publishing a project gives
it a public share link that anyone can chat with — see app/features/chat/public_router.py for
those routes.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.deps import get_current_user, get_owned_project, get_session
from app.features.projects import service
from app.features.projects.models import Project
from app.features.projects.schemas import ProjectOut, ProjectUpdate
from app.features.users.models import User

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Create a new project for the current user."""
    return service.create_project(session, current_user.id, data)


@router.get("", response_model=list[ProjectOut])
def get_projects(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """List the current user's projects."""
    return service.list_projects(session, current_user.id)


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
    return service.apply_update(session, project, data)


@router.delete("/{project_id}", status_code=204)
def remove_project(
    project: Project = Depends(get_owned_project),
    session: Session = Depends(get_session),
):
    """Permanently delete a project, including every saved conversation and access log for it."""
    service.delete_project(session, project)
    return None
