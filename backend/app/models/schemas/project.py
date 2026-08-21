"""
Project Request/Response Shapes

The request/response shapes for app/api/projects.py: the full project representation, a
partial update, dashboard stats, and the in-app preview chat.

How to use:
    from app.models.schemas.project import ProjectOut
"""

from datetime import datetime

from pydantic import field_validator

from app.core.error_codes import ErrorCode
from app.core.schema import CamelModel
from app.models.schemas.auth import MAX_PASSWORD_BYTES
from app.models.schemas.chat import ChatHistoryEntry

# A shared classroom PIN, not an account password — short and memorable is fine, unlike the
# stricter 10-char+digit rule enforced on User passwords (schemas/auth.py).
MIN_CHAT_PASSWORD_LENGTH = 4


class ProjectOut(CamelModel):
    id: str
    title: str
    description: str | None
    status: str
    llm_api_key_id: str | None
    # Derived from the referenced key — kept in the response so project cards and the
    # analytics model filter don't need an extra request.
    llm_model: str | None
    preprompt: str | None
    start_prompt: str | None
    avatar_model_url: str | None
    avatar_background_url: str | None
    grade_level: str | None
    creativity: float
    published: bool
    share_slug: str | None
    save_conversations: bool
    survey_before_url: str | None
    survey_before_enabled: bool
    survey_after_url: str | None
    survey_after_enabled: bool
    tts_enabled: bool
    tts_api_key_id: str | None
    tts_voice: str | None
    spoken_language: str
    stt_enabled: bool
    chat_default_open: bool
    password_protected: bool
    created_at: datetime


class ProjectUpdate(CamelModel):
    title: str | None = None
    description: str | None = None
    # The model choice goes through the key reference; llm_model is derived from it server-side
    # and is therefore deliberately not writable.
    llm_api_key_id: str | None = None
    preprompt: str | None = None
    start_prompt: str | None = None
    avatar_model_url: str | None = None
    avatar_background_url: str | None = None
    grade_level: str | None = None
    creativity: float | None = None
    save_conversations: bool | None = None
    survey_before_url: str | None = None
    survey_before_enabled: bool | None = None
    survey_after_url: str | None = None
    survey_after_enabled: bool | None = None
    tts_enabled: bool | None = None
    tts_api_key_id: str | None = None
    tts_voice: str | None = None
    spoken_language: str | None = None
    stt_enabled: bool | None = None
    chat_default_open: bool | None = None
    # None = no change (field omitted); "" or explicit null clears/disables the password; a
    # non-empty string sets/changes it — handled separately in api/projects.py, never written
    # straight to the DB (see services/project_service.py::set_or_clear_chat_password).
    chat_password: str | None = None

    @field_validator("chat_password")
    @classmethod
    def validate_chat_password(cls, value: str | None) -> str | None:
        if not value:
            return value
        if len(value) < MIN_CHAT_PASSWORD_LENGTH:
            raise ValueError(ErrorCode.CHAT_PASSWORD_TOO_SHORT)
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(ErrorCode.CHAT_PASSWORD_TOO_LONG)
        return value


class ProjectStats(CamelModel):
    total_projects: int
    published_projects: int
    sessions_last_7_days: int
    messages_last_7_days: int


class PreviewMessageRequest(CamelModel):
    message: str
    history: list[ChatHistoryEntry] = []


class PreviewMessageResponse(CamelModel):
    reply: str
    audio_base64: str | None = None
    content_type: str | None = None
