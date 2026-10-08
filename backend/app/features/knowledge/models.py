"""
Knowledge Base Tables

A teacher's library of knowledge bases (KnowledgeBase), each a set of uploaded documents
(KnowledgeDocument) that projects can attach (Project.knowledge_base_ids_json). Only metadata
lives here — who owns what, file names, sizes, status. The documents' text, chunks and vectors
live in the optional knowledge service (rag/), addressed by these rows' IDs; the original files
are kept nowhere.

How to use:
    from app.features.knowledge.models import KnowledgeBase, KnowledgeDocument

    kb = session.get(KnowledgeBase, kb_id)
"""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeBase(SQLModel, table=True):
    """One teacher's collection of documents, embedded with one fixed model."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    name: str
    description: str | None = None
    # "local" (the knowledge service's own model, the default) or "api" (one of the teacher's
    # embedding keys). Fixed at creation together with embedding_model: vectors from different
    # models can't be compared, so changing either would make the KB unsearchable.
    embedding_mode: str = "local"
    embedding_api_key_id: str | None = Field(default=None, foreign_key="userapikey.id", index=True)
    # The local model ID, or the litellm model string of the API key at creation time.
    embedding_model: str
    created_at: datetime = Field(default_factory=_now)


class KnowledgeDocument(SQLModel, table=True):
    """One uploaded document; its indexed text lives in the knowledge service."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    knowledge_base_id: str = Field(foreign_key="knowledgebase.id", index=True)
    # Denormalized from the KB so quota sums and ownership checks need no join.
    user_id: str = Field(foreign_key="user.id", index=True)
    # Display label only (sanitised, see features/knowledge/upload_checks.py) — never a path.
    filename: str
    file_type: str
    size_bytes: int
    # Rejects uploading the same file twice into one KB.
    sha256: str = Field(index=True)
    parser: str = "light"
    # queued | processing | ready | failed — mirrored from the knowledge service while not final
    # (see features/knowledge/service.py::refresh_statuses).
    status: str = "queued"
    error_code: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    truncated: bool = False
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class RagPendingDeletion(SQLModel, table=True):
    """A delete the knowledge service couldn't be told about yet (it was unreachable).

    Retried by the periodic task loop (see app/tasks/knowledge_cleanup.py), so a document's
    derived text never outlives the document just because the service was down at that moment.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    # "document" | "knowledge_base"
    kind: str
    target_id: str
    created_at: datetime = Field(default_factory=_now)
