"""
DOCX Text Extraction

Reads word/document.xml straight from the archive with lxml, instead of going through
python-docx, so the parser settings that matter for untrusted XML are explicit here: no DTDs, no
entity expansion, no network, no huge trees. OOXML never contains a DOCTYPE, so one is rejected
outright — that alone rules out XXE and "billion laughs" payloads.

Runs only inside the parser subprocess (see sandbox.py), after checks.inspect_docx_archive has
already vetted the archive. Body paragraphs and tables are read in document order; headers,
footers, comments and embedded objects are ignored. DOCX has no fixed pages, so sections carry
the nearest heading instead of a page number.
"""

import io
import re
import zipfile

from lxml import etree

from app import errors
from app.errors import RagError
from app.parsing.checks import MAX_ZIP_TOTAL_UNCOMPRESSED
from app.parsing.types import ParseResult, Section, normalize_text

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_P, _TBL, _TR, _TC, _T, _TAB, _BR, _CR = (
    f"{{{_W}}}{tag}" for tag in ("p", "tbl", "tr", "tc", "t", "tab", "br", "cr")
)
_PSTYLE, _OUTLINE, _VAL = f"{{{_W}}}pStyle", f"{{{_W}}}outlineLvl", f"{{{_W}}}val"

# Built-in heading style IDs: "Heading1" in English Word, "berschrift1" in German Word (the
# style ID drops the "Ü"), "Title"/"Titel" for the document title.
_HEADING_STYLE_RE = re.compile(r"^(heading|berschrift|title|titel)\s*\d*$", re.IGNORECASE)


def _parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False, huge_tree=False
    )


def _paragraph_text(paragraph) -> str:
    parts = []
    for node in paragraph.iter(_T, _TAB, _BR, _CR):
        if node.tag == _T:
            parts.append(node.text or "")
        elif node.tag == _TAB:
            parts.append("\t")
        else:
            parts.append("\n")
    return "".join(parts)


def _is_heading(paragraph) -> bool:
    props = paragraph.find(f"{{{_W}}}pPr")
    if props is None:
        return False
    if props.find(_OUTLINE) is not None:
        return True
    style = props.find(_PSTYLE)
    return style is not None and bool(_HEADING_STYLE_RE.match(style.get(_VAL, "")))


def _table_text(table) -> str:
    rows = []
    for row in table.iter(_TR):
        cells = [" ".join(_paragraph_text(p) for p in cell.iter(_P)).strip() for cell in row.iter(_TC)]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def parse_docx(data: bytes) -> ParseResult:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            with archive.open("word/document.xml") as part:
                # Bounded read on top of the central-directory check: the declared size can lie.
                xml = part.read(MAX_ZIP_TOTAL_UNCOMPRESSED + 1)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError) as exc:
        raise RagError(errors.DOCX_INVALID) from exc
    if len(xml) > MAX_ZIP_TOTAL_UNCOMPRESSED:
        raise RagError(errors.FILE_TOO_COMPLEX)
    if b"<!DOCTYPE" in xml[:4096].upper() or b"<!ENTITY" in xml.upper():
        raise RagError(errors.DOCX_INVALID)

    try:
        root = etree.fromstring(xml, _parser())
    except etree.XMLSyntaxError as exc:
        raise RagError(errors.DOCX_INVALID) from exc
    body = root.find(f"{{{_W}}}body")
    if body is None:
        raise RagError(errors.DOCX_INVALID)

    sections: list[Section] = []
    heading: str | None = None
    current: list[str] = []

    def flush() -> None:
        text = normalize_text("\n\n".join(current))
        if text:
            sections.append(Section(text, heading=heading))

    for block in body:
        if block.tag == _P:
            text = _paragraph_text(block)
            if _is_heading(block) and text.strip():
                flush()
                current = []
                heading = normalize_text(text)[:200]
            elif text.strip():
                current.append(text)
        elif block.tag == _TBL:
            text = _table_text(block)
            if text:
                current.append(text)
    flush()
    return ParseResult(sections)
