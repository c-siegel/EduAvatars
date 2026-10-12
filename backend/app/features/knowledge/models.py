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

from sqlalchemy import UniqueConstraint
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
    # Failed, and the knowledge service still has the original (it keeps it for a while after a
    # failure), so POST /knowledge-documents/{id}/retry can index it again without a re-upload.
    retryable: bool = False
    # Source metadata (features/knowledge/metadata.py), in layers that are combined when read,
    # never copied into each other: the teacher's own entries win over the linked bibliography
    # entry, which wins over the file's own header. So re-importing a bibliography updates every
    # linked document, and clearing a field falls back to the next layer.
    # What the file's header said (text/Markdown only), already mapped to our field names.
    header_json: str | None = None
    # What the teacher entered in the dashboard — only the fields they set.
    meta_json: str | None = None
    # The BibTeX key of the linked bibliography entry (KnowledgeBibEntry), set by the teacher, by
    # the file's header or by an automatic match.
    bibtex_key: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class KnowledgeBibEntry(SQLModel, table=True):
    """One entry of a knowledge base's imported bibliography (features/knowledge/bibtex.py).

    The bibliographic layer of the metadata of every document linked to it by BibTeX key.
    Re-importing replaces a knowledge base's entries; the links stay, as they're by key.
    """

    __table_args__ = (UniqueConstraint("knowledge_base_id", "key"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    knowledge_base_id: str = Field(foreign_key="knowledgebase.id", index=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    key: str
    # Our metadata fields (features/knowledge/metadata.py) plus "files": the attached files'
    # names, for linking documents by file name.
    fields_json: str = "{}"


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
