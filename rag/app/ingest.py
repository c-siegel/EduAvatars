"""
Background Indexing

An upload is accepted (POST /documents) as soon as the cheap checks pass; the real work — parse,
chunk, embed, index — runs here, on a small pool of worker threads, while the document's status
moves queued → processing → ready | failed. The backend polls that status.

The uploaded file waits in <data_dir>/incoming/<document_id> and is deleted as soon as it has been
parsed, whatever the outcome: only derived text is ever kept (docs/rag-plan.md §6.5).

After a restart, documents that were still queued or processing are picked up again if they use
the local model and their file is still there. Documents embedded with an API key can't be: the
key was only ever held in memory, so they fail with INTERRUPTED and the teacher retries.

How to use:
    ingestor = Ingestor(store, data_dir)
    ingestor.start()
    ingestor.submit(Job(...))
"""

import logging
import os
import queue
import threading
from dataclasses import dataclass
from pathlib import Path

from app import errors
from app.chunking import chunk_sections
from app.config import settings
from app.embedding import chunk_size_for, get_embedder
from app.errors import RagError
from app.parsing.docling import parse_with_docling
from app.parsing.sandbox import parse_in_sandbox
from app.parsing.types import ParseResult
from app.schemas import DocumentLimits, EmbeddingConfig
from app.store import Store

logger = logging.getLogger(__name__)


@dataclass
class Job:
    document_id: str
    knowledge_base_id: str
    file_type: str
    parser: str
    embedding: EmbeddingConfig
    limits: DocumentLimits


class Ingestor:
    def __init__(self, store: Store, data_dir: str) -> None:
        self._store = store
        self._incoming = Path(data_dir) / "incoming"
        self._incoming.mkdir(parents=True, exist_ok=True)
        self._queue: queue.Queue[Job | None] = queue.Queue()
        self._threads: list[threading.Thread] = []

    def incoming_path(self, document_id: str) -> Path:
        return self._incoming / document_id

    def start(self) -> None:
        self._recover()
        for index in range(max(1, settings.rag_ingest_workers)):
            thread = threading.Thread(target=self._run, name=f"ingest-{index}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        for _ in self._threads:
            self._queue.put(None)
        for thread in self._threads:
            thread.join(timeout=5)
        self._threads.clear()

    def submit(self, job: Job) -> None:
        self._queue.put(job)

    def wait_idle(self) -> None:
        """Block until every submitted job is done (used by tests)."""
        self._queue.join()

    def _recover(self) -> None:
        for row in self._store.unfinished_documents():
            path = self.incoming_path(row["id"])
            if row["embedding_mode"] == "local" and path.exists():
                self.submit(
                    Job(
                        row["id"],
                        row["knowledge_base_id"],
                        row["file_type"],
                        row["parser"],
                        EmbeddingConfig(mode="local", model=row["embedding_model"]),
                        DocumentLimits().clamped(),
                    )
                )
            else:
                self._store.set_status(row["id"], "failed", errors.INTERRUPTED)
                path.unlink(missing_ok=True)
        # Leftovers whose document row is gone (deleted while the service was down).
        for path in self._incoming.iterdir():
            if not self._store.document_exists(path.name):
                path.unlink(missing_ok=True)

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            try:
                if job is None:
                    return
                self.process(job)
            finally:
                self._queue.task_done()

    def process(self, job: Job) -> None:
        path = self.incoming_path(job.document_id)
        if not self._store.document_exists(job.document_id):
            path.unlink(missing_ok=True)
            return
        self._store.set_status(job.document_id, "processing")
        try:
            try:
                data = path.read_bytes()
            finally:
                # Parsed or not, the original never stays on disk.
                path.unlink(missing_ok=True)
            result = self._parse(job, data)
            del data
            if not result.sections:
                raise RagError(errors.NO_EXTRACTABLE_TEXT)

            embedder = get_embedder(job.embedding)
            size, overlap = chunk_size_for(job.embedding)
            chunks = chunk_sections(result.sections, size, overlap)
            vectors = embedder.embed_passages([chunk.embedding_text() for chunk in chunks])
            stored = self._store.store_chunks(
                job.document_id,
                job.knowledge_base_id,
                chunks,
                vectors,
                page_count=result.page_count,
                char_count=result.char_count,
                truncated=result.truncated,
            )
            if stored:
                logger.info("Indexed document %s: %d chunks", job.document_id, len(chunks))
        except RagError as exc:
            logger.info("Document %s failed: %s", job.document_id, exc.code)
            self._store.set_status(job.document_id, "failed", exc.code)
        except Exception:
            logger.exception("Document %s failed unexpectedly", job.document_id)
            self._store.set_status(job.document_id, "failed", errors.PARSE_FAILED)

    def _parse(self, job: Job, data: bytes) -> ParseResult:
        if job.parser == "docling" and job.file_type in ("pdf", "docx"):
            return parse_with_docling(job.file_type, data, job.limits)
        return parse_in_sandbox(job.file_type, data, job.limits)


def write_incoming(path: Path, data: bytes) -> None:
    """Write an upload so that only this service's user can read it."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
