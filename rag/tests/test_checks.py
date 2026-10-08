import io
import zipfile

import pytest

from app import errors
from app.errors import RagError
from app.parsing.checks import detect_file_type, safe_display_name
from tests.fixtures import docx_xml, make_docx, make_pdf


def _code(filename: str, data: bytes) -> str:
    with pytest.raises(RagError) as excinfo:
        detect_file_type(filename, data)
    return excinfo.value.code


def test_accepts_the_four_supported_types():
    assert detect_file_type("Skript.PDF", make_pdf(["Hallo"])) == "pdf"
    assert detect_file_type("a.docx", make_docx(docx_xml([("p", "Text")]))) == "docx"
    assert detect_file_type("a.txt", "Grüße".encode()) == "txt"
    assert detect_file_type("notes.markdown", b"# Title\nBody") == "md"


@pytest.mark.parametrize("name", ["a.exe", "a.doc", "a.docm", "a.html", "noextension", "a.pdf.exe"])
def test_rejects_other_extensions(name):
    assert _code(name, b"anything") == errors.UNSUPPORTED_FILE_TYPE


def test_extension_and_content_must_agree():
    assert _code("renamed.pdf", b"MZ\x90\x00 an executable") == errors.FILE_TYPE_MISMATCH
    assert _code("renamed.docx", make_pdf(["x"])) == errors.FILE_TYPE_MISMATCH
    assert _code("binary.txt", b"abc\x00def") == errors.FILE_TYPE_MISMATCH


def test_rejects_empty_file():
    assert _code("a.txt", b"") == errors.FILE_EMPTY


def test_rejects_zip_bomb_by_compression_ratio():
    # 4 MB of zeros deflates to a few KB: far beyond the 100:1 ratio a real document reaches.
    bomb = make_docx(docx_xml([("p", "x")]), extra={"word/media/bomb.bin": b"\0" * (4 * 1024 * 1024)})
    assert _code("bomb.docx", bomb) == errors.ARCHIVE_TOO_LARGE


def test_rejects_too_many_entries():
    extra = {f"word/media/{i}.txt": b"x" for i in range(1001)}
    assert _code("many.docx", make_docx(docx_xml([("p", "x")]), extra=extra)) == errors.ARCHIVE_TOO_LARGE


def test_rejects_path_traversal_entry():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", docx_xml([("p", "x")]))
        archive.writestr("../../etc/evil", "x")
    assert _code("traversal.docx", buffer.getvalue()) == errors.DOCX_INVALID


def test_rejects_macro_documents():
    with_vba = make_docx(docx_xml([("p", "x")]), extra={"word/vbaProject.bin": b"VBA"})
    assert _code("macro.docx", with_vba) == errors.DOCX_MACROS
    macro_type = make_docx(docx_xml([("p", "x")]), content_types="<Types>macroEnabled</Types>")
    assert _code("macro.docx", macro_type) == errors.DOCX_MACROS


def test_rejects_archive_without_document_part():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    assert _code("empty.docx", buffer.getvalue()) == errors.DOCX_INVALID


def test_safe_display_name_strips_paths_and_invisible_characters():
    assert safe_display_name("C:\\Users\\x\\..\\Skript.pdf") == "Skript.pdf"
    assert safe_display_name("../../etc/passwd") == "passwd"
    assert safe_display_name("evil\u202etxt.pdf") == "eviltxt.pdf"
    assert safe_display_name("\x00\x01") == "document"


def test_safe_display_name_keeps_the_extension_when_shortening():
    name = safe_display_name("Becker et al. (2025). " + "Was wir heute übers Klima wissen " * 5 + "8XH7TH2V.pdf")
    assert len(name) <= 120 and name.endswith(".pdf")
    assert detect_file_type(name, make_pdf(["x"])) == "pdf"
