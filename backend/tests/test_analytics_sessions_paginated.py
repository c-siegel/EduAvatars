"""Tests for get_sessions_paginated (app/services/analytics_service.py). Used to look up each
row's Project via a separate session.get() call per conversation — an N+1 query pattern, since
Project is already joined into the same query for its WHERE filters. Selecting Project.title
alongside Conversation instead should return identical results from a single query."""

import json
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

import app.db.base  # noqa: F401  (registers every model's table on SQLModel.metadata)
from app.models.conversation import Conversation
from app.models.project import Project
from app.services.analytics_service import get_sessions_paginated


def _make_session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _conversation(project_id: str, started_at: datetime, messages: list[dict]) -> Conversation:
    return Conversation(
        project_id=project_id,
        visitor_id="visitor-1",
        messages_json=json.dumps(messages),
        started_at=started_at,
        updated_at=started_at,
    )


def test_returns_project_title_and_correct_pagination() -> None:
    with _make_session() as session:
        project = Project(user_id="user-1", title="My Tutor")
        session.add(project)
        session.commit()
        session.refresh(project)

        now = datetime.now(timezone.utc)
        for i in range(3):
            session.add(
                _conversation(
                    project.id,
                    now - timedelta(minutes=i),
                    [{"role": "user", "content": f"Question {i}"}],
                )
            )
        session.commit()

        result = get_sessions_paginated(session, "user-1", page=1, per_page=2)

        assert result["total"] == 3
        assert len(result["items"]) == 2
        assert all(item.project_title == "My Tutor" for item in result["items"])
        # Most recent first (order_by started_at.desc()).
        assert result["items"][0].last_question == "Question 0"


def test_second_page_returns_the_remaining_row() -> None:
    with _make_session() as session:
        project = Project(user_id="user-1", title="My Tutor")
        session.add(project)
        session.commit()
        session.refresh(project)

        now = datetime.now(timezone.utc)
        for i in range(3):
            session.add(_conversation(project.id, now - timedelta(minutes=i), []))
        session.commit()

        result = get_sessions_paginated(session, "user-1", page=2, per_page=2)

        assert result["total"] == 3
        assert len(result["items"]) == 1
