"""
Metadata Headers in Text and Markdown Files

A Markdown or text file may start with a metadata header ("front matter"), as tools like Arcana,
Obsidian or static site generators write it:

    ---
    title: "Kannst DU den Klimawandel stoppen?"
    citation: "Kurzgesagt (n.d.). Kannst DU den Klimawandel stoppen?."
    usage_priority: secondary
    ---

The header describes the source; it isn't part of the material. Indexed as text it would end up
in the first chunk, skew its embedding and could be quoted to students. So it's split off here
and its fields are reported to the backend, which decides which of them it knows
(backend/app/features/knowledge/metadata.py) — this module only reads the format.

Only a flat subset of YAML is understood: `key: value`, quoted strings, `[a, b]` lists, `- item`
lists and `|`/`>` blocks. No anchors, tags, nesting or other YAML features (and no YAML library):
they aren't needed for metadata, and they're where YAML parsers get expensive or unsafe. Lines are
read one by one with bounded patterns, so the work is linear in the header's size.

A file only has a header if it starts with `---`, a closing `---` (or `...`) follows within
MAX_HEADER_CHARS, and every line in between is one of the forms above, a comment, blank, or
indented. Anything else — e.g. a Markdown horizontal rule followed by a paragraph — is content.

How to use:
    fields, body = split_header(text)
"""

import re

from app.parsing.types import clean_inline

MAX_HEADER_CHARS = 8192
MAX_KEYS = 40
MAX_VALUE_CHARS = 500
MAX_LIST_ITEMS = 20

_OPEN = "---"
_CLOSE = ("---", "...")
_KEY_RE = re.compile(r"([A-Za-z0-9_][A-Za-z0-9_.\-]{0,63})[ \t]*:(?:[ \t]|$)")
_ITEM_RE = re.compile(r"-(?:[ \t]|$)")

HeaderValue = str | list[str]


def split_header(text: str) -> tuple[dict[str, HeaderValue], str]:
    """(header fields, text without the header). No header: ({}, text unchanged)."""
    if not text.startswith(_OPEN):
        return {}, text
    head = text[: MAX_HEADER_CHARS + 1]
    lines = head.split("\n")
    if lines[0].rstrip(" \t\r") != _OPEN:
        return {}, text
    closing = None
    consumed = len(lines[0]) + 1
    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip(" \t\r") in _CLOSE:
            closing = index
            break
        consumed += len(line) + 1
        if consumed > MAX_HEADER_CHARS:
            return {}, text
    if closing is None:
        return {}, text
    fields = _parse([line.rstrip("\r") for line in lines[1:closing]])
    if fields is None:
        return {}, text
    body_start = sum(len(line) + 1 for line in lines[: closing + 1])
    return fields, text[body_start:]


def _parse(lines: list[str]) -> dict[str, HeaderValue] | None:
    fields: dict[str, HeaderValue] = {}
    key: str | None = None  # the key whose `- item` list or `|` block is being read
    block: list[str] | None = None
    seen_key = False
    for line in lines:
        stripped = line.strip()
        if block is not None:
            if not stripped or line[:1] in (" ", "\t"):
                block.append(stripped)
                continue
            _store(fields, key, " ".join(part for part in block if part))
            block = None
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1] in (" ", "\t") and not _ITEM_RE.match(stripped):
            # Nested structure isn't supported; it's skipped rather than read wrongly.
            continue
        if _ITEM_RE.match(stripped):
            if key is None:
                return None
            item = _scalar(stripped[1:].strip())
            current = fields.get(key)
            items = current if isinstance(current, list) else []
            if item and len(items) < MAX_LIST_ITEMS:
                items.append(item[:MAX_VALUE_CHARS])
            if items:
                fields[key] = items
            continue
        match = _KEY_RE.match(stripped)
        if not match:
            return None  # a line that isn't metadata: this isn't a header
        seen_key = True
        key = match.group(1).lower()
        raw = stripped[match.end() :].strip()
        if raw in ("|", ">", "|-", ">-", "|+", ">+"):
            block = []
            continue
        if raw.startswith("[") and raw.endswith("]"):
            items = [_scalar(part) for part in _split_flow(raw[1:-1])]
            _store(fields, key, [item[:MAX_VALUE_CHARS] for item in items if item][:MAX_LIST_ITEMS])
        else:
            _store(fields, key, _scalar(raw))
    if block is not None:
        _store(fields, key, " ".join(part for part in block if part))
    return fields if seen_key else None


def _store(fields: dict[str, HeaderValue], key: str | None, value: HeaderValue) -> None:
    if key is None or not value or (key not in fields and len(fields) >= MAX_KEYS):
        return
    fields[key] = value if isinstance(value, list) else clean_inline(value)[:MAX_VALUE_CHARS]


def _scalar(raw: str) -> str:
    """A YAML scalar: quoted ("…" with \\-escapes, '…' with '' escapes) or plain (comment cut)."""
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == '"' and raw.endswith('"'):
        out, escaped = [], False
        for char in raw[1:-1]:
            if escaped:
                out.append({"n": " ", "t": " "}.get(char, char))
                escaped = False
            elif char == "\\":
                escaped = True
            else:
                out.append(char)
        return clean_inline("".join(out))
    if len(raw) >= 2 and raw[0] == "'" and raw.endswith("'"):
        return clean_inline(raw[1:-1].replace("''", "'"))
    comment = raw.find(" #")
    if comment != -1:
        raw = raw[:comment]
    return clean_inline(raw)


def _split_flow(raw: str) -> list[str]:
    """Split a `[a, "b, c"]` list's inside at commas outside quotes."""
    parts, current, quote = [], [], None
    for char in raw:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
            current.append(char)
        elif char == ",":
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return [part.strip() for part in parts]
