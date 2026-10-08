"""
First-Line Upload Checks

What the backend rejects before a knowledge-base upload is stored or forwarded (docs/rag-plan.md
§6.1): only the four supported types, the extension and the first bytes must agree, and the file
name becomes a harmless display label. The knowledge service repeats these checks and does the
expensive ones (archive inspection, sandboxed parsing) — it never trusts its caller, and this
layer exists so an obviously wrong file costs neither a request to it nor any quota.

How to use:
    file_type = detect_file_type(filename, data)   # raises KnowledgeUploadRejected
"""

import codecs
import posixpath
import unicodedata

from app.core.error_codes import ErrorCode
from app.core.errors import DomainError

_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "md", ".markdown": "md"}


class KnowledgeUploadRejected(DomainError):
    status_code = 400


def detect_file_type(filename: str, data: bytes) -> str:
    if not data:
        raise KnowledgeUploadRejected(ErrorCode.KNOWLEDGE_FILE_EMPTY)
    file_type = _EXTENSIONS.get(posixpath.splitext(filename.lower().strip())[1])
    if file_type is None:
        raise KnowledgeUploadRejected(ErrorCode.KNOWLEDGE_UNSUPPORTED_FILE_TYPE)
    if file_type == "pdf" and b"%PDF-" not in data[:1024]:
        raise KnowledgeUploadRejected(ErrorCode.KNOWLEDGE_FILE_TYPE_MISMATCH)
    if file_type == "docx" and not data.startswith(b"PK\x03\x04"):
        raise KnowledgeUploadRejected(ErrorCode.KNOWLEDGE_FILE_TYPE_MISMATCH)
    if (
        file_type in ("txt", "md")
        and b"\x00" in data
        and not data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE))
    ):
        raise KnowledgeUploadRejected(ErrorCode.KNOWLEDGE_FILE_TYPE_MISMATCH)
    return file_type


def safe_display_name(filename: str, max_length: int = 120) -> str:
    """The file name without directories, control or bidi-override characters, cut to length —
    shown in the dashboard and in transcripts' source lines, never used as a path."""
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch) not in ("Cc", "Cf"))
    return name.strip()[:max_length] or "document"
