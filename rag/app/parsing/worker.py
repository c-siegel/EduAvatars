"""
Parser Subprocess Entry Point

Started by sandbox.py as `python -I -m app.parsing.worker <file_type> <max_pages> <max_chars>
<memory_mb> <cpu_seconds>`. Applies its own resource limits before reading a single byte, reads the
file from stdin, and writes one JSON object to stdout. It never opens the index database or the
network — it only ever sees the bytes it was handed.

Limits are set here rather than via subprocess's preexec_fn: preexec_fn isn't safe in a process
that runs threads (the ingest workers do), while a fresh interpreter setting limits on itself
before doing anything else is equivalent and safe.

POSIX resource limits don't exist on Windows (no `resource` module), where the service only runs in
local development: there, only the parent's wall-clock timeout applies (see sandbox.py, which
logs this once at startup). Production runs in the Linux container, with every limit.
"""

import json
import sys

try:
    import resource
except ImportError:  # Windows
    resource = None


def limits_supported() -> bool:
    return resource is not None


def _limit_resources(memory_mb: int, cpu_seconds: int) -> None:
    if resource is None:
        return
    memory = memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    # Parsing writes no files; stdout is a pipe, which RLIMIT_FSIZE doesn't count.
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main() -> int:
    file_type, max_pages, max_chars, memory_mb, cpu_seconds = (
        sys.argv[1],
        int(sys.argv[2]),
        int(sys.argv[3]),
        int(sys.argv[4]),
        int(sys.argv[5]),
    )
    _limit_resources(memory_mb, cpu_seconds)

    # Imported after the limits, so even module initialisation runs inside them.
    from app import errors
    from app.errors import RagError
    from app.parsing.types import cap_sections

    data = sys.stdin.buffer.read()
    try:
        if file_type == "pdf":
            from app.parsing.pdf import parse_pdf

            result = parse_pdf(data, max_pages)
        elif file_type == "docx":
            from app.parsing.docx import parse_docx

            result = parse_docx(data)
        elif file_type in ("txt", "md"):
            from app.parsing.text import parse_text

            result = parse_text(data, file_type)
        else:
            raise RagError(errors.UNSUPPORTED_FILE_TYPE)
        sections, truncated = cap_sections(result.sections, max_chars)
        payload = {
            "ok": True,
            "page_count": result.page_count,
            "truncated": truncated,
            "sections": [{"text": s.text, "page": s.page, "heading": s.heading} for s in sections],
        }
    except RagError as exc:
        payload = {"ok": False, "error": exc.code}
    except (MemoryError, RecursionError):
        payload = {"ok": False, "error": errors.FILE_TOO_COMPLEX}
    except Exception:
        payload = {"ok": False, "error": errors.PARSE_FAILED}

    # Bytes, not sys.stdout.write: stdout's text encoding is the platform's (cp1252 on Windows,
    # where PYTHONIOENCODING can't help — `-I` ignores it), and a single "ﬁ" ligature or emoji
    # in a document then crashed the whole parse. The parent always decodes UTF-8.
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
