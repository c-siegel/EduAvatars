"""
Deleting Evaluation Data Along With What It Belongs To

Run items hold copies of a knowledge base's passages and of a project's answers, so they must
not outlive either. Called from the knowledge base, project and account deletes. SQLite runs
without foreign-key enforcement here (see features/users/account.py), so every dependent row is
deleted explicitly. None of these commit: they run inside the caller's transaction.

How to use:
    from app.features.evaluation import cleanup

    cleanup.delete_for_knowledge_base(session, kb.id)
"""

from sqlalchemy import delete
from sqlmodel import Session, select

from app.features.evaluation.models import EvalRun, EvalRunItem, EvalTestCase, EvalTestSet


def _delete_runs(session: Session, run_ids: list[str]) -> None:
    if not run_ids:
        return
    session.execute(delete(EvalRunItem).where(EvalRunItem.run_id.in_(run_ids)))
    session.execute(delete(EvalRun).where(EvalRun.id.in_(run_ids)))


def delete_test_sets(session: Session, test_set_ids: list[str]) -> None:
    """The test sets with their questions and every run that used them."""
    if not test_set_ids:
        return
    _delete_runs(session, list(session.exec(select(EvalRun.id).where(EvalRun.test_set_id.in_(test_set_ids)))))
    session.execute(delete(EvalTestCase).where(EvalTestCase.test_set_id.in_(test_set_ids)))
    session.execute(delete(EvalTestSet).where(EvalTestSet.id.in_(test_set_ids)))


def delete_for_knowledge_base(session: Session, knowledge_base_id: str) -> None:
    """Its test sets, and every run holding passages from it — also runs of a project that used
    it next to the test set's own knowledge base."""
    delete_test_sets(
        session, list(session.exec(select(EvalTestSet.id).where(EvalTestSet.knowledge_base_id == knowledge_base_id)))
    )
    # A JSON list of UUIDs; the quoted ID can't match anything but itself.
    _delete_runs(
        session,
        list(
            session.exec(
                select(EvalRun.id).where(EvalRun.knowledge_base_ids_json.contains(f'"{knowledge_base_id}"'))
            )
        ),
    )


def delete_for_project(session: Session, project_id: str) -> None:
    _delete_runs(session, list(session.exec(select(EvalRun.id).where(EvalRun.project_id == project_id))))


def delete_for_user(session: Session, user_id: str) -> None:
    _delete_runs(session, list(session.exec(select(EvalRun.id).where(EvalRun.user_id == user_id))))
    session.execute(delete(EvalTestCase).where(EvalTestCase.user_id == user_id))
    session.execute(delete(EvalTestSet).where(EvalTestSet.user_id == user_id))


def detach_judge_key(session: Session, key_id: str) -> None:
    """A deleted key leaves finished runs readable; their judge model is in the snapshot."""
    for run in session.exec(select(EvalRun).where(EvalRun.judge_api_key_id == key_id)):
        run.judge_api_key_id = None
        session.add(run)
