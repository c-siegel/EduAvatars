"""
Chat Activity Tables

What the public chat records: one row per page view (ProjectAccess) and, for projects with
save_conversations enabled, each visitor's saved conversation (Conversation). Read by the
analytics feature, purged by the retention task.
"""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Conversation(SQLModel, table=True):
    """One visitor's saved conversation with a published project."""

    # Only created if Project.save_conversations is enabled.
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    visitor_id: str = Field(index=True)
    # Visitor-entered name/ID, only asked for if Project.require_visitor_name is set (see
    # features/chat/visitor_name.py) — None for every project that doesn't ask for one.
    visitor_name: str | None = None
    messages_json: str = "[]"
    # Indexed: features/analytics/service.py orders/filters on both, and tasks/retention.py deletes
    # WHERE updated_at < cutoff — without an index, both are full-table scans on the
    # fastest-growing table in the app (see the matching alembic migration).
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class ProjectAccess(SQLModel, table=True):
    """One page view of a published project's public chat."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    visitor_id: str = Field(index=True)
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
