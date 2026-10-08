"""
Upload Checks That Run Before Any Parser Sees a File

Cheap, synchronous checks on the raw bytes (see docs/rag-plan.md §6.2): the file type is decided by
the extension AND the content agreeing — never by a browser-supplied Content-Type — and a DOCX
(a ZIP archive) is inspected through its central directory before a single entry is decompressed.
Nothing here parses PDF or XML; that only happens in the sandboxed subprocess (sandbox.py).

How to use:
    file_type = detect_file_type("Skript.pdf", data)   # raises RagError
"""

import codecs
import io
import posixpath
import unicodedata
import zipfile

from app import errors
from app.errors import RagError

FILE_TYPES = ("pdf", "docx", "txt", "md")

_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "md", ".markdown": "md"}

# A real DOCX has a few dozen entries and rarely more than a few MB uncompressed. These bounds
# leave room for large documents while stopping archive ("zip") bombs before decompression.
MAX_ZIP_ENTRIES = 1000
MAX_ZIP_TOTAL_UNCOMPRESSED = 100 * 1024 * 1024
MAX_ZIP_RATIO = 100
# Small XML parts legitimately compress better than 100:1 (long runs of identical markup), so the
# ratio only counts for entries that are big enough to matter.
_RATIO_MIN_ENTRY_SIZE = 1024 * 1024

# The only parts app/parsing/docx.py ever reads.
DOCX_REQUIRED_PARTS = ("[Content_Types].xml", "word/document.xml")


def detect_file_type(filename: str, data: bytes) -> str:
    """Return "pdf" | "docx" | "txt" | "md", or raise if the name and the content don't agree."""
    if not data:
        raise RagError(errors.FILE_EMPTY)
    extension = posixpath.splitext(filename.lower().strip())[1]
    file_type = _EXTENSIONS.get(extension)
    if file_type is None:
        raise RagError(errors.UNSUPPORTED_FILE_TYPE)

    if file_type == "pdf":
        # The PDF spec allows junk before the header, but real files start with it; a "PDF" whose
        # first kilobyte has no header is far more likely to be something else renamed.
        if b"%PDF-" not in data[:1024]:
            raise RagError(errors.FILE_TYPE_MISMATCH)
    elif file_type == "docx":
        if not data.startswith(b"PK\x03\x04"):
            raise RagError(errors.FILE_TYPE_MISMATCH)
        inspect_docx_archive(data)
    else:
        # NUL bytes mean binary content with a text name — except in UTF-16, which is only
        # accepted with its byte-order mark (see text.py).
        if b"\x00" in data and not data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            raise RagError(errors.FILE_TYPE_MISMATCH)
    return file_type


def inspect_docx_archive(data: bytes) -> None:
    """Reject archive bombs, path tricks and macro documents using only the central directory."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        entries = archive.infolist()
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        raise RagError(errors.DOCX_INVALID) from exc

    if len(entries) > MAX_ZIP_ENTRIES:
        raise RagError(errors.ARCHIVE_TOO_LARGE)
    total = 0
    names = set()
    for entry in entries:
        name = entry.filename
        if name.startswith(("/", "\\")) or ".." in name.split("/") or "\\" in name or ":" in name:
            raise RagError(errors.DOCX_INVALID)
        if entry.flag_bits & 0x1:
            # Encrypted entries — Word never writes these; password-protected .docx files are a
            # different (OLE) container that already fails the "PK" header check.
            raise RagError(errors.DOCX_INVALID)
        total += entry.file_size
        if total > MAX_ZIP_TOTAL_UNCOMPRESSED:
            raise RagError(errors.ARCHIVE_TOO_LARGE)
        if entry.file_size > _RATIO_MIN_ENTRY_SIZE and entry.file_size > MAX_ZIP_RATIO * max(entry.compress_size, 1):
            raise RagError(errors.ARCHIVE_TOO_LARGE)
        names.add(name)

    if not all(part in names for part in DOCX_REQUIRED_PARTS):
        raise RagError(errors.DOCX_INVALID)
    # Macro-enabled documents (.docm saved as .docx) carry a VBA project. Embedded objects
    # (word/embeddings/*) are allowed but never opened by the parser.
    if any(posixpath.basename(name).lower() == "vbaproject.bin" for name in names):
        raise RagError(errors.DOCX_MACROS)
    content_types = archive.read("[Content_Types].xml")[: 1024 * 1024]
    if b"macroEnabled" in content_types or b"vbaProject" in content_types:
        raise RagError(errors.DOCX_MACROS)


def safe_display_name(filename: str, max_length: int = 120) -> str:
    """A file name that's safe to show and log: no directories, control or bidi characters."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch) not in ("Cc", "Cf"))
    return name.strip()[:max_length] or "document"
