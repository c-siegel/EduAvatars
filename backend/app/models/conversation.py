"""
Conversation Table

One saved chat conversation between a visitor and a published project, kept only if the
project owner enabled Project.save_conversations.

How to use:
    from app.models.conversation import Conversation

    conversations = session.exec(select(Conversation).where(Conversation.project_id == project_id))
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
    # services/visitor_name_service.py) — None for every project that doesn't ask for one.
    visitor_name: str | None = None
    messages_json: str = "[]"
    # Indexed: analytics_service.py orders/filters on both, and retention_service.py deletes
    # WHERE updated_at < cutoff — without an index, both are full-table scans on the
    # fastest-growing table in the app (see the matching alembic migration).
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
