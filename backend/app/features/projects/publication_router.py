"""
Project Publishing Routes

A project's publication is its public share link: PUT creates it (always a fresh link, see
publish.py), DELETE takes the project out of circulation.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.deps import get_owned_project, get_session
from app.features.projects.models import Project
from app.features.projects.publish import publish_project, unpublish_project
from app.features.projects.schemas import ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.put("/{project_id}/publication", response_model=ProjectOut)
def publish(project: Project = Depends(get_owned_project), session: Session = Depends(get_session)):
    """Publish a project, making it reachable via its public share link."""
    return publish_project(session, project)


@router.delete("/{project_id}/publication", response_model=ProjectOut)
def unpublish(project: Project = Depends(get_owned_project), session: Session = Depends(get_session)):
    """Unpublish a project, removing public access."""
    return unpublish_project(session, project)
