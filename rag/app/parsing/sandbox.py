"""
Sandboxed Parsing

Untrusted documents are parsed in a short-lived child interpreter (worker.py) with limits on
memory, CPU time, open files and file writes, plus a wall-clock timeout enforced here. A PDF
that explodes into gigabytes when decompressed, a pathological XML tree or a parser bug that
spins forever costs one killed child process — never the service, the index or other jobs.

How to use:
    result = parse_in_sandbox("pdf", data, limits)   # ParseResult, or raises RagError
"""

import json
import logging
import os
import signal
import subprocess
import sys

from app import errors
from app.config import settings
from app.errors import RagError
from app.parsing.types import ParseResult, Section
from app.schemas import DocumentLimits

logger = logging.getLogger(__name__)

# Not defined on Windows, where the CPU limit doesn't exist either (see worker.py).
_SIGXCPU = getattr(signal, "SIGXCPU", None)


def warn_if_unsandboxed() -> None:
    """Called once at startup: say plainly when parsing runs without resource limits."""
    from app.parsing.worker import limits_supported

    if not limits_supported():
        logger.warning(
            "This platform has no POSIX resource limits (Windows): uploaded documents are parsed "
            "with a wall-clock timeout only, without memory or CPU limits. Fine for local "
            "development; run the knowledge service in its Linux container for real use."
        )


def parse_in_sandbox(file_type: str, data: bytes, limits: DocumentLimits) -> ParseResult:
    cpu_seconds = settings.rag_parse_timeout_s
    command = [
        sys.executable,
        # Isolated mode: no PYTHON* environment variables, no user site-packages, and the current
        # directory isn't put on sys.path — the child only imports the installed app package.
        "-I",
        "-m",
        "app.parsing.worker",
        file_type,
        str(limits.max_pages),
        str(limits.max_chars),
        str(settings.rag_parse_memory_mb),
        str(cpu_seconds),
    ]
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
    # Windows' Python needs SYSTEMROOT to initialise (random numbers, sockets) in a bare environment.
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    try:
        completed = subprocess.run(
            command,
            input=data,
            capture_output=True,
            # A little longer than the CPU limit: a child that's blocked rather than busy (it
            # shouldn't be, it does no I/O) still gets killed.
            timeout=cpu_seconds + 15,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RagError(errors.PARSE_TIMEOUT) from exc

    if completed.returncode != 0 or not completed.stdout:
        # Only the tail of stderr and no document text: enough for an operator to see why (a
        # traceback, "MemoryError"), without copying the teacher's material into the logs.
        logger.warning(
            "Parser subprocess for a %s file ended with code %s: %s",
            file_type,
            completed.returncode,
            completed.stderr.decode("utf-8", errors="replace")[-500:].strip() or "(no output)",
        )
        if _SIGXCPU is not None and completed.returncode == -_SIGXCPU:
            # RLIMIT_CPU is the only source of SIGXCPU (the worker sets soft = hard, so it's sent
            # before any SIGKILL) — the teacher should read "took too long", not "too complex".
            raise RagError(errors.PARSE_TIMEOUT)
        # Otherwise killed for memory (RLIMIT_AS → MemoryError the interpreter couldn't even
        # report) or crashed outright.
        raise RagError(errors.FILE_TOO_COMPLEX)
    try:
        payload = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RagError(errors.PARSE_FAILED) from exc
    if not payload.get("ok"):
        raise RagError(payload.get("error") or errors.PARSE_FAILED)
    return ParseResult(
        sections=[Section(s["text"], s.get("page"), s.get("heading")) for s in payload["sections"]],
        page_count=payload.get("page_count"),
        truncated=bool(payload.get("truncated")),
    )
