"""
Public Chat Request/Response Shapes

The request/response shapes for the public chat routes (app/api/public_chat.py): what a
visitor's browser sends and receives.

How to use:
    from app.models.schemas.chat import ChatMessageIn
"""

from typing import Literal

from pydantic import field_validator

from app.core.error_codes import ErrorCode
from app.core.schema import CamelModel
from app.models.schemas.auth import MAX_PASSWORD_BYTES

# Generous for a real typed/spoken chat turn (roughly a full page of text), but bounded — without
# this, an anonymous visitor could send arbitrarily large messages (or stuff bloat into `history`,
# see ChatMessageIn below) within the existing per-visitor rate limit, inflating token cost
# against the project owner's own LLM API key with no server-side size cap at all.
_MAX_CHAT_MESSAGE_CHARS = 8000


def _check_chat_message_length(value: str) -> str:
    if len(value) > _MAX_CHAT_MESSAGE_CHARS:
        raise ValueError(ErrorCode.CHAT_MESSAGE_TOO_LONG)
    return value


class ChatHistoryEntry(CamelModel):
    # Literal instead of a free str, as protection against prompt injection via the history — a
    # manipulated client could otherwise smuggle in e.g. role="system" and try to overwrite the
    # real system prompt. Anything other than "user"/"assistant" fails with 422 before any code runs.
    role: Literal["user", "assistant"]
    content: str
    # ISO 8601 timestamp of this message, set server-side when a conversation is saved (see
    # api/public_chat.py::_save_conversation_turn) — always None on the way in, since the
    # frontend never sends one with its request history. Saved conversations from before this
    # field existed also don't have one.
    timestamp: str | None = None

    # Caps each entry the same way as the current message (see ChatMessageIn) — history is
    # otherwise just as visitor-controlled (the frontend echoes it back on every request) and
    # would be an easy way around a length cap that only checked `message`.
    @field_validator("content")
    @classmethod
    def validate_content_length(cls, value: str) -> str:
        return _check_chat_message_length(value)


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
    # Whether the frontend should use POST /message/stream instead of /message — see
    # api/public_chat.py::send_message_stream. Meaningless (and always False here) without
    # tts_enabled, since the whole point is audio starting before the full reply is ready.
    streaming_enabled: bool = False
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
    # Whether a visitor must type a name or ID before the chat starts (see
    # services/visitor_name_service.py) — unlike password_protected/unlocked above, this doesn't
    # gate any other field here: the name has no secrecy purpose, so nothing needs to be withheld
    # while it's still missing. Whether it's already been entered lives entirely client-side (see
    # lib/visitorNameStorage.ts), since there's nothing server-side to verify it against.
    require_visitor_name: bool = False
    # Told to students, not used for any logic: whether this chat is being recorded, and which AI
    # model answers them. Both exist so the page can be honest about what happens to what they
    # type — see the notice under the chat and the "?" in the header (pages/PublicChat).
    save_conversations: bool = False
    llm_model: str | None = None
    # Route to the once-generated start_prompt audio (see api/projects.py's start-audio routes) —
    # None means it hasn't been generated (yet), in which case the frontend just shows the
    # start_prompt as text without trying to speak it. Populated the same way as start_prompt
    # (stays None while password-locked), see public_chat.py::load_tutor.
    start_audio_url: str | None = None


class ChatUnlockRequest(CamelModel):
    password: str

    # bcrypt.checkpw (see chat_password_service.py) raises an unhandled ValueError above 72
    # bytes instead of truncating — without this, a single oversized guess 500s this endpoint,
    # which needs no login at all.
    @field_validator("password")
    @classmethod
    def validate_password_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(ErrorCode.CHAT_PASSWORD_TOO_LONG)
        return value


class ChatUnlockOut(CamelModel):
    unlock_token: str


class ChatMessageIn(CamelModel):
    message: str
    # The visible conversation so far, from the frontend (lives only in the browser tab, see
    # pages/PublicChat/index.tsx) — without it, every request would be stateless and the model
    # wouldn't know earlier rounds of the conversation. Additionally capped server-side, see
    # services/llm_service.py::_build_messages.
    history: list[ChatHistoryEntry] = []

    # Belt and braces alongside the frontend's own guard (sendMessage's trim-check in
    # pages/PublicChat/index.tsx) — a blank message has no legitimate use here, so nothing should
    # ever forward one to the LLM as a real user turn, whether that's a frontend bug or a direct
    # API call.
    @field_validator("message")
    @classmethod
    def validate_message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(ErrorCode.CHAT_MESSAGE_EMPTY)
        return _check_chat_message_length(value)


class ChatMessageOut(CamelModel):
    reply: str
    audio_base64: str | None = None
    content_type: str | None = None
    # Wall-clock duration of the LLM/TTS calls in send_message(), for the client-side latency log
    # (see pages/PublicChat/index.tsx) — None for tts_ms means TTS didn't run at all (disabled/no
    # key), not that it was instant.
    llm_ms: float | None = None
    tts_ms: float | None = None
