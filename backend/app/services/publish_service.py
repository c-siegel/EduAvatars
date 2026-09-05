"""
Publishing Projects

Publishing/unpublishing a project: generates a short, unique share-link slug and flips the
published flag. Every publish mints a NEW slug, so a link that was handed out before is not
silently reactivated later.

How to use:
    from app.services.publish_service import publish_project, unpublish_project

    publish_project(session, project)
"""

import secrets
import string

from sqlmodel import Session, select

from app.models.project import Project

# A 5-character uppercase code, with up to 10 attempts at finding an unused one.
_SLUG_LENGTH = 5
_MAX_ATTEMPTS = 10


def _generate_unique_slug(session: Session) -> str:
    """Generate a random 5-letter slug that isn't already used by another project."""
    # secrets, not random: the slug is the only thing standing between a stranger and an
    # unprotected published chat, so it shouldn't come from a predictable PRNG.
    for _ in range(_MAX_ATTEMPTS):
        candidate = "".join(secrets.choice(string.ascii_uppercase) for _ in range(_SLUG_LENGTH))
        exists = session.exec(select(Project).where(Project.share_slug == candidate)).first()
        if exists is None:
            return candidate
    raise RuntimeError("Konnte keinen eindeutigen Share-Slug generieren.")


def publish_project(session: Session, project: Project) -> Project:
    """Publish a project under a freshly generated share-link slug."""
    # Deliberately a NEW slug on every publish, including a republish: unpublishing is how a
    # teacher takes a chat out of circulation, so the link they already handed out (possibly to a
    # whole class, possibly forwarded onwards) must not start working again by itself. The teacher
    # re-shares the new link with the people who should still have access.
    project.share_slug = _generate_unique_slug(session)
    project.published = True
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def unpublish_project(session: Session, project: Project) -> Project:
    """Unpublish a project; the old share link stops working and is not reused (see publish_project)."""
    project.published = False
    session.add(project)
    session.commit()
    session.refresh(project)
    return project
