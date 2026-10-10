"""
Source Metadata of Knowledge Documents

What a document is (title, author, year, kind of source, how much to rely on it) so the avatar can
judge it and cite it when a student asks where something comes from. It never reaches the search
index — only the prompt (features/knowledge/prompt.py) — so editing it never needs re-indexing.

Three layers, combined per field when read, never copied into each other (see
KnowledgeDocument in models.py):

    the teacher's own entries  >  the linked bibliography entry (BibTeX)  >  the file's own header

The bibliography beats the header for bibliographic fields; the header is usually the only place
for priority, source type and note. Clearing a field in the dashboard falls back to the next layer.

Only the fields below exist. A header or a BibTeX entry may carry anything; everything else is
dropped here. source_type and priority are fixed vocabularies on purpose: the prompt uses the
English word, so a file can't put free text into it.

How to use:
    fields = metadata.from_header(status["metadata"])    # raw header → our fields
    meta = metadata.effective(document, entry_fields)     # the combined view
    text = metadata.citation_text(meta)                   # "Müller & Schmidt (2020). Titel."
"""

import json
import re
import unicodedata

from app.features.knowledge.models import KnowledgeDocument

FIELDS = (
    "title",
    "author",
    "year",
    "container",
    "url",
    "citation",
    "source_type",
    "priority",
    "note",
    "bibtex_key",
)
SOURCE_TYPES = ("script", "worksheet", "article", "book", "thesis", "report", "web", "transcript", "other")
PRIORITIES = ("primary", "secondary", "supplementary")
MAX_LENGTH = {"title": 300, "author": 300, "container": 200, "url": 500, "citation": 500, "note": 300}
YEAR_RANGE = (1000, 2100)
BIBTEX_KEY_RE = re.compile(r"[A-Za-z0-9_:\-./+]{1,100}")

# Header keys that mean one of our fields, in order of preference (Arcana writes both
# usage_priority and scope; the more specific one wins).
_HEADER_KEYS = {
    "title": ("title",),
    "author": ("author", "authors", "creator"),
    "year": ("year", "publication-year", "publication_year", "published"),
    "container": ("container", "journal", "booktitle", "publisher"),
    "url": ("url", "source-url", "source_url", "link"),
    "citation": ("citation",),
    "source_type": ("source-type", "source_type", "content_type", "content-type", "type"),
    "priority": ("priority", "usage_priority", "usage-priority", "scope"),
    "note": ("note", "notes"),
    "bibtex_key": ("bibtex-key", "bibtex_key", "citekey", "cite-key", "bibkey"),
}

# Keyword → source type, checked in order: "transkript" contains "skript", so transcripts first.
_SOURCE_TYPE_WORDS = (
    ("transcript", ("transcript", "transkript")),
    ("worksheet", ("worksheet", "arbeitsblatt", "übungsblatt", "aufgabenblatt")),
    ("script", ("script", "skript", "lecture", "vorlesung", "handout", "unterlagen")),
    ("thesis", ("thesis", "dissertation", "bachelorarbeit", "masterarbeit")),
    ("report", ("report", "bericht", "studie")),
    ("book", ("book", "buch", "chapter", "kapitel")),
    ("article", ("article", "artikel", "paper", "journal", "aufsatz", "proceedings")),
    ("web", ("web", "website", "webseite", "online", "blog", "wiki")),
)
_PRIORITY_WORDS = (
    ("supplementary", ("supplement", "optional", "ergänz", "background", "hintergrund", "low", "niedrig")),
    ("secondary", ("secondary", "sekundär", "sekundaer", "medium", "mittel")),
    ("primary", ("primary", "primär", "primaer", "core", "main", "haupt", "high", "hoch")),
)
_YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")


def _clean(value) -> str:
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    text = unicodedata.normalize("NFC", str(value))
    # Invisible and bidi characters go (they can make text read differently than it's stored);
    # tabs and line breaks become the spaces they stand for.
    return " ".join(_CONTROL_RE.sub("", text).split())


def source_type_of(raw: str) -> str | None:
    word = _clean(raw).lower()
    if not word:
        return None
    if word in SOURCE_TYPES:
        return word
    for kind, keywords in _SOURCE_TYPE_WORDS:
        if any(k in word for k in keywords):
            return kind
    return "other"


def priority_of(raw: str) -> str | None:
    word = _clean(raw).lower()
    if word in PRIORITIES:
        return word
    for priority, keywords in _PRIORITY_WORDS:
        if any(k in word for k in keywords):
            return priority
    return None


def year_of(raw) -> int | None:
    match = _YEAR_RE.search(_clean(raw))
    if not match:
        return None
    year = int(match.group(1))
    return year if YEAR_RANGE[0] <= year <= YEAR_RANGE[1] else None


def clean_fields(fields: dict) -> dict:
    """Our fields only, each validated and capped; empty ones dropped."""
    out: dict = {}
    for name in FIELDS:
        value = fields.get(name)
        if value is None or value == "" or value == []:
            continue
        if name == "year":
            year = year_of(value)
            if year is not None:
                out[name] = year
        elif name == "source_type":
            kind = source_type_of(value)
            if kind:
                out[name] = kind
        elif name == "priority":
            priority = priority_of(value)
            if priority:
                out[name] = priority
        elif name == "url":
            url = _clean(value)
            # Shown as a link in the dashboard: only web addresses, never javascript: or data:.
            if url.lower().startswith(("http://", "https://")) and len(url) <= MAX_LENGTH["url"]:
                out[name] = url
        elif name == "bibtex_key":
            key = _clean(value)
            if BIBTEX_KEY_RE.fullmatch(key):
                out[name] = key
        else:
            text = _clean(value)[: MAX_LENGTH[name]]
            if text:
                out[name] = text
    return out


def from_header(raw: dict | None) -> dict:
    """A file's header (as the knowledge service reports it, rag/app/parsing/header.py) → our fields."""
    if not isinstance(raw, dict):
        return {}
    picked = {}
    for name, keys in _HEADER_KEYS.items():
        for key in keys:
            if raw.get(key) not in (None, "", []):
                picked[name] = raw[key]
                break
    return clean_fields(picked)


def _load(value: str | None) -> dict:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def manual_fields(document: KnowledgeDocument) -> dict:
    """The teacher's own entries, including the bibliography link."""
    fields = _load(document.meta_json)
    if document.bibtex_key and BIBTEX_KEY_RE.fullmatch(document.bibtex_key):
        fields["bibtex_key"] = document.bibtex_key
    return fields


def effective(document: KnowledgeDocument, entry_fields: dict | None = None) -> dict:
    """The combined metadata: teacher > bibliography entry > header, per field."""
    merged = {**_load(document.header_json)}
    merged.update({k: v for k, v in (entry_fields or {}).items() if k in FIELDS})
    merged.update(_load(document.meta_json))
    if document.bibtex_key:
        merged["bibtex_key"] = document.bibtex_key
    return clean_fields(merged)


def _short_author(author: str) -> str:
    """"Müller, Anna; Schmidt, Ben" → "Müller & Schmidt"; a single name or organisation as is."""
    # Only ";" and "&" separate people: "and" also occurs inside organisation names.
    names = [n.strip() for n in re.split(r";| & ", author) if n.strip()]
    lasts = [n.split(",", 1)[0].strip() if "," in n else n for n in names]
    if not lasts:
        return author
    if len(lasts) == 1:
        return lasts[0]
    if len(lasts) == 2:
        return f"{lasts[0]} & {lasts[1]}"
    return f"{lasts[0]} et al."


def _sentence(text: str) -> str:
    return text if text.endswith((".", "?", "!")) else f"{text}."


def citation_text(meta: dict) -> str | None:
    """The explicit citation, or one generated from what's known:

    author and year → "Short author (Year). Title. Container."
    author only     → "Short author (n.d.). Title."
    no author       → "Title (Year)" / "Title" — a worksheet or textbook chapter needs neither.
    """
    if meta.get("citation"):
        return meta["citation"]
    title, author, year, container = (meta.get(k) for k in ("title", "author", "year", "container"))
    if author:
        parts = [f"{_short_author(author)} ({year or 'n.d.'})."]
        if title:
            parts.append(_sentence(title))
        if container:
            parts.append(_sentence(container))
        return " ".join(parts)
    if title:
        text = f"{title} ({year})" if year else title
        return f"{text}, {container}" if container else text
    return None
