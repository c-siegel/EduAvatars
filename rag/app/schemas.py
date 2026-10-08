"""
Request and Response Bodies of the Internal API

Only the backend talks to this service (see app/main.py). IDs are opaque strings the backend
generated; this service never learns who owns what.
"""

from typing import Literal

from pydantic import BaseModel, Field, SecretStr

from app.config import settings

# Backend IDs are UUIDs; the pattern keeps anything path- or SQL-like out of log lines and file
# names (incoming uploads are stored as <data_dir>/incoming/<document_id>).
ID_PATTERN = r"^[A-Za-z0-9-]{1,64}$"


class EmbeddingConfig(BaseModel):
    """Which model embeds a knowledge base. Fixed when the KB is created (see app/store.py)."""

    mode: Literal["local", "api"]
    # Local: a model ID from the allowlist in app/embedding.py. API: a litellm model string,
    # e.g. "openai/text-embedding-3-small".
    model: str = Field(min_length=1, max_length=200)
    # Only for "api". Kept in memory for the duration of one request or ingest job, never stored
    # or logged (SecretStr keeps it out of reprs and validation errors).
    api_key: SecretStr | None = None
    api_base: str | None = Field(default=None, max_length=500)


class DocumentLimits(BaseModel):
    """The admin's current limits (backend SiteSettings), clamped to this service's ceilings."""

    max_upload_mb: int = Field(default=20, ge=1)
    max_pages: int = Field(default=500, ge=1)
    max_chars: int = Field(default=2_000_000, ge=1000)

    def clamped(self) -> "DocumentLimits":
        return DocumentLimits(
            max_upload_mb=min(self.max_upload_mb, settings.rag_hard_max_upload_mb),
            max_pages=min(self.max_pages, settings.rag_hard_max_pages),
            max_chars=min(self.max_chars, settings.rag_hard_max_chars),
        )


class DocumentMeta(BaseModel):
    """The JSON "meta" form field next to an uploaded file."""

    document_id: str = Field(pattern=ID_PATTERN)
    knowledge_base_id: str = Field(pattern=ID_PATTERN)
    filename: str = Field(min_length=1, max_length=255)
    parser: Literal["light", "docling"] = "light"
    embedding: EmbeddingConfig
    limits: DocumentLimits = DocumentLimits()


class DocumentStatus(BaseModel):
    document_id: str
    status: Literal["queued", "processing", "ready", "failed"]
    error_code: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    char_count: int | None = None
    truncated: bool = False
    # Failed, and the original is still here: POST /documents/{id}/retry can process it again.
    retryable: bool = False


class StatusRequest(BaseModel):
    document_ids: list[str] = Field(max_length=500)


class RetryRequest(BaseModel):
    """Like DocumentMeta, minus the IDs: the parser may change (e.g. to Docling for a scan), the
    embedding config is needed again because API keys are never stored here."""

    parser: Literal["light", "docling"] = "light"
    embedding: EmbeddingConfig
    limits: DocumentLimits = DocumentLimits()


class QueryRequest(BaseModel):
    knowledge_base_ids: list[str] = Field(min_length=1, max_length=20)
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=20)
    embedding: EmbeddingConfig


class Passage(BaseModel):
    chunk_id: int
    document_id: str
    knowledge_base_id: str
    text: str
    page: int | None
    heading: str | None
    score: float


class QueryResponse(BaseModel):
    passages: list[Passage]


class EmbeddingTestRequest(BaseModel):
    embedding: EmbeddingConfig


class EmbeddingTestResponse(BaseModel):
    dimensions: int


class HardLimits(BaseModel):
    max_upload_mb: int
    max_pages: int
    max_chars: int


class Capabilities(BaseModel):
    local_model: str
    local_model_dimensions: int
    file_types: list[str]
    hard_limits: HardLimits
    docling_available: bool
