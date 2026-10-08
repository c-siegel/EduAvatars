"""
Configuration Settings for the Evaluation Service

Read from environment variables (.env / docker/docker-compose.yml). The judge LLM's key never
appears here: the backend sends it with every request (see app/schemas.py::JudgeConfig).

How to use:
    from app.config import settings
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_TOKENS = {"", "change-me", "changeme"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    rag_service_token: str = ""
    """Shared secret: required from the backend, and sent to the knowledge service for /embed."""

    rag_service_url: str = "http://rag:8090"
    """The knowledge service, which embeds with a knowledge base's own model (answer relevancy)."""

    rag_eval_data_dir: str = "/data"
    """Cached prompt translations (see app/language.py)."""

    rag_eval_concurrency: int = 4
    """Judge calls in flight at once. Providers rate-limit; more mostly means more 429s."""

    rag_eval_llm_timeout_seconds: float = 120.0
    """Per judge call."""

    @model_validator(mode="after")
    def _require_token(self) -> "Settings":
        if self.rag_service_token.strip().lower() in _PLACEHOLDER_TOKENS:
            raise ValueError("RAG_SERVICE_TOKEN must be set (the same value as the backend's and the knowledge service's)")
        return self


settings = Settings()
