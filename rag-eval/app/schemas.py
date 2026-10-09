"""
Request and Response Bodies of the Internal API

Only the backend calls this service (see app/main.py). The questions, answers and passages it
sends are the teacher's own test material — never saved student conversations.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, model_validator

MetricName = Literal[
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "factual_correctness",
    "coverage",
    "restraint",
]
Language = Literal["de", "en"]
# Where a test question comes from, which decides what it can tell us (see app/scoring.py):
#   grounded  drafted from a passage of the material — tests retrieval
#   topic     asked about the subject without knowing the material — tests coverage (gaps)
#   offtopic  outside the subject — tests whether the avatar admits what it doesn't know
QuestionKind = Literal["grounded", "topic", "offtopic"]


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
    kind: QuestionKind = "grounded"


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


class TopicContext(BaseModel):
    """What the questions are about, without any of the material's content: the avatar's own
    instructions, the descriptions the teacher wrote and the titles of the uploaded documents."""

    preprompt: str = Field(default="", max_length=8000)
    project_title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)
    document_titles: list[str] = Field(default_factory=list, max_length=50)
    objectives: str = Field(default="", max_length=2000)
    # Questions the test set already has, so new ones don't repeat them.
    existing_questions: list[str] = Field(default_factory=list, max_length=40)


class GenerateRequest(BaseModel):
    kind: QuestionKind = "grounded"
    # grounded: the sampled passages. topic/offtopic: none — the point is not to know them.
    chunks: list[SourceChunk] = Field(default_factory=list, max_length=100)
    topic: TopicContext | None = None
    size: int = Field(default=10, ge=1, le=50)
    judge: JudgeConfig
    language: Language = "de"

    @model_validator(mode="after")
    def _check_inputs(self) -> "GenerateRequest":
        if self.kind == "grounded" and not self.chunks:
            raise ValueError("chunks are required for grounded questions")
        if self.kind != "grounded" and self.topic is None:
            raise ValueError("topic is required for topic and offtopic questions")
        return self


class GeneratedCase(BaseModel):
    question: str
    # Only grounded questions have one: for the others there is nothing in the material to take it from.
    reference: str | None = None
    chunk_id: int | None = None


class GenerateResponse(BaseModel):
    cases: list[GeneratedCase]
