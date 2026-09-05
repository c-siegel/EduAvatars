"""Tests for build_conversation_csv's CSV/formula-injection guard (app/services/
analytics_service.py). visitor_name and message content come straight from an anonymous chat
visitor with no format restriction, so a value starting with =, +, -, or @ must not reach the
exported cell unescaped — Excel/Sheets would read it as a live formula the moment a teacher
opens the exported file."""

import csv
import io
import json

from app.models.conversation import Conversation
from app.models.project import Project
from app.services.analytics_service import build_conversation_csv


def _project() -> Project:
    return Project(user_id="user-1", title="Test Project", llm_model="anthropic/claude-sonnet-4-5")


def _conversation(visitor_name: str | None, messages: list[dict]) -> Conversation:
    return Conversation(
        project_id="project-1",
        visitor_id="visitor-1",
        visitor_name=visitor_name,
        messages_json=json.dumps(messages),
    )


def _rows(csv_text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(csv_text)))


def test_formula_visitor_name_is_escaped() -> None:
    conversation = _conversation('=HYPERLINK("http://evil","x")', [])
    rows = _rows(build_conversation_csv(conversation, _project()))
    name_row = next(row for row in rows if row and row[0] == "Name/ID")
    assert name_row[1] == '\'=HYPERLINK("http://evil","x")'


def test_formula_message_content_is_escaped() -> None:
    conversation = _conversation(None, [{"role": "user", "content": "+1+1", "timestamp": "t"}])
    rows = _rows(build_conversation_csv(conversation, _project()))
    message_row = rows[-1]
    assert message_row[2] == "'+1+1"


def test_ordinary_content_is_left_untouched() -> None:
    conversation = _conversation("Alex", [{"role": "assistant", "content": "Hello there!", "timestamp": "t"}])
    rows = _rows(build_conversation_csv(conversation, _project()))
    name_row = next(row for row in rows if row and row[0] == "Name/ID")
    assert name_row[1] == "Alex"
    message_row = rows[-1]
    assert message_row[1] == "Hello there!"
