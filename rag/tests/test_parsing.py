import subprocess

import pytest

from app import errors
from app.config import settings
from app.errors import RagError
from app.parsing import sandbox
from app.parsing.sandbox import parse_in_sandbox
from app.parsing.types import normalize_text, split_markdown
from app.schemas import DocumentLimits
from tests.fixtures import BILLION_LAUGHS_DOCUMENT, XXE_DOCUMENT, docx_xml, make_docx, make_pdf

LIMITS = DocumentLimits()


def _code(file_type: str, data: bytes, limits: DocumentLimits = LIMITS) -> str:
    with pytest.raises(RagError) as excinfo:
        parse_in_sandbox(file_type, data, limits)
    return excinfo.value.code


def test_pdf_keeps_page_numbers():
    result = parse_in_sandbox("pdf", make_pdf(["Photosynthese erklärt", "Zellatmung erklärt"]), LIMITS)
    assert result.page_count == 2
    assert [s.page for s in result.sections] == [1, 2]
    assert "Photosynthese" in result.sections[0].text
    assert "Zellatmung" in result.sections[1].text


def test_pdf_with_empty_user_password_opens():
    result = parse_in_sandbox("pdf", make_pdf(["Nur Druck gesperrt"], empty_user_password=True), LIMITS)
    assert "Druck" in result.sections[0].text


def test_password_protected_pdf_is_rejected():
    assert _code("pdf", make_pdf(["Geheim"], password="secret")) == errors.PDF_ENCRYPTED


def test_pdf_page_limit():
    data = make_pdf(["eins", "zwei", "drei"])
    assert _code("pdf", data, DocumentLimits(max_pages=2)) == errors.TOO_MANY_PAGES


def test_garbage_pdf_fails_cleanly():
    assert _code("pdf", b"%PDF-1.7\n this is not a pdf") == errors.PARSE_FAILED


def test_docx_headings_paragraphs_and_tables():
    xml = docx_xml(
        [("p", "Vorwort"), ("h", "Kapitel 1"), ("p", "Erster Absatz."), ("t", "Name|Wert;Pi|3,14"), ("h", "Kapitel 2"), ("p", "Zweiter.")]
    )
    result = parse_in_sandbox("docx", make_docx(xml), LIMITS)
    assert [(s.heading, s.text) for s in result.sections] == [
        (None, "Vorwort"),
        ("Kapitel 1", "Erster Absatz.\n\nName | Wert\nPi | 3,14"),
        ("Kapitel 2", "Zweiter."),
    ]


@pytest.mark.parametrize("document", [XXE_DOCUMENT, BILLION_LAUGHS_DOCUMENT])
def test_docx_with_dtd_is_rejected(document):
    assert _code("docx", make_docx(document)) == errors.DOCX_INVALID


def test_text_encodings_and_markdown_sections():
    assert parse_in_sandbox("txt", "Übung macht den Meister".encode("cp1252"), LIMITS).sections[0].text == (
        "Übung macht den Meister"
    )
    utf16 = "Größe".encode("utf-16")
    assert parse_in_sandbox("txt", utf16, LIMITS).sections[0].text == "Größe"
    result = parse_in_sandbox("md", "Intro\n# Teil A\nInhalt A\n## Teil B\nInhalt B".encode(), LIMITS)
    assert [(s.heading, s.text) for s in result.sections] == [(None, "Intro"), ("Teil A", "Inhalt A"), ("Teil B", "Inhalt B")]


def test_character_limit_truncates():
    result = parse_in_sandbox("txt", ("a" * 5000).encode(), DocumentLimits(max_chars=1000))
    assert result.truncated
    assert result.char_count == 1000


def test_memory_limit_kills_the_parser(monkeypatch):
    # Far too little address space for an interpreter: the child dies, the service doesn't.
    monkeypatch.setattr(settings, "rag_parse_memory_mb", 16)
    assert _code("txt", b"hello") == errors.FILE_TOO_COMPLEX


def test_wall_clock_timeout(monkeypatch):
    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="worker", timeout=1)

    monkeypatch.setattr(sandbox.subprocess, "run", hang)
    assert _code("txt", b"hello") == errors.PARSE_TIMEOUT


def test_normalize_removes_invisible_characters():
    assert normalize_text("a\x00b‮c​ d\r\n\n\n\ne   f") == "abc d\n\ne f"


def test_split_markdown_keeps_heading_labels():
    sections = split_markdown("# A\n\ntext a\n\n# B\ntext b", page=3)
    assert [(s.page, s.heading, s.text) for s in sections] == [(3, "A", "text a"), (3, "B", "text b")]


def test_pdf_decompression_bomb_is_contained():
    import io
    import zlib

    from pypdf import PdfWriter
    from pypdf.generic import NameObject, StreamObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    stream = StreamObject()
    # ~100 MB of content stream in ~100 KB: past pypdf's own decompression limit.
    stream._data = zlib.compress(b"BT (x) Tj ET\n" + b" " * (100 * 1024 * 1024), 9)
    stream[NameObject("/Filter")] = NameObject("/FlateDecode")
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)

    # The page is skipped, not inflated; the ingest worker then reports NO_EXTRACTABLE_TEXT.
    assert parse_in_sandbox("pdf", buffer.getvalue(), LIMITS).sections == []
