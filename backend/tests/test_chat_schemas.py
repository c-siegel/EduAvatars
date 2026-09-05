"""Tests for ChatMessageIn's blank-message and length guards, and ChatUnlockRequest's
password-length guard (app/models/schemas/chat.py). The blank-message check is the backend's own
backstop against an empty user turn reaching the LLM, alongside the frontend's own check
(sendMessage's trim-check in pages/PublicChat/index.tsx). The length caps exist because an
anonymous visitor had no server-side limit on message (or echoed history) size, so a handful of
requests within the existing rate limit could send arbitrarily large text against the project
owner's own LLM API key. The password-length check exists because bcrypt.checkpw (see
services/chat_password_service.py) raises an unhandled error above 72 bytes instead of
truncating — without it, a single oversized guess would 500 this fully unauthenticated route."""

import pytest
from pydantic import ValidationError

from app.models.schemas.chat import ChatHistoryEntry, ChatMessageIn, ChatUnlockRequest


@pytest.mark.parametrize("message", ["", "   ", "\n\t"])
def test_rejects_blank_message(message: str) -> None:
    with pytest.raises(ValidationError):
        ChatMessageIn(message=message)


def test_accepts_non_blank_message() -> None:
    assert ChatMessageIn(message="Hallo!").message == "Hallo!"


def test_rejects_oversized_message() -> None:
    with pytest.raises(ValidationError):
        ChatMessageIn(message="a" * 8001)


def test_accepts_message_at_the_length_limit() -> None:
    message = "a" * 8000
    assert ChatMessageIn(message=message).message == message


def test_rejects_oversized_history_entry() -> None:
    with pytest.raises(ValidationError):
        ChatHistoryEntry(role="user", content="a" * 8001)


def test_rejects_oversized_unlock_password() -> None:
    with pytest.raises(ValidationError):
        ChatUnlockRequest(password="a" * 73)


def test_accepts_unlock_password_within_bcrypt_limit() -> None:
    assert ChatUnlockRequest(password="a" * 72).password == "a" * 72
