"""
Parser Output and Text Normalisation

Every parser (pdf.py, docx.py, text.py, docling.py) turns a file into a list of Sections: runs
of text that the chunker (app/chunking.py) never splits across, each with the page and nearest
heading it came from.
"""

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class Section:
    text: str
    page: int | None = None
    heading: str | None = None


@dataclass
class ParseResult:
    sections: list[Section] = field(default_factory=list)
    page_count: int | None = None
    truncated: bool = False

    @property
    def char_count(self) -> int:
        return sum(len(s.text) for s in self.sections)


# Every control/format character except tab and newline: NUL, escape sequences, bidi overrides
# (which can make text read differently than it's stored), zero-width joiners and the like.
_INVISIBLE_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏‪-‮⁠-⁩﻿]")
_SPACES_RE = re.compile(r"[ \t ]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def normalize_text(text: str) -> str:
    """NFC, no invisible/control characters, collapsed whitespace — what gets indexed and shown."""
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = _INVISIBLE_RE.sub("", text)
    text = "\n".join(_SPACES_RE.sub(" ", line).strip() for line in text.split("\n"))
    return _BLANK_LINES_RE.sub("\n\n", text).strip()


def split_markdown(text: str, page: int | None = None, heading: str | None = None) -> list[Section]:
    """Split Markdown at its headings, keeping each heading as the section's label."""
    sections: list[Section] = []
    current: list[str] = []

    def flush() -> None:
        body = normalize_text("\n".join(current))
        if body:
            sections.append(Section(body, page, heading))

    for line in text.split("\n"):
        match = _MARKDOWN_HEADING_RE.match(line.strip())
        if match:
            flush()
            current = []
            heading = normalize_text(match.group(2))[:200] or heading
        else:
            current.append(line)
    flush()
    return sections


def cap_sections(sections: list[Section], max_chars: int) -> tuple[list[Section], bool]:
    """Keep at most `max_chars` characters in total; True if anything was cut."""
    kept: list[Section] = []
    remaining = max_chars
    for section in sections:
        if remaining <= 0:
            return kept, True
        if len(section.text) > remaining:
            kept.append(Section(section.text[:remaining], section.page, section.heading))
            return kept, True
        kept.append(section)
        remaining -= len(section.text)
    return kept, False
