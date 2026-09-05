"""Tests for delete_project's file cleanup (app/services/project_service.py). Deleting a project
used to leave its generated start-prompt audio file (start_audio_path) behind on disk forever —
unlike account deletion, which does unlink every file it owns (see services/account_service.py).
avatar_model_url/avatar_background_url are deliberately NOT covered here: those point at reusable
library assets other projects may still reference, so only their own library-delete endpoints
remove those files."""

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

import app.db.base  # noqa: F401  (registers every model's table on SQLModel.metadata)
from app.models.project import Project
from app.services.project_service import delete_project


def _make_session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_delete_project_removes_its_start_audio_file(tmp_path) -> None:
    audio_path = tmp_path / "start.mp3"
    audio_path.write_bytes(b"fake audio")

    with _make_session() as session:
        project = Project(user_id="user-1", title="Test Project", start_audio_path=str(audio_path))
        session.add(project)
        session.commit()
        session.refresh(project)

        delete_project(session, project)

    assert not audio_path.exists()


def test_delete_project_without_start_audio_does_not_raise(tmp_path) -> None:
    with _make_session() as session:
        project = Project(user_id="user-1", title="Test Project")
        session.add(project)
        session.commit()
        session.refresh(project)

        delete_project(session, project)  # must not raise even with start_audio_path=None
