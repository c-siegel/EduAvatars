"""
Chunking

Splits parsed Sections into passages small enough to embed well and to hand several of them to
the LLM per turn. Paragraphs are packed into chunks of roughly `size` characters with `overlap`
characters carried over, so a fact that straddles two chunks is still found whole in one of them.
A chunk never crosses a section boundary — in a PDF that's a page, so every chunk has exactly
one page number.

Sizes are in characters, not tokens: ~4 characters per token for German and English, so the
default 1400/200 is about 350/50 tokens. The embedding model decides the size (see
app/embedding.py) — a model that truncates at 128 tokens needs shorter chunks.
"""

import re
from dataclasses import dataclass

from app.parsing.types import Section

_SENTENCE_END_RE = re.compile(r"(?<=[.!?…:;])\s+")


@dataclass
class Chunk:
    text: str
    page: int | None
    heading: str | None
    ordinal: int

    def embedding_text(self) -> str:
        """What gets embedded: the heading in front helps short chunks match their topic."""
        return f"{self.heading}\n{self.text}" if self.heading else self.text


def _split_long(paragraph: str, size: int) -> list[str]:
    """Break a paragraph longer than `size` at sentence ends, or at spaces as a last resort."""
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_END_RE.split(paragraph):
        while len(sentence) > size:
            cut = sentence.rfind(" ", 0, size)
            cut = cut if cut > size // 2 else size
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if current and len(current) + 1 + len(sentence) > size:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return [p for p in pieces if p]


def _tail(text: str, overlap: int) -> str:
    """The last ~`overlap` characters of `text`, starting at a word boundary."""
    if overlap <= 0 or len(text) <= overlap:
        return text if overlap > 0 else ""
    tail = text[-overlap:]
    space = tail.find(" ")
    return tail[space + 1 :] if 0 <= space < len(tail) - 1 else tail


def chunk_sections(sections: list[Section], size: int = 1400, overlap: int = 200) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in sections:
        paragraphs: list[str] = []
        for paragraph in section.text.split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph:
                paragraphs.extend(_split_long(paragraph, size) if len(paragraph) > size else [paragraph])

        current = ""
        for paragraph in paragraphs:
            if current and len(current) + 2 + len(paragraph) > size:
                chunks.append(Chunk(current, section.page, section.heading, len(chunks)))
                carried = _tail(current, overlap)
                current = f"{carried}\n\n{paragraph}" if carried else paragraph
            else:
                current = f"{current}\n\n{paragraph}" if current else paragraph
        if current:
            chunks.append(Chunk(current, section.page, section.heading, len(chunks)))
    return chunks
