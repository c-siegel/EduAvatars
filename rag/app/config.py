"""
Configuration Settings for the Knowledge (RAG) Service

Typed settings, read from environment variables (set in .env / docker/docker-compose.yml). Only
the operator-level knobs live here: the shared token, where data goes, which local embedding
model runs, and the hard ceilings. The per-upload limits an admin can change in the dashboard
arrive with every request from the backend instead (see DocumentLimits in app/schemas.py) and are
clamped to the ceilings below.

How to use:
    from app.config import settings

    settings.data_dir
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_TOKENS = {"", "change-me", "changeme"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    rag_service_token: str = ""
    """Shared secret the backend sends as a bearer token. Required — the service refuses to start without it."""

    rag_data_dir: str = "/data"
    """Index database and in-flight uploads. A persistent volume in Docker."""

    rag_model_cache_dir: str | None = None
    """Where the local embedding model is downloaded to; defaults to <rag_data_dir>/model-cache."""

    rag_local_embedding_model: str = "jinaai/jina-embeddings-v2-base-de"
    """Local embedding model; must be on the allowlist in app/embedding.py."""

    rag_embedding_threads: int | None = None
    """ONNX threads for the local model; None lets onnxruntime decide (all cores)."""

    docling_url: str | None = None
    """Base URL of an optional docling-serve container; enables the "docling" parser."""

    docling_ocr_engine: str = "easyocr"
    """OCR engine docling-serve uses for scanned pages (easyocr, rapidocr and tesserocr are Apache-2.0)."""

    docling_timeout_seconds: float = 600.0

    # Ceilings for the admin-adjustable limits (backend SiteSettings). The backend validates its
    # values against these (via GET /capabilities), and every request is clamped to them here
    # again, so a buggy or compromised caller can't push this service past what the operator set.
    rag_hard_max_upload_mb: int = 100
    rag_hard_max_pages: int = 2000
    rag_hard_max_chars: int = 10_000_000

    rag_parse_memory_mb: int = 1024
    """Address-space limit for one parser subprocess (see app/parsing/sandbox.py)."""

    rag_parse_timeout_s: int = 120
    """CPU and wall-clock limit for one parser subprocess."""

    rag_ingest_workers: int = 1
    """
    Parallel indexing jobs. One by default: the local model also embeds every chat question, and a
    second ingest job would mostly slow those down rather than finish indexing sooner.
    """

    rag_max_vector_distance: float = 0.75
    """
    Cosine distance above which a vector hit is dropped (0 = identical, 2 = opposite). Keeps
    small talk ("Hallo!") from retrieving random passages. A heuristic — model-dependent.
    """

    @model_validator(mode="after")
    def _require_token(self) -> "Settings":
        if self.rag_service_token.strip().lower() in _PLACEHOLDER_TOKENS:
            raise ValueError(
                "RAG_SERVICE_TOKEN must be set to a random secret (the same value as the backend's), "
                'e.g. python3 -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return self

    @property
    def model_cache_dir(self) -> str:
        return self.rag_model_cache_dir or f"{self.rag_data_dir}/model-cache"


settings = Settings()
