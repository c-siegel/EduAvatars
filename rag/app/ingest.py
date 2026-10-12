"""
Background Indexing

An upload is accepted (POST /documents) as soon as the cheap checks pass; the real work — parse,
chunk, embed, index — runs here, on a small pool of worker threads, while the document's status
moves queued → processing → ready | failed. The backend polls that status.

The uploaded file waits in <data_dir>/incoming/<document_id>. Once the document is indexed, the
file is deleted: only derived text is kept (docs/rag-plan.md §6.5). If indexing fails, the file is
kept for RAG_FAILED_UPLOAD_RETENTION_HOURS so the teacher can retry with one click (retry()), then
swept away.

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
import time
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
                # The file stays (if it's there): the teacher can retry with a fresh key.
                self._store.set_status(row["id"], "failed", errors.INTERRUPTED)
        self.sweep()

    def sweep(self) -> None:
        """Delete originals nobody can use any more: of deleted documents, of indexed ones, and of
        failed ones past the retention time."""
        cutoff = time.time() - settings.rag_failed_upload_retention_hours * 3600
        for path in self._incoming.iterdir():
            row = self._store.get_document(path.name)
            if row is None or row["status"] == "ready":
                path.unlink(missing_ok=True)
            elif row["status"] == "failed" and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)

    def retryable(self, document_id: str) -> bool:
        row = self._store.get_document(document_id)
        return row is not None and row["status"] == "failed" and self.incoming_path(document_id).exists()

    def retry(self, document_id: str, parser: str, embedding: EmbeddingConfig, limits: DocumentLimits) -> None:
        """Queue a failed document again, from its kept original."""
        row = self._store.get_document(document_id)
        if row is None:
            raise RagError(errors.DOCUMENT_NOT_FOUND, status_code=404)
        if not self.retryable(document_id):
            raise RagError(errors.RETRY_NOT_POSSIBLE, status_code=409)
        self._store.register_knowledge_base(row["knowledge_base_id"], embedding)
        self._store.set_parser(document_id, parser)
        self._store.set_status(document_id, "queued")
        self.submit(Job(document_id, row["knowledge_base_id"], row["file_type"], parser, embedding, limits))

    def _run(self) -> None:
        while True:
            try:
                # Waking up now and then also expires kept originals of failed documents.
                job = self._queue.get(timeout=600)
            except queue.Empty:
                self.sweep()
                continue
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
            data = path.read_bytes()
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
                metadata=result.metadata,
            )
            # Indexed (or deleted meanwhile): the original has no further use.
            path.unlink(missing_ok=True)
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
