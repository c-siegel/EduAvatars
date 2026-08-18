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
    messages_json: str = "[]"
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
