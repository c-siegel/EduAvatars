"""
Public Chat Request/Response Shapes

The request/response shapes for the public chat routes (app/api/public_chat.py): what a
visitor's browser sends and receives.

How to use:
    from app.models.schemas.chat import ChatMessageIn
"""

from typing import Literal

from app.core.schema import CamelModel


class ChatHistoryEntry(CamelModel):
    # Literal instead of a free str, as protection against prompt injection via the history — a
    # manipulated client could otherwise smuggle in e.g. role="system" and try to overwrite the
    # real system prompt. Anything other than "user"/"assistant" fails with 422 before any code runs.
    role: Literal["user", "assistant"]
    content: str


class PublicProjectOut(CamelModel):
    title: str
    teacher_name: str
    # The avatar's first message — empty means the frontend shows a generic greeting (see
    # pages/PublicChat/index.tsx). Also passed to the model as context, see
    # services/llm_service.py::send_chat_message.
    start_prompt: str | None = None
    avatar_model_url: str | None = None
    avatar_background_url: str | None = None
    spoken_language: str = "de"
    tts_enabled: bool = False
    stt_enabled: bool = False
    # Controls whether the chat should start open or collapsed-but-expandable — configurable from
    # the Configurator (see models/project.py), but the frontend doesn't render a collapsed state
    # yet, so this currently has no visible effect.
    chat_default_open: bool = True
    # Already combined server-side with the respective checkbox (see
    # public_chat.py::load_tutor) — not enabled or without a URL both end up as None here, the
    # anonymous page never needs to know about the checkbox itself.
    survey_before_url: str | None = None
    survey_after_url: str | None = None
    # Whether this project requires a password before start_prompt/avatar/etc. are shown at all —
    # when True and unlocked is False, every field above is deliberately left at its default
    # (nothing persona-related leaks pre-unlock), see public_chat.py::load_tutor.
    password_protected: bool = False
    unlocked: bool = True
    # Told to students, not used for any logic: whether this chat is being recorded, and which AI
    # model answers them. Both exist so the page can be honest about what happens to what they
    # type — see the notice under the chat and the "?" in the header (pages/PublicChat).
    save_conversations: bool = False
    llm_model: str | None = None


class ChatUnlockRequest(CamelModel):
    password: str


class ChatUnlockOut(CamelModel):
    unlock_token: str


class ChatMessageIn(CamelModel):
    message: str
    # The visible conversation so far, from the frontend (lives only in the browser tab, see
    # pages/PublicChat/index.tsx) — without it, every request would be stateless and the model
    # wouldn't know earlier rounds of the conversation. Additionally capped server-side, see
    # services/llm_service.py::_build_messages.
    history: list[ChatHistoryEntry] = []


class ChatMessageOut(CamelModel):
    reply: str
    audio_base64: str | None = None
    content_type: str | None = None
    # Wall-clock duration of the LLM/TTS calls in send_message(), for the client-side latency log
    # (see pages/PublicChat/index.tsx) — None for tts_ms means TTS didn't run at all (disabled/no
    # key), not that it was instant.
    llm_ms: float | None = None
    tts_ms: float | None = None
