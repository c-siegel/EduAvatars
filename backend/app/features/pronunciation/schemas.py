"""
Pronunciation Word List Request/Response Shapes

The shapes for features/pronunciation/router.py, plus clean_rule(), the one place that decides
what a valid term/spoken pair is — shared by the form (these schemas) and the text import
(service.py), so both reject exactly the same things.
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.core.error_codes import ErrorCode
from app.core.schema import CamelModel
from app.features.ai.tts.pronunciation import NUMBER_PLACEHOLDER, placeholder_count, spell_out

# The languages a project can speak (see frontend/src/lib/speechOptions.ts).
Language = Literal["de", "en"]

MAX_TERM_LENGTH = 100
MAX_SPOKEN_LENGTH = 200
_WHITESPACE = re.compile(r"\s+")


def clean_rule(term: str, spoken: str, use_spell_out: bool = False) -> tuple[str, str]:
    """Normalize a term/spoken pair, or raise ValueError(<ErrorCode>).

    Whitespace runs collapse to one space (the engine treats a space as "any whitespace" anyway).
    A term needs real text besides `{number}` — a bare placeholder would rewrite every number the
    avatar says. The spoken form may drop a number but can't invent one the term doesn't capture.
    """
    term = _WHITESPACE.sub(" ", term).strip()
    if not term or len(term) > MAX_TERM_LENGTH or not term.replace(NUMBER_PLACEHOLDER, "").strip():
        raise ValueError(ErrorCode.PRONUNCIATION_TERM_INVALID)
    if use_spell_out:
        if placeholder_count(term):
            raise ValueError(ErrorCode.PRONUNCIATION_SPELL_OUT_WITH_NUMBER)
        spoken = spell_out(term)
    spoken = _WHITESPACE.sub(" ", spoken).strip()
    if not spoken or len(spoken) > MAX_SPOKEN_LENGTH:
        raise ValueError(ErrorCode.PRONUNCIATION_SPOKEN_INVALID)
    if placeholder_count(spoken) > placeholder_count(term):
        raise ValueError(ErrorCode.PRONUNCIATION_SPOKEN_NUMBER_MISMATCH)
    return term, spoken


class PronunciationEntryUpdate(CamelModel):
    term: str = Field(max_length=MAX_TERM_LENGTH * 2)
    # May be left empty with spell_out — it's generated from the term then.
    spoken: str = Field(default="", max_length=MAX_SPOKEN_LENGTH * 2)
    whole_word: bool = True
    case_sensitive: bool = False
    # "Read letter by letter": the spoken form becomes the term spelled out ("GPT" -> "G P T").
    spell_out: bool = False

    @model_validator(mode="after")
    def _clean(self):
        self.term, self.spoken = clean_rule(self.term, self.spoken, self.spell_out)
        return self


class PronunciationEntryCreate(PronunciationEntryUpdate):
    language: Language


class PronunciationEntryOut(CamelModel):
    id: str
    language: str
    term: str
    spoken: str
    whole_word: bool
    case_sensitive: bool
    source_pack: str | None
    created_at: datetime


class PronunciationImportIn(CamelModel):
    language: Language
    # The pasted text or the contents of an uploaded .txt/.csv file (read in the browser).
    text: str = Field(max_length=200_000)
    # Whether an imported term replaces an existing entry with the same term (else it's skipped).
    overwrite: bool = False
    # Only report what would happen; nothing is saved.
    dry_run: bool = False


class PronunciationImportLineError(CamelModel):
    line: int
    content: str
    error: str  # an ErrorCode


class PronunciationImportResult(CamelModel):
    added: int
    updated: int
    skipped: int
    errors: list[PronunciationImportLineError]


class PronunciationPreviewIn(CamelModel):
    # A sentence or two, same cap as the voice-clip preview — enough to hear a few terms in context.
    text: str = Field(min_length=1, max_length=300)
    language: Language
    # False: only show the rewritten text (free, instant). True: also synthesize it.
    synthesize: bool = False
    # Which TTS to hear it with: one of the teacher's own "tts" keys, or None for the local-TTS
    # sidecar (optionally cloning one of their voice clips).
    tts_api_key_id: str | None = None
    tts_voice: str | None = Field(default=None, max_length=200)
    voice_clip_id: str | None = None


class PronunciationPreviewOut(CamelModel):
    # What the TTS engine is actually given — after the word list AND the built-in rules.
    spoken_text: str
    # The terms of the word list that matched, so the page can show which entries took effect.
    applied_terms: list[str]
    audio_base64: str | None = None
    content_type: str | None = None


class PresetEntryOut(CamelModel):
    term: str
    spoken: str
    whole_word: bool
    case_sensitive: bool


class PresetPackOut(CamelModel):
    id: str
    language: str
    version: int
    entries: list[PresetEntryOut]
    # How many of the teacher's entries currently come from this pack (0: not applied).
    applied_count: int


class PresetApplyResult(CamelModel):
    added: int
    # Terms the teacher already had — their own version wins.
    skipped: int


class PresetRemoveResult(CamelModel):
    removed: int
