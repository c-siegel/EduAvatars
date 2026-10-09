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
