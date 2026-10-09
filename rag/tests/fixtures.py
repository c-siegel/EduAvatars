"""
Test Documents, Generated in Code

Small valid PDFs and DOCX files, plus the hostile ones the upload checks and the sandbox must
stop: archive bombs, XXE / entity-expansion XML, macro documents, encrypted PDFs, renamed files.
"""

import io
import zipfile

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_pdf(pages: list[str], *, password: str | None = None, empty_user_password: bool = False) -> bytes:
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        lines = []
        for index, line in enumerate(text.split("\n")):
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            lines.append(f"BT /F1 12 Tf 72 {720 - 16 * index} Td ({escaped}) Tj ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(lines).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
    if password is not None or empty_user_password:
        writer.encrypt(user_password=password or "", owner_password="owner-secret", algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx_xml(blocks: list[tuple[str, str]]) -> str:
    """blocks: ("h", text) for a heading, ("p", text) for a paragraph, ("t", "a|b;c|d") for a table."""
    body = []
    for kind, text in blocks:
        if kind == "h":
            body.append(f'<w:p><w:pPr><w:pStyle w:val="berschrift1"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>')
        elif kind == "p":
            body.append(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>")
        else:
            rows = "".join(
                "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in row.split("|")) + "</w:tr>"
                for row in text.split(";")
            )
            body.append(f"<w:tbl>{rows}</w:tbl>")
    return f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{_W}"><w:body>{"".join(body)}</w:body></w:document>'


def make_docx(document_xml: str, extra: dict[str, bytes] | None = None, content_types: str = _CONTENT_TYPES) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document_xml)
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return buffer.getvalue()


XXE_DOCUMENT = (
    '<?xml version="1.0"?><!DOCTYPE w:document [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
    f'<w:document xmlns:w="{_W}"><w:body><w:p><w:r><w:t>&xxe;</w:t></w:r></w:p></w:body></w:document>'
)

BILLION_LAUGHS_DOCUMENT = (
    '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
    '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
    '<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]>'
    f'<w:document xmlns:w="{_W}"><w:body><w:p><w:r><w:t>&lol3;</w:t></w:r></w:p></w:body></w:document>'
)
