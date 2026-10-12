"""
Reading BibTeX Files

Teachers who work with citation software (Zotero with Better BibTeX, JabRef, Citavi, …) already
have their sources as a .bib file. Imported per knowledge base, its entries become the
bibliographic layer of the documents' metadata (features/knowledge/metadata.py), linked by
BibTeX key.

Our own small reader instead of a library: the maintained ones are either LGPL (bibtexparser 1.x)
or a pre-release major version, and metadata needs only a subset — entries with braced, quoted or
bare values, `#` concatenation, @string macros, the usual LaTeX accents. The file is untrusted
input, so it's read in one pass with explicit limits (size, entries, brace depth, value length):
a malformed entry is skipped from where it broke, never re-scanned, so the work stays linear in
the file's size even for a file of nothing but unclosed braces.

How to use:
    entries, skipped = parse_bibtex(text)
    fields = to_fields(entries[0])     # our metadata fields, plus "files" for matching
"""

import re
import unicodedata
from dataclasses import dataclass, field

MAX_BIB_BYTES = 1024 * 1024
MAX_ENTRIES = 2000
_MAX_DEPTH = 32
# The longest value kept, after joining its parts ("a" # macro # "b"): the stored fields are a
# few hundred characters at most. Without a cap on the *joined* value, @string macros that
# concatenate each other double in size per line — a 20 KB file grows a 300 MB title. Longer
# values (an abstract, say) are dropped, not the entry.
_MAX_VALUE = 5000
# Where an entry's key must end (keys are at most 100 characters): looking further would scan the
# rest of the file for every malformed entry.
_KEY_WINDOW = 200
_KEY_RE = re.compile(r"[A-Za-z0-9_:\-./+]{1,100}")
_MAX_FILE_NAME = 255

_MONTHS = {m: m.capitalize() for m in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")}
_NAME_RE = re.compile(r"[A-Za-z0-9_\-:.+/]+")
_SKIP_TYPES = {"comment", "preamble"}

# Entry type → our source type (metadata.SOURCE_TYPES).
_TYPE_MAP = {
    "article": "article",
    "inproceedings": "article",
    "conference": "article",
    "proceedings": "book",
    "book": "book",
    "inbook": "book",
    "incollection": "book",
    "booklet": "book",
    "phdthesis": "thesis",
    "mastersthesis": "thesis",
    "thesis": "thesis",
    "techreport": "report",
    "report": "report",
    "online": "web",
    "electronic": "web",
    "www": "web",
    "webpage": "web",
}

_ACCENTS = {'"': "\u0308", "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303", "=": "\u0304", ".": "\u0307", "c": "\u0327", "v": "\u030c", "u": "\u0306", "H": "\u030b"}
_ACCENT_RE = re.compile(r"\\([\"'`^~=.])(?:\{\s*\\?([A-Za-z])\s*\}|\s?\\?([A-Za-z]))|\\([cvuH])\s*\{\s*\\?([A-Za-z])\s*\}|\\([cvuH]) ([A-Za-z])")
_NAMED = {"ss": "ß", "o": "ø", "O": "Ø", "aa": "å", "AA": "Å", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ", "l": "ł", "L": "Ł", "i": "ı"}
_NAMED_RE = re.compile(r"\\(ss|aa|AA|ae|AE|oe|OE|o|O|l|L|i)(?![A-Za-z])\s?")
_ESCAPED_RE = re.compile(r"\\([&%$_#{}])")
_COMMAND_RE = re.compile(r"\\[A-Za-z]+\*?\s*")


@dataclass
class BibEntry:
    key: str
    type: str
    fields: dict[str, str] = field(default_factory=dict)


class _Scanner:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def skip_space(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t\r\n":
            self.pos += 1

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def name(self) -> str:
        match = _NAME_RE.match(self.text, self.pos)
        if not match:
            return ""
        self.pos = match.end()
        return match.group(0)

    def balanced(self, opening: str, closing: str) -> str | None:
        """The text up to the matching closing delimiter (pos is just after the opening one)."""
        depth, start = 0, self.pos
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\":
                self.pos += 2
                continue
            if char == "\n" and self.text.startswith("@", self.pos + 1):
                # An entry starting on a new line: the value before it was never closed. Stop
                # here, so the next entry isn't swallowed.
                self.pos += 1
                return None
            if char == "{":
                depth += 1
                if depth > _MAX_DEPTH:
                    return None
            elif char == "}" and (closing != "}" or depth > 0):
                depth -= 1
                if depth < 0:
                    return None
            elif char == closing and depth == 0:
                value = self.text[start : self.pos]
                self.pos += 1
                return value if len(value) <= _MAX_VALUE else ""
            self.pos += 1
        return None


def _value(scanner: _Scanner, macros: dict[str, str]) -> str | None:
    """One field value: parts in braces, quotes or bare (number / macro), joined by '#'."""
    parts: list[str] = []
    total = 0
    too_long = False
    while True:
        scanner.skip_space()
        char = scanner.peek()
        if char == "{":
            scanner.pos += 1
            part = scanner.balanced("{", "}")
        elif char == '"':
            scanner.pos += 1
            part = scanner.balanced("{", '"')
        else:
            word = scanner.name()
            if not word:
                return None
            # A number stands for itself; an unknown macro for nothing, as in BibTeX.
            part = word if word.isdigit() else macros.get(word.lower(), "")
        if part is None:
            return None
        parts.append(part)
        total += len(part)
        if total > _MAX_VALUE:
            parts, total = [], 0
            too_long = True
        scanner.skip_space()
        if scanner.peek() != "#":
            return "" if too_long else "".join(parts)
        scanner.pos += 1


def _skip_to_next_entry(scanner: _Scanner) -> None:
    next_at = scanner.text.find("@", scanner.pos)
    scanner.pos = next_at if next_at != -1 else len(scanner.text)


def parse_bibtex(text: str) -> tuple[list[BibEntry], int]:
    """(entries, number of entries skipped as malformed, duplicate or over the limit)."""
    scanner = _Scanner(text)
    macros: dict[str, str] = dict(_MONTHS)
    entries: list[BibEntry] = []
    seen: set[str] = set()
    skipped = 0
    while True:
        at = text.find("@", scanner.pos)
        if at == -1:
            break
        scanner.pos = at + 1
        kind = scanner.name().lower()
        scanner.skip_space()
        opening = scanner.peek()
        if not kind or opening not in "{(":
            continue
        closing = "}" if opening == "{" else ")"
        scanner.pos += 1
        if kind in _SKIP_TYPES:
            if scanner.balanced("{", closing) is None:
                break  # unclosed to the end of the file
            continue
        if kind == "string":
            scanner.skip_space()
            name = scanner.name().lower()
            scanner.skip_space()
            if name and scanner.peek() == "=":
                scanner.pos += 1
                value = _value(scanner, macros)
                if value is not None and len(macros) < 500:
                    macros[name] = value
            _skip_to_next_entry(scanner)
            continue

        scanner.skip_space()
        key_start = scanner.pos
        window = scanner.pos + _KEY_WINDOW
        comma = text.find(",", scanner.pos, window)
        end = text.find(closing, scanner.pos, window)
        if comma == -1 and end == -1:
            skipped += 1
            _skip_to_next_entry(scanner)
            continue
        if end != -1 and (comma == -1 or end < comma):
            # "@misc{key}" — a key without fields says nothing about the source.
            skipped += 1
            scanner.pos = end + 1
            continue
        key = text[key_start:comma].strip()
        scanner.pos = comma + 1
        fields: dict[str, str] = {}
        # The same characters the dashboard accepts for a key (metadata.BIBTEX_KEY_RE): a key like
        # "Müller2020" couldn't be shown or chosen there, so its entry is skipped.
        ok = bool(_KEY_RE.fullmatch(key))
        while ok:
            scanner.skip_space()
            char = scanner.peek()
            if char == closing:
                scanner.pos += 1
                break
            if char == ",":
                scanner.pos += 1
                continue
            name = scanner.name().lower()
            scanner.skip_space()
            if not name or scanner.peek() != "=":
                ok = False
                break
            scanner.pos += 1
            value = _value(scanner, macros)
            if value is None:
                ok = False
                break
            if name not in fields and len(fields) < 50:
                fields[name] = value
        if not ok:
            skipped += 1
            _skip_to_next_entry(scanner)
            continue
        if key.lower() in seen or len(entries) >= MAX_ENTRIES:
            skipped += 1
            continue
        seen.add(key.lower())
        entries.append(BibEntry(key=key, type=kind, fields=fields))
    return entries, skipped


def latex_to_text(value: str) -> str:
    """The common LaTeX in .bib files → plain text: accents, escapes, commands, braces."""
    def accent(match: re.Match) -> str:
        mark = match.group(1) or match.group(4) or match.group(6)
        letter = match.group(2) or match.group(3) or match.group(5) or match.group(7)
        return unicodedata.normalize("NFC", letter + _ACCENTS[mark])

    text = _ACCENT_RE.sub(accent, value)
    text = _NAMED_RE.sub(lambda m: _NAMED[m.group(1)], text)
    text = text.replace("\\,", " ")  # a thin space, as in "50\\,\\%"
    text = _ESCAPED_RE.sub(lambda m: "\x00" + m.group(1), text)
    text = text.replace("---", "—").replace("--", "–").replace("~", " ")
    text = _COMMAND_RE.sub("", text)
    text = text.replace("{", "").replace("}", "").replace("\x00", "")
    return " ".join(unicodedata.normalize("NFC", text).split())


def _split_names(raw: str) -> list[str]:
    """Split an author list at " and " outside braces ({Kurzgesagt and friends} is one name)."""
    names, depth, start, i = [], 0, 0, 0
    lowered = raw.lower()
    while i < len(raw):
        char = raw[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif depth == 0 and lowered.startswith(" and ", i):
            names.append(raw[start:i])
            i += 5
            start = i
            continue
        i += 1
    names.append(raw[start:])
    return [n.strip() for n in names if n.strip()]


def format_authors(raw: str) -> str:
    """BibTeX names → "Last, First; Last, First"; an organisation in braces stays as it is."""
    out = []
    for name in _split_names(raw):
        stripped = name.strip()
        if stripped.startswith("{") and stripped.endswith("}") or "," in stripped:
            out.append(latex_to_text(stripped))
            continue
        words = latex_to_text(stripped).split()
        out.append(f"{words[-1]}, {' '.join(words[:-1])}" if len(words) > 1 else " ".join(words))
    return "; ".join(n for n in out if n)


def _files(raw: str) -> list[str]:
    """Base names of the attached files: Zotero "Desc:path/file.pdf:mime", JabRef ":file.pdf:PDF",
    or plain paths; several separated by ';'."""
    names = []
    for part in raw.split(";"):
        pieces = [p for p in part.split(":") if p.strip()]
        candidates = [p for p in pieces if "." in p.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]]
        if candidates:
            path = candidates[0] if len(candidates) == 1 else max(candidates, key=len)
            names.append(path.replace("\\", "/").rsplit("/", 1)[-1].strip()[:_MAX_FILE_NAME])
    return [n for n in names if n][:10]


def to_fields(entry: BibEntry) -> dict:
    """An entry → our metadata fields (still to be validated by metadata.clean_fields), plus the
    attached files' names under "files" for linking documents by file name."""
    f = entry.fields
    out: dict = {"bibtex_key": entry.key}
    if f.get("title"):
        out["title"] = latex_to_text(f["title"])
    author = f.get("author") or f.get("editor")
    if author:
        out["author"] = format_authors(author)
    if f.get("year") or f.get("date"):
        out["year"] = latex_to_text(f.get("year") or f.get("date"))
    for name in ("journal", "journaltitle", "booktitle", "publisher", "school", "institution", "howpublished"):
        if f.get(name):
            out["container"] = latex_to_text(f[name])
            break
    if f.get("url"):
        out["url"] = latex_to_text(f["url"]).replace(" ", "")
    elif f.get("doi"):
        doi = latex_to_text(f["doi"]).replace(" ", "")
        out["url"] = doi if doi.lower().startswith("http") else f"https://doi.org/{doi}"
    out["source_type"] = _TYPE_MAP.get(entry.type, "web" if entry.type == "misc" and "url" in out else "other")
    if f.get("note"):
        out["note"] = latex_to_text(f["note"])
    if f.get("file"):
        out["files"] = _files(f["file"])
    return out
