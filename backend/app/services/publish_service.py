"""
Publishing Projects

Publishing/unpublishing a project: generates a short, unique share-link slug on first publish
and flips the published flag. Unpublishing keeps the slug, so republishing reactivates the same
link.

How to use:
    from app.services.publish_service import publish_project, unpublish_project

    publish_project(session, project)
"""

import random
import string

from sqlmodel import Session, select

from app.models.project import Project

# Business logic carried over 1:1 from the source repo: a 5-character uppercase code, up to 10
# attempts at uniqueness, the slug is kept across re-publishing (never regenerated).
_SLUG_LENGTH = 5
_MAX_ATTEMPTS = 10


def _generate_unique_slug(session: Session) -> str:
    """Generate a random 5-letter slug that isn't already used by another project."""
    for _ in range(_MAX_ATTEMPTS):
        candidate = "".join(random.choices(string.ascii_uppercase, k=_SLUG_LENGTH))
        exists = session.exec(select(Project).where(Project.share_slug == candidate)).first()
        if exists is None:
            return candidate
    raise RuntimeError("Konnte keinen eindeutigen Share-Slug generieren.")


def publish_project(session: Session, project: Project) -> Project:
    """Publish a project, generating its share-link slug on first publish."""
    if project.share_slug is None:
        project.share_slug = _generate_unique_slug(session)
    project.published = True
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def unpublish_project(session: Session, project: Project) -> Project:
    """Unpublish a project; its share-link slug is kept for a future republish."""
    # The slug is kept so a republish reactivates the same link.
    project.published = False
    session.add(project)
    session.commit()
    session.refresh(project)
    return project
