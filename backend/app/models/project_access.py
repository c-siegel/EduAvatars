"""
Project Access Log Table

One row per page view of a published project's public chat — the raw data behind the
analytics dashboard (see app/services/analytics_service.py).

How to use:
    from app.models.project_access import ProjectAccess

    session.add(ProjectAccess(project_id=project_id, visitor_id=visitor_id))
"""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class ProjectAccess(SQLModel, table=True):
    """One page view of a published project's public chat."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    visitor_id: str = Field(index=True)
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
