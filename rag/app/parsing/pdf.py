"""
PDF Text Extraction (pypdf)

Runs only inside the parser subprocess (see sandbox.py). One Section per page, so every chunk
keeps its page number. Scanned pages without a text layer come back empty — the caller turns an
all-empty result into NO_EXTRACTABLE_TEXT, with Docling (OCR) as the suggested fix.
"""

import io
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app import errors
from app.errors import RagError
from app.parsing.types import ParseResult, Section, normalize_text

# pypdf logs a warning for every slightly malformed object; real-world PDFs are full of them.
logging.getLogger("pypdf").setLevel(logging.ERROR)


def parse_pdf(data: bytes, max_pages: int) -> ParseResult:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # Many teaching PDFs are "encrypted" with an empty user password only to restrict
            # printing or copying — those open fine. Anything needing a real password doesn't.
            try:
                if not reader.decrypt(""):
                    raise RagError(errors.PDF_ENCRYPTED)
            except RagError:
                raise
            except Exception as exc:
                raise RagError(errors.PDF_ENCRYPTED) from exc
        page_count = len(reader.pages)
    except RagError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise RagError(errors.PARSE_FAILED) from exc

    if page_count > max_pages:
        raise RagError(errors.TOO_MANY_PAGES)

    sections = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except MemoryError:
            raise
        except Exception:
            # One broken page (bad font program, unsupported filter) shouldn't lose the rest.
            continue
        text = normalize_text(text)
        if text:
            sections.append(Section(text, page=number))
    return ParseResult(sections, page_count=page_count)
