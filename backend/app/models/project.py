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
    # Both are passed straight through to the model as the standard sampling parameters (see
    # services/llm_service.py). Providers accept 0.0-2.0 for temperature and 0.0-1.0 for top_p;
    # the same range is enforced in schemas/project.py so a bad value is rejected here rather
    # than by the provider mid-chat. Changing both at once is discouraged (see the hint texts in
    # the configurator), but nothing stops an educator from doing it.
    temperature: float = 0.5
    # 1.0 = no nucleus filtering, which is what every provider defaults to.
    top_p: float = 1.0
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
    # Sentence-chunked streaming for the public chat (see services/text_chunk_service.py) — ignored
    # for the GWDG Arcana LLM provider's citation-guarded stream, which always streams regardless
    # of this flag (see services/llm_service.py::ArcanaReferenceGuard).
    streaming_enabled: bool = True
    # Reference to a key of type "tts" (mirrors llm_api_key_id) — replaces the old tts_provider
    # (a free string), so multiple similar TTS keys (e.g. two custom endpoints) stay unambiguous.
    # See services/api_key_service.py::resolve_tts_key.
    tts_api_key_id: str | None = Field(default=None, foreign_key="userapikey.id", index=True)
    tts_voice: str | None = None
    # Does NOT control lip-sync quality (that's now audio-driven via HeadAudio, independent of
    # language) — instead it's the language hint for STT (services/stt_service.py) and a short
    # preprompt instruction, so text replies actually come back in this language.
    spoken_language: str = "de"
    # Reference to a key of type "stt" (mirrors tts_api_key_id/llm_api_key_id) — selects a
    # "bring your own key" (BYOK) STT provider (currently GWDG SAIA). None (the default) keeps
    # transcribing locally through the instance-wide Whisper server instead, see
    # services/stt_service.py::transcribe_audio.
    stt_api_key_id: str | None = Field(default=None, foreign_key="userapikey.id", index=True)
    # Only unlocks the microphone button in the public chat — stt_api_key_id (above) decides which
    # engine actually transcribes.
    stt_enabled: bool = True
    # Whether the public chat should start open (True) or collapsed-but-expandable (False). The
    # value is configurable and persisted from the Configurator, but public_chat.py/PublicChat
    # frontend don't yet render a collapsed state — that's still to be implemented.
    chat_default_open: bool = True
    # Optional teacher-set access gate for the public chat link (see services/chat_password_
    # service.py) — bcrypt hash, same scheme as User.password_hash. None means anyone with the
    # share link can chat, same as before this field existed.
    chat_password_hash: str | None = None
    # Whether a visitor must type a name or ID before the chat starts (see
    # services/visitor_name_service.py) — unlike chat_password_hash this isn't a secret, just a
    # label that ends up on Conversation.visitor_name so a saved transcript can be told apart from
    # every other visitor's. Only takes effect together with save_conversations: it's pointless
    # (and needlessly identifying) to ask for a name when nothing is being kept.
    require_visitor_name: bool = False
    # Filesystem path to the once-synthesized audio for start_prompt (see
    # services/tts_service.py, api/projects.py's start-audio routes) — None until the educator
    # clicks "Generate audio", so every visitor's chat load doesn't re-synthesize the same fixed
    # text. Cleared automatically whenever start_prompt/tts_voice/tts_api_key_id changes (see
    # services/project_service.py::update_project), so a stale voice/text is never served.
    start_audio_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def password_protected(self) -> bool:
        """Whether a visitor must unlock this project's chat with a password before using it."""
        return self.chat_password_hash is not None

    @property
    def start_audio_url(self) -> str | None:
        """Route to the cached start-prompt audio, or None if it hasn't been generated yet."""
        return f"/projects/{self.id}/start-audio" if self.start_audio_path else None
