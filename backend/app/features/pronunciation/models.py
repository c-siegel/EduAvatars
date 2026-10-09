"""
Pronunciation Word List Table

Each teacher's own rules for how the TTS should pronounce a term, per spoken language (see
features/ai/tts/pronunciation.py for how they're applied, and service.py for how they're managed).
They apply to every project of that teacher that speaks the language.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class PronunciationEntry(SQLModel, table=True):
    """One term of a teacher's word list and how the TTS should say it instead."""

    # One spelling per teacher and language — a second "pH" would make it a coin toss which one
    # the TTS gets. "pH" and "PH" are still two different terms (one may be case-sensitive).
    __table_args__ = (UniqueConstraint("user_id", "language", "term", name="uq_pronunciationentry_user_language_term"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    # "de" | "en", the same codes as Project.spoken_language.
    language: str
    term: str
    spoken: str
    whole_word: bool = True
    case_sensitive: bool = False
    # The preset pack this entry was copied from (see presets/), so the page can label it and the
    # pack can be removed again. Cleared once the teacher edits the entry — it's theirs from then on.
    source_pack: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
