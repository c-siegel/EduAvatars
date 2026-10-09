"""
Evaluation Tables

A teacher's test sets (EvalTestSet: questions with optional reference answers, EvalTestCase) per
knowledge base, and the runs that answer them through a project and have them scored by the
evaluation service (EvalRun, one EvalRunItem per question). Nothing here comes from students:
the questions are the teacher's own or drafted from their material, and runs aren't saved as
conversations.

A run keeps copies — question, answer, the retrieved passages, a snapshot of the configuration —
so it stays readable after the project or test set changes. Because the passages are copies of
the knowledge base's text, runs are deleted together with the knowledge base (see cleanup.py).

How to use:
    from app.features.evaluation.models import EvalRun

    run = session.get(EvalRun, run_id)
"""

import json
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return str(uuid.uuid4())


class EvalTestSet(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    knowledge_base_id: str = Field(foreign_key="knowledgebase.id", index=True)
    name: str
    # "de" | "en" — the judge's prompts and drafted questions follow it.
    language: str = "de"
    created_at: datetime = Field(default_factory=_now)


class EvalTestCase(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    test_set_id: str = Field(foreign_key="evaltestset.id", index=True)
    # Denormalized from the test set so ownership checks need no join.
    user_id: str = Field(foreign_key="user.id", index=True)
    question: str
    reference: str | None = None
    # "manual" | "csv" | "generated"
    origin: str = "manual"
    # What the question tests (rag-eval/app/schemas.py::QuestionKind): "grounded" (drafted from a
    # passage: retrieval), "topic" (asked about the subject without knowing the material: coverage
    # and gaps), "offtopic" (outside the subject: does the avatar admit it doesn't know).
    kind: str = "grounded"
    # Drafted questions start unapproved: runs only use approved ones, so nothing the judge wrote
    # is measured before the teacher has read it.
    approved: bool = True
    # The knowledge service's passage a drafted question came from, so drafting again picks others.
    source_chunk_id: int | None = None
    created_at: datetime = Field(default_factory=_now)


class EvalRun(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    test_set_id: str = Field(foreign_key="evaltestset.id", index=True)
    # Cleared when the key is deleted; the judge's model stays in config_json.
    judge_api_key_id: str | None = Field(default=None, foreign_key="userapikey.id", index=True)
    # Snapshot at start: project and test set names, LLM, knowledge settings, judge model, metrics.
    config_json: str = "{}"
    metrics_json: str = "[]"
    # Every knowledge base the run's passages can come from (the project's and the test set's),
    # so deleting any of them deletes the run and its copies of their text (see cleanup.py).
    knowledge_base_ids_json: str = "[]"
    # queued | answering | scoring | done | failed | cancelled | interrupted
    status: str = "queued"
    error_code: str | None = None
    case_count: int = 0
    answered_count: int = 0
    scored_count: int = 0
    # Per metric {mean, median, count}, plus latency percentiles — filled when the run ends.
    summary_json: str | None = None
    created_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None

    @property
    def metrics(self) -> list[str]:
        return json.loads(self.metrics_json or "[]")

    @property
    def config(self) -> dict:
        return json.loads(self.config_json or "{}")


class EvalRunItem(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    run_id: str = Field(foreign_key="evalrun.id", index=True)
    # The case it was copied from; None once that case is deleted.
    test_case_id: str | None = None
    position: int = 0
    question: str
    reference: str | None = None
    # Copied from the case, so the summary can be split by kind after the case changes or goes.
    kind: str = "grounded"
    answer: str | None = None
    # [{text, filename, page, score}] — the passages the answer was given, as they were.
    contexts_json: str = "[]"
    # {metric: {value, error}}
    scores_json: str | None = None
    retrieval_ms: float | None = None
    llm_ms: float | None = None
    error_code: str | None = None
