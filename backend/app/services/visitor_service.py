"""
Visitor Access Logging

Records that an anonymous visitor loaded a published project's public chat page, for analytics
(see app/services/analytics_service.py).

How to use:
    from app.services.visitor_service import log_access

    log_access(session, project.id, visitor_id)
"""

from sqlmodel import Session

from app.models.project_access import ProjectAccess

# Deliberately independent of core/security.py: the public chat page has no user login, only an
# anonymous visitor_id (see app.core.deps.get_or_set_visitor_id).


def log_access(session: Session, project_id: str, visitor_id: str) -> None:
    """Record one visit to a project's public chat page."""
    session.add(ProjectAccess(project_id=project_id, visitor_id=visitor_id))
    session.commit()
