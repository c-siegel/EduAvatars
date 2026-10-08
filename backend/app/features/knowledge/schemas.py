"""
Knowledge Base Request/Response Shapes

For features/knowledge/router.py. Nothing here ever carries a document's text except the teacher's
own test search, and nothing ever carries an API key.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.schema import CamelModel


class KnowledgeBaseCreate(CamelModel):
    name: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    # None: the knowledge service's local model (the default). Otherwise one of the teacher's
    # embedding keys — then the documents' text is sent to that provider when indexed.
    embedding_api_key_id: str | None = None


class KnowledgeBaseUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class KnowledgeBaseOut(CamelModel):
    id: str
    name: str
    description: str | None
    embedding_mode: str
    embedding_model: str
    embedding_api_key_id: str | None
    # An API-embedded KB whose key was deleted can't be searched any more (see
    # service.detach_embedding_key) — the dashboard says so instead of failing silently.
    embedding_available: bool
    document_count: int
    size_bytes: int
    used_by_projects: int
    created_at: datetime


class KnowledgeDocumentOut(CamelModel):
    id: str
    knowledge_base_id: str
    filename: str
    file_type: str
    size_bytes: int
    parser: str
    status: Literal["queued", "processing", "ready", "failed"]
    error_code: str | None
    page_count: int | None
    chunk_count: int | None
    truncated: bool
    created_at: datetime


class KnowledgeSearchIn(CamelModel):
    query: str = Field(min_length=1, max_length=2000)


class KnowledgePassageOut(CamelModel):
    chunk_id: int
    document_id: str
    filename: str | None
    text: str
    page: int | None
    heading: str | None
    score: float


class KnowledgeLimitsOut(CamelModel):
    max_upload_mb: int
    max_pages: int
    max_documents_per_kb: int
    max_kb_per_user: int
    user_quota_mb: int


class KnowledgeStatusOut(CamelModel):
    """GET /providers/rag-status — whether the dashboard shows the knowledge features at all."""

    available: bool
    # Whether the knowledge service is actually answering right now (available can be true while
    # the container is down — uploads then fail with a clear error).
    reachable: bool = False
    local_model: str | None = None
    docling_available: bool = False
    file_types: list[str] = []
    limits: KnowledgeLimitsOut | None = None
    usage_bytes: int = 0
