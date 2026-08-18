"""
Project Table

A user's configured AI persona: prompt, avatar, LLM/TTS keys, and publishing state. See the
root README for what a "project" is in this app, and app/api/public_chat.py for how a
published project is served to visitors.

How to use:
    from app.models.project import Project

    project = session.get(Project, project_id)
"""

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Project(SQLModel, table=True):
    """One user's configured AI persona (avatar, prompt, LLM/TTS setup, publishing state)."""

    # Fields carried over 1:1 from the source repo.
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    title: str
    description: str | None = None
    status: str = "draft"
    # Reference to the key set up in the API dashboard (provider + model + endpoint). This makes
    # the model choice unambiguous even if two keys for the same provider exist.
    llm_api_key_id: str | None = Field(default=None, foreign_key="userapikey.id", index=True)
    # Denormalized copy of the litellm model string from the referenced key — written whenever
    # the project is saved, so analytics/filtering (analytics_service) and the project cards
    # don't need a join on the key.
    llm_model: str | None = None
    preprompt: str | None = None
    # Shown to students as the avatar's first message AND passed to the model as context (see
    # services/llm_service.py::send_chat_message) — unlike the previous, purely client-side
    # greeting, the model now actually knows this text too (e.g. for a posed task students are
    # meant to respond to). Empty means the frontend shows a generic greeting.
    start_prompt: str | None = None
    avatar_model_url: str | None = None
    # Route to a background image from the library (see models/background_image.py), e.g.
    # "/backgrounds/{id}/file" — None keeps showing the neutral light-gray default surface.
    avatar_background_url: str | None = None
    grade_level: str | None = None
    pedagogy: str | None = None
    safety: str | None = None
    lesson_behavior: str | None = None
    custom_prompt: str | None = None
    prompt_mode_auto: bool = True
    manual_system_prompt: str | None = None
    creativity: float = 0.5
    published: bool = False
    share_slug: str | None = Field(default=None, unique=True, index=True)
    save_conversations: bool = False
    # Optional Tally.so surveys (for research purposes), passed through unchanged as an iframe
    # source — a valid/allowed Tally URL is the user's own responsibility (same pattern as the
    # free-text model field, see lib/llmModels.ts). One checkbox per survey decouples "a URL is
    # set" from "the survey is currently active".
    survey_before_url: str | None = None
    survey_before_enabled: bool = False
    survey_after_url: str | None = None
    survey_after_enabled: bool = False
    tts_enabled: bool = False
    # Reference to a key of type "tts" (mirrors llm_api_key_id) — replaces the old tts_provider
    # (a free string), so multiple similar TTS keys (e.g. two custom endpoints) stay unambiguous.
    # See services/api_key_service.py::resolve_tts_key.
    tts_api_key_id: str | None = Field(default=None, foreign_key="userapikey.id", index=True)
    tts_voice: str | None = None
    # Does NOT control lip-sync quality (that's now audio-driven via HeadAudio, independent of
    # language) — instead it's the language hint for STT (services/stt_service.py) and a short
    # preprompt instruction, so text replies actually come back in this language.
    spoken_language: str = "de"
    # Only unlocks the microphone button in the public chat — which service transcribes is no
    # longer a per-project setting (see services/stt_service.py: exclusively the instance-wide
    # Whisper server, no user-owned key possible).
    stt_enabled: bool = False
    # Whether the public chat should start open (True) or collapsed-but-expandable (False). The
    # value is configurable and persisted from the Configurator, but public_chat.py/PublicChat
    # frontend don't yet render a collapsed state — that's still to be implemented.
    chat_default_open: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
