"""
Running an Evaluation in the Background

A run first answers every question through the project's real answer path (retrieval, prompt,
LLM — see features/chat/pipeline.py::answer_for_evaluation), one after another, so it never takes
more than one request slot from a class's chats. Then it sends the answers in batches of ten to
the evaluation service for scoring. Progress is committed after every question and batch, so the
dashboard can poll it.

One worker thread for the whole instance: runs wait in line instead of competing for the CPU and
the providers' rate limits. A run whose row disappears (deleted, or its knowledge base or project
deleted) stops at its next step; a cancelled one too. A backend restart ends running runs as
"interrupted" (service.mark_interrupted, called at startup).

How to use:
    runner.submit(run.id)
"""

import dataclasses
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.error_codes import ErrorCode
from app.db.session import engine
from app.features.api_keys.models import UserApiKey
from app.features.chat.pipeline import LLMFailed, answer_for_evaluation, prepare_chat
from app.features.evaluation import eval_client
from app.features.evaluation.models import EvalRun, EvalRunItem, EvalTestSet
from app.features.evaluation.service import EvaluationError, judge_for, run_items, summarize
from app.features.knowledge.models import KnowledgeBase
from app.features.knowledge.service import KnowledgeError, embedding_config
from app.features.projects.models import Project

logger = logging.getLogger(__name__)

SCORE_BATCH_SIZE = 10

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="evaluation")


class _Stopped(Exception):
    """The run was cancelled or deleted while it ran."""


def submit(run_id: str) -> None:
    _executor.submit(execute_run, run_id)


def execute_run(run_id: str) -> None:
    try:
        with Session(engine) as session:
            _execute(session, run_id)
    except _Stopped:
        logger.info("Evaluation run %s stopped (cancelled or deleted)", run_id)
    except Exception as exc:
        # Only the type: a database error's message carries the statement's parameters, which
        # can be answers or passages.
        logger.error("Evaluation run %s failed: %s", run_id, type(exc).__name__)
        with Session(engine) as session:
            _finish(session, run_id, "failed", ErrorCode.EVALUATION_SERVICE_UNAVAILABLE)


def _keys_present(session: Session, run: EvalRun, llm_key_id: str | None) -> bool:
    """A key the teacher deleted mid-run must not be charged any further."""
    if llm_key_id is not None and session.get(UserApiKey, llm_key_id) is None:
        return False
    return run.judge_api_key_id is not None and session.get(UserApiKey, run.judge_api_key_id) is not None


def _current(session: Session, run_id: str) -> EvalRun:
    """The run — raises _Stopped if it was cancelled or deleted meanwhile.

    Reads the status with a query instead of expiring the session, which would throw away the
    item changes not yet committed. Only the columns the runner changes are written back, so a
    cancel in between isn't overwritten.
    """
    status = session.exec(select(EvalRun.status).where(EvalRun.id == run_id)).first()
    if status is None or status in ("cancelled", "done", "failed", "interrupted"):
        raise _Stopped()
    return session.get(EvalRun, run_id)


def _finish(session: Session, run_id: str, status: str, error_code: str | None = None) -> None:
    session.expire_all()
    run = session.get(EvalRun, run_id)
    if run is None or run.status == "cancelled":
        return
    run.status, run.error_code = status, error_code
    run.finished_at = datetime.now(timezone.utc)
    run.summary_json = json.dumps(summarize(run.metrics, run_items(session, run)))
    session.add(run)
    session.commit()


def _contexts(passages) -> list[dict]:
    return [
        {"text": p.text, "filename": p.filename, "page": p.page, "score": round(p.score, 4)} for p in passages
    ]


def _execute(session: Session, run_id: str) -> None:
    run = session.get(EvalRun, run_id)
    if run is None or run.status != "queued":
        return
    project = session.get(Project, run.project_id)
    test_set = session.get(EvalTestSet, run.test_set_id)
    context = prepare_chat(session, project) if project is not None else None
    if context is None or test_set is None:
        _finish(session, run_id, "failed", ErrorCode.NO_LLM_MODEL_SELECTED)
        return
    # Measured like a student's turn, but without speech and without saving a conversation.
    context = dataclasses.replace(context, tts_enabled=False, tts_key=None, voice_clip=None, save_conversations=False)

    run.status = "answering"
    session.add(run)
    session.commit()
    for item in run_items(session, run):
        run = _current(session, run_id)
        if not _keys_present(session, run, context.llm_key.id):
            _finish(session, run_id, "failed", ErrorCode.EVALUATION_KEY_DELETED)
            return
        try:
            answer = answer_for_evaluation(context, item.question)
        except LLMFailed as exc:
            # The provider's message may echo the request; only its type goes to the log.
            logger.warning("Evaluation run %s: answering failed (%s)", run_id, type(exc.__cause__).__name__)
            item.error_code = ErrorCode.EVALUATION_LLM_FAILED
        else:
            item.answer = answer.text
            item.contexts_json = json.dumps(_contexts(answer.passages), ensure_ascii=False)
            item.retrieval_ms, item.llm_ms = answer.retrieval_ms, answer.llm_ms
        run = _current(session, run_id)
        run.answered_count += 1
        session.add_all([item, run])
        session.commit()

    answered = [item for item in run_items(session, run) if item.answer is not None]
    if not answered:
        _finish(session, run_id, "failed", ErrorCode.EVALUATION_LLM_FAILED)
        return

    run = _current(session, run_id)
    run.status = "scoring"
    session.add(run)
    session.commit()
    try:
        judge = judge_for(session, run.user_id, run.judge_api_key_id)
    except EvaluationError:
        _finish(session, run_id, "failed", ErrorCode.EVALUATION_JUDGE_KEY_INVALID)
        return
    embedding = None
    kb = session.get(KnowledgeBase, test_set.knowledge_base_id)
    if "answer_relevancy" in run.metrics and kb is not None:
        try:
            embedding = embedding_config(session, kb)
        except KnowledgeError:
            embedding = None  # answer relevancy is then skipped with NO_EMBEDDING

    for start in range(0, len(answered), SCORE_BATCH_SIZE):
        batch = answered[start : start + SCORE_BATCH_SIZE]
        run = _current(session, run_id)
        if not _keys_present(session, run, None):
            _finish(session, run_id, "failed", ErrorCode.EVALUATION_KEY_DELETED)
            return
        body = {
            "items": [
                {
                    "id": item.id,
                    "question": item.question,
                    "answer": item.answer[:20000],
                    "contexts": [c["text"][:20000] for c in json.loads(item.contexts_json)][:20],
                    "reference": item.reference,
                }
                for item in batch
            ],
            "metrics": run.metrics,
            "judge": judge.config,
            "embedding": embedding,
            "language": test_set.language,
        }
        try:
            scored = {result["id"]: result["scores"] for result in eval_client.score(body)}
        except eval_client.EvalRejected as exc:
            _finish(session, run_id, "failed", exc.code)
            return
        except eval_client.EvalUnavailable:
            _finish(session, run_id, "failed", ErrorCode.EVALUATION_SERVICE_UNAVAILABLE)
            return
        run = _current(session, run_id)
        for item in batch:
            item.scores_json = json.dumps(scored.get(item.id, {}))
            session.add(item)
        run.scored_count += len(batch)
        session.add(run)
        session.commit()

    if _all_judge_calls_failed(session, run):
        _finish(session, run_id, "failed", ErrorCode.EVALUATION_JUDGE_FAILED)
        return
    _finish(session, run_id, "done")


def _all_judge_calls_failed(session: Session, run: EvalRun) -> bool:
    """Every cell JUDGE_FAILED means a wrong key or model, not a bad answer — say so."""
    cells = [
        score
        for item in session.exec(select(EvalRunItem).where(EvalRunItem.run_id == run.id))
        if item.scores_json
        for score in json.loads(item.scores_json).values()
    ]
    return bool(cells) and all(cell.get("error") == "JUDGE_FAILED" for cell in cells)
