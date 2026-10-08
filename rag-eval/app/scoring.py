"""
Scoring Answers with Ragas

Each test question gets each requested metric (0 = bad, 1 = good):

| Metric              | Question it answers                                              | Needs     |
|---------------------|------------------------------------------------------------------|-----------|
| faithfulness        | Is every claim in the answer backed by the retrieved passages?    | passages  |
| answer_relevancy    | Does the answer address the question?                            | embedding |
| context_precision   | Are the retrieved passages relevant, the relevant ones first?    | passages  |
| context_recall      | Did retrieval find what the reference answer needs?              | reference |
| factual_correctness | Does the answer agree with the reference answer?                 | reference |

context_precision uses the reference answer when there is one, the generated answer otherwise.
A metric that can't apply to an item (no passages were retrieved, no reference answer) is left
out with a reason instead of being scored as 0, so it doesn't drag averages down unfairly.

Failures are per item and metric: one judge call that times out costs one cell, not the run.
Exception messages are not passed on — they can contain the provider's request, including text.

How to use:
    items = await score_items(request)
"""

import asyncio
import logging
import math

from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecisionWithoutReference,
    ContextPrecisionWithReference,
    ContextRecall,
    FactualCorrectness,
    Faithfulness,
)

from app.config import settings
from app.embeddings import RagServiceEmbedding
from app.judge import make_judge
from app.language import adapt_metric
from app.schemas import MetricScore, ScoredItem, ScoreItem, ScoreRequest

logger = logging.getLogger(__name__)

# Why a metric has no value for an item. The dashboard translates these.
NO_CONTEXTS = "NO_CONTEXTS"
NO_REFERENCE = "NO_REFERENCE"
NO_EMBEDDING = "NO_EMBEDDING"
NOT_SCORABLE = "NOT_SCORABLE"
JUDGE_FAILED = "JUDGE_FAILED"


class _Metrics:
    """The metric objects for one request, built (and translated) once, shared by all items."""

    def __init__(self, request: ScoreRequest) -> None:
        self.request = request
        self.llm = make_judge(request.judge)
        names = set(request.metrics)
        self.faithfulness = Faithfulness(llm=self.llm) if "faithfulness" in names else None
        self.relevancy = (
            AnswerRelevancy(llm=self.llm, embeddings=RagServiceEmbedding(request.embedding))
            if "answer_relevancy" in names and request.embedding
            else None
        )
        self.precision_ref = ContextPrecisionWithReference(llm=self.llm) if "context_precision" in names else None
        self.precision_noref = ContextPrecisionWithoutReference(llm=self.llm) if "context_precision" in names else None
        self.recall = ContextRecall(llm=self.llm) if "context_recall" in names else None
        self.correctness = FactualCorrectness(llm=self.llm) if "factual_correctness" in names else None

    async def adapt(self) -> None:
        for metric in (
            self.faithfulness,
            self.relevancy,
            self.precision_ref,
            self.precision_noref,
            self.recall,
            self.correctness,
        ):
            if metric is not None:
                await adapt_metric(metric, self.request.language, self.llm)


async def _run(metric_name: str, call) -> MetricScore:
    try:
        result = await call()
    except Exception as exc:  # noqa: BLE001 — any judge/provider failure costs this one cell
        logger.warning("Judge call for %s failed: %s", metric_name, type(exc).__name__)
        return MetricScore(value=None, error=JUDGE_FAILED)
    value = float(result.value) if result.value is not None else math.nan
    if math.isnan(value):
        # e.g. faithfulness of an answer without any factual statement ("Hallo!").
        return MetricScore(value=None, error=NOT_SCORABLE)
    return MetricScore(value=round(min(1.0, max(0.0, value)), 4))


async def _score_item(metrics: _Metrics, item: ScoreItem, semaphore: asyncio.Semaphore) -> ScoredItem:
    jobs = {}
    q, a, ctx, ref = item.question, item.answer, item.contexts, item.reference

    def add(name, call):
        async def guarded():
            async with semaphore:
                return await _run(name, call)

        jobs[name] = guarded()

    skipped: dict[str, MetricScore] = {}
    for name in metrics.request.metrics:
        if name == "faithfulness":
            if not ctx:
                skipped[name] = MetricScore(value=None, error=NO_CONTEXTS)
            else:
                add(name, lambda: metrics.faithfulness.ascore(user_input=q, response=a, retrieved_contexts=ctx))
        elif name == "answer_relevancy":
            if metrics.relevancy is None:
                skipped[name] = MetricScore(value=None, error=NO_EMBEDDING)
            else:
                add(name, lambda: metrics.relevancy.ascore(user_input=q, response=a))
        elif name == "context_precision":
            if not ctx:
                skipped[name] = MetricScore(value=None, error=NO_CONTEXTS)
            elif ref:
                add(name, lambda: metrics.precision_ref.ascore(user_input=q, reference=ref, retrieved_contexts=ctx))
            else:
                add(name, lambda: metrics.precision_noref.ascore(user_input=q, response=a, retrieved_contexts=ctx))
        elif name == "context_recall":
            if not ref:
                skipped[name] = MetricScore(value=None, error=NO_REFERENCE)
            elif not ctx:
                # Nothing retrieved: nothing of the reference was found.
                skipped[name] = MetricScore(value=0.0)
            else:
                add(name, lambda: metrics.recall.ascore(user_input=q, retrieved_contexts=ctx, reference=ref))
        elif name == "factual_correctness":
            if not ref:
                skipped[name] = MetricScore(value=None, error=NO_REFERENCE)
            else:
                add(name, lambda: metrics.correctness.ascore(response=a, reference=ref))

    names = list(jobs)
    results = await asyncio.gather(*jobs.values())
    scores = {**skipped, **dict(zip(names, results))}
    return ScoredItem(id=item.id, scores={name: scores[name] for name in metrics.request.metrics})


async def score_items(request: ScoreRequest) -> list[ScoredItem]:
    metrics = _Metrics(request)
    await metrics.adapt()
    semaphore = asyncio.Semaphore(max(1, settings.rag_eval_concurrency))
    return list(await asyncio.gather(*(_score_item(metrics, item, semaphore) for item in request.items)))
