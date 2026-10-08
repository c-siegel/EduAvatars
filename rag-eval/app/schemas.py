"""
Request and Response Bodies of the Internal API

Only the backend calls this service (see app/main.py). The questions, answers and passages it
sends are the teacher's own test material — never saved student conversations.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr

MetricName = Literal["faithfulness", "answer_relevancy", "context_precision", "context_recall", "factual_correctness"]
Language = Literal["de", "en"]


class JudgeConfig(BaseModel):
    """The LLM that scores answers: one of the teacher's own keys, held in memory per request."""

    # litellm model string, e.g. "openai/gpt-4o".
    model: str = Field(min_length=1, max_length=200)
    api_key: SecretStr | None = None
    api_base: str | None = Field(default=None, max_length=500)


class ScoreItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(max_length=20000)
    contexts: list[str] = Field(default_factory=list, max_length=20)
    reference: str | None = Field(default=None, max_length=8000)


class ScoreRequest(BaseModel):
    items: list[ScoreItem] = Field(min_length=1, max_length=20)
    metrics: list[MetricName] = Field(min_length=1)
    judge: JudgeConfig
    # The knowledge base's embedding config, passed on to the knowledge service's /embed —
    # needed only for answer_relevancy.
    embedding: dict[str, Any] | None = None
    language: Language = "de"


class MetricScore(BaseModel):
    # 0..1, None if the metric couldn't be computed for this item (see `error`).
    value: float | None
    error: str | None = None


class ScoredItem(BaseModel):
    id: str
    scores: dict[str, MetricScore]


class ScoreResponse(BaseModel):
    items: list[ScoredItem]


class SourceChunk(BaseModel):
    chunk_id: int
    text: str = Field(min_length=1, max_length=20000)
    heading: str | None = None
    page: int | None = None


class GenerateRequest(BaseModel):
    chunks: list[SourceChunk] = Field(min_length=1, max_length=100)
    size: int = Field(default=10, ge=1, le=50)
    judge: JudgeConfig
    language: Language = "de"


class GeneratedCase(BaseModel):
    question: str
    reference: str
    chunk_id: int


class GenerateResponse(BaseModel):
    cases: list[GeneratedCase]
