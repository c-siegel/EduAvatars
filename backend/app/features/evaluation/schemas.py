"""
Evaluation Request/Response Shapes

For features/evaluation/router.py. Test material and run results are the teacher's own; nothing
here carries an API key or anything from a student.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.schema import CamelModel

MetricName = Literal["faithfulness", "answer_relevancy", "context_precision", "context_recall", "factual_correctness"]
Language = Literal["de", "en"]


class EvaluationStatusOut(CamelModel):
    available: bool
    reachable: bool = False
    ragas_version: str | None = None
    max_cases_per_run: int | None = None
    max_drafts_per_request: int | None = None
    metrics: list[str] = []
    # For the cost estimate shown before a run: judge calls per question and metric
    # (context_precision: per retrieved passage).
    judge_calls_per_metric: dict[str, int] = {}


class TestSetCreate(CamelModel):
    name: str = Field(max_length=200)
    language: Language = "de"


class TestSetUpdate(CamelModel):
    name: str | None = Field(default=None, max_length=200)
    language: Language | None = None


class TestSetOut(CamelModel):
    id: str
    knowledge_base_id: str
    name: str
    language: str
    case_count: int
    approved_count: int
    created_at: datetime


class TestCaseCreate(CamelModel):
    question: str = Field(max_length=4000)
    reference: str | None = Field(default=None, max_length=8000)


class TestCaseUpdate(CamelModel):
    question: str | None = Field(default=None, max_length=4000)
    reference: str | None = Field(default=None, max_length=8000)
    approved: bool | None = None


class TestCaseOut(CamelModel):
    id: str
    test_set_id: str
    question: str
    reference: str | None
    origin: str
    approved: bool
    created_at: datetime


class CsvImportOut(CamelModel):
    imported: int
    skipped: int


class GenerateIn(CamelModel):
    judge_api_key_id: str
    size: int = Field(default=10, ge=1, le=10)


class RunCreate(CamelModel):
    project_id: str
    test_set_id: str
    judge_api_key_id: str
    metrics: list[MetricName] = Field(min_length=1)


class RunKnowledgeBaseOut(CamelModel):
    name: str
    embedding_model: str | None = None


class RunConfigOut(CamelModel):
    """The snapshot taken when the run started (service._snapshot)."""

    project_title: str | None = None
    llm: str | None = None
    temperature: float | None = None
    knowledge_mode: str | None = None
    top_k: int | None = None
    knowledge_bases: list[RunKnowledgeBaseOut] = []
    test_set_name: str | None = None
    test_set_knowledge_base: str | None = None
    language: str | None = None
    judge: str | None = None
    metrics: list[str] = []


class MetricSummaryOut(CamelModel):
    mean: float | None
    median: float | None
    count: int


class LatencyOut(CamelModel):
    p50: float | None
    p90: float | None


class RunSummaryOut(CamelModel):
    metrics: dict[str, MetricSummaryOut]
    retrieval_ms: LatencyOut
    llm_ms: LatencyOut


class RunOut(CamelModel):
    id: str
    project_id: str
    test_set_id: str
    status: str
    error_code: str | None
    metrics: list[str]
    config: RunConfigOut
    case_count: int
    answered_count: int
    scored_count: int
    summary: RunSummaryOut | None
    created_at: datetime
    finished_at: datetime | None


class RunContextOut(CamelModel):
    text: str
    filename: str | None = None
    page: int | None = None
    score: float | None = None


class MetricScoreOut(CamelModel):
    value: float | None
    error: str | None = None


class RunItemOut(CamelModel):
    id: str
    position: int
    question: str
    reference: str | None
    answer: str | None
    contexts: list[RunContextOut]
    scores: dict[str, MetricScoreOut]
    retrieval_ms: float | None
    llm_ms: float | None
    error_code: str | None


class RunDetailOut(RunOut):
    items: list[RunItemOut]
