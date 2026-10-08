"""
Error Codes

Machine-readable codes this service returns (HTTP detail {"code": ...}) or stores on a failed
document. The backend passes them through to the dashboard, which translates them — so they are
part of the contract with backend/app/features/knowledge/rag_client.py and must not be renamed.
"""


class RagError(Exception):
    """A failure with a code the dashboard can explain to the teacher."""

    def __init__(self, code: str, status_code: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


# Upload checks (app/parsing/checks.py)
UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
FILE_TYPE_MISMATCH = "FILE_TYPE_MISMATCH"
FILE_TOO_LARGE = "FILE_TOO_LARGE"
FILE_EMPTY = "FILE_EMPTY"
DOCX_INVALID = "DOCX_INVALID"
DOCX_MACROS = "DOCX_MACROS"
ARCHIVE_TOO_LARGE = "ARCHIVE_TOO_LARGE"

# Parsing (app/parsing/)
PDF_ENCRYPTED = "PDF_ENCRYPTED"
TOO_MANY_PAGES = "TOO_MANY_PAGES"
NO_EXTRACTABLE_TEXT = "NO_EXTRACTABLE_TEXT"
FILE_TOO_COMPLEX = "FILE_TOO_COMPLEX"
PARSE_TIMEOUT = "PARSE_TIMEOUT"
PARSE_FAILED = "PARSE_FAILED"
DOCLING_UNAVAILABLE = "DOCLING_UNAVAILABLE"
DOCLING_FAILED = "DOCLING_FAILED"

# Embedding (app/embedding.py)
EMBEDDING_FAILED = "EMBEDDING_FAILED"
EMBEDDING_MODEL_NOT_ALLOWED = "EMBEDDING_MODEL_NOT_ALLOWED"
EMBEDDING_KEY_MISSING = "EMBEDDING_KEY_MISSING"
EMBEDDING_MISMATCH = "EMBEDDING_MISMATCH"

# Jobs and records
INTERRUPTED = "INTERRUPTED"
DOCUMENT_EXISTS = "DOCUMENT_EXISTS"
DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
