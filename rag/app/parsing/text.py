"""
Plain-Text and Markdown Extraction

Encodings are tried in a fixed order instead of being guessed: UTF-8 (what every current editor
saves), UTF-16 only when it has a byte-order mark (Windows Notepad's "Unicode"), then
Windows-1252 (older German Windows tools), with Latin-1 as the catch-all. Statistical detection
(e.g. charset-normalizer) misreads short German texts — "Übung" came back as "㎾ung" — while
this order is right for practically every file a teacher in a German- or English-speaking school
has.

Markdown is split at its headings so chunks carry them; plain text is split at blank lines by
the chunker.
"""

import codecs

from app.parsing.types import ParseResult, Section, normalize_text, split_markdown


def decode_text(data: bytes) -> str:
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", errors="replace")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def parse_text(data: bytes, file_type: str) -> ParseResult:
    text = decode_text(data)
    if file_type == "md":
        return ParseResult(split_markdown(text))
    normalized = normalize_text(text)
    return ParseResult([Section(normalized)] if normalized else [])
