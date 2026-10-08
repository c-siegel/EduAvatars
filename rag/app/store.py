"""
The Index: SQLite with sqlite-vec and FTS5

Everything this service keeps lives in one SQLite file (<data_dir>/rag.db): which embedding model
each knowledge base uses, the status of each document, the chunk texts, a full-text index over
them (FTS5) and their vectors (sqlite-vec). Only derived text is stored — original files are
deleted as soon as they're parsed (see app/ingest.py).

Vectors go into one vec0 table per dimension (vec_chunks_768, vec_chunks_1536, …), because a
knowledge base can use a local model or any API model and a vec0 column has a fixed size. The
knowledge-base ID is a partition key, so a search only ever scans the requested KBs.

One connection, guarded by a lock: every statement here takes milliseconds, and the ingest
workers and the query route are few, so serialising them is simpler than a connection pool and
never blocks for long.

How to use:
    store = Store("/data/rag.db")
    store.register_knowledge_base(kb_id, config)
"""

import sqlite3
import threading
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlite_vec

from app import errors
from app.chunking import Chunk
from app.errors import RagError
from app.schemas import DocumentStatus, EmbeddingConfig

_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    embedding_mode TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    dimensions INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases(id),
    file_type TEXT NOT NULL,
    parser TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    page_count INTEGER,
    chunk_count INTEGER,
    char_count INTEGER,
    truncated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS documents_kb ON documents(knowledge_base_id);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id),
    knowledge_base_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    page INTEGER,
    heading TEXT,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS chunks_kb ON chunks(knowledge_base_id);
-- Contentless would save space, but then rows can't be deleted by rowid; the text is small next
-- to the vectors anyway. remove_diacritics 2 makes "Uebung"/"Übung"-style variants closer and
-- folds accents for the English/French terms that show up in German teaching material.
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, tokenize = 'unicode61 remove_diacritics 2'
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _vec_table(dimensions: int) -> str:
    if not 1 <= dimensions <= 8192:
        raise RagError(errors.EMBEDDING_FAILED)
    return f"vec_chunks_{int(dimensions)}"


def _placeholders(values: Sequence) -> str:
    return ",".join("?" for _ in values)


class Store:
    def __init__(self, path: str) -> None:
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.enable_load_extension(True)
        sqlite_vec.load(self._db)
        self._db.enable_load_extension(False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(_SCHEMA)
        self._vec_tables: set[str] = {
            row["name"]
            for row in self._db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'vec_chunks_%'")
            if row["name"].removeprefix("vec_chunks_").isdigit()
        }

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # --- Knowledge bases ---------------------------------------------------------------------

    def register_knowledge_base(self, kb_id: str, config: EmbeddingConfig) -> None:
        """Remember the KB's model on first sight; reject a later request with a different one."""
        with self._lock:
            row = self._db.execute(
                "SELECT embedding_mode, embedding_model FROM knowledge_bases WHERE id = ?", (kb_id,)
            ).fetchone()
            if row is None:
                self._db.execute(
                    "INSERT INTO knowledge_bases (id, embedding_mode, embedding_model, created_at) VALUES (?, ?, ?, ?)",
                    (kb_id, config.mode, config.model, _now()),
                )
            elif (row["embedding_mode"], row["embedding_model"]) != (config.mode, config.model):
                raise RagError(errors.EMBEDDING_MISMATCH, status_code=409)

    def check_query_config(self, kb_ids: list[str], config: EmbeddingConfig) -> int | None:
        """The vector dimensions shared by `kb_ids`, or None if none of them has vectors yet.

        Raises EMBEDDING_MISMATCH if any KB was built with another model: the caller groups a
        project's KBs by model and sends one query per group.
        """
        with self._lock:
            rows = self._db.execute(
                f"SELECT embedding_mode, embedding_model, dimensions FROM knowledge_bases WHERE id IN ({_placeholders(kb_ids)})",
                kb_ids,
            ).fetchall()
        dimensions = None
        for row in rows:
            if (row["embedding_mode"], row["embedding_model"]) != (config.mode, config.model):
                raise RagError(errors.EMBEDDING_MISMATCH, status_code=409)
            dimensions = dimensions or row["dimensions"]
        return dimensions

    def delete_knowledge_base(self, kb_id: str) -> None:
        with self._lock:
            ids = [r["id"] for r in self._db.execute("SELECT id FROM documents WHERE knowledge_base_id = ?", (kb_id,))]
            for document_id in ids:
                self._delete_document_locked(document_id)
            self._db.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))

    # --- Documents ---------------------------------------------------------------------------

    def create_document(self, document_id: str, kb_id: str, file_type: str, parser: str) -> None:
        with self._lock:
            try:
                self._db.execute(
                    "INSERT INTO documents (id, knowledge_base_id, file_type, parser, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 'queued', ?, ?)",
                    (document_id, kb_id, file_type, parser, _now(), _now()),
                )
            except sqlite3.IntegrityError as exc:
                raise RagError(errors.DOCUMENT_EXISTS, status_code=409) from exc

    def set_status(self, document_id: str, status: str, error_code: str | None = None) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE documents SET status = ?, error_code = ?, updated_at = ? WHERE id = ?",
                (status, error_code, _now(), document_id),
            )

    def get_document(self, document_id: str) -> sqlite3.Row | None:
        with self._lock:
            return self._db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()

    def set_parser(self, document_id: str, parser: str) -> None:
        with self._lock:
            self._db.execute("UPDATE documents SET parser = ? WHERE id = ?", (parser, document_id))

    def document_exists(self, document_id: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM documents WHERE id = ?", (document_id,)).fetchone() is not None

    def statuses(self, document_ids: list[str]) -> list[DocumentStatus]:
        if not document_ids:
            return []
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM documents WHERE id IN ({_placeholders(document_ids)})", document_ids
            ).fetchall()
        return [
            DocumentStatus(
                document_id=row["id"],
                status=row["status"],
                error_code=row["error_code"],
                page_count=row["page_count"],
                chunk_count=row["chunk_count"],
                char_count=row["char_count"],
                truncated=bool(row["truncated"]),
            )
            for row in rows
        ]

    def unfinished_documents(self) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(
                "SELECT d.id, d.knowledge_base_id, d.file_type, d.parser, k.embedding_mode, k.embedding_model "
                "FROM documents d JOIN knowledge_bases k ON k.id = d.knowledge_base_id "
                "WHERE d.status IN ('queued', 'processing')"
            ).fetchall()

    def store_chunks(
        self,
        document_id: str,
        kb_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
        *,
        page_count: int | None,
        char_count: int,
        truncated: bool,
    ) -> bool:
        """Replace the document's chunks and mark it ready. False if it was deleted meanwhile."""
        dimensions = len(vectors[0]) if vectors else None
        with self._lock:
            if not self.document_exists(document_id):
                return False
            if dimensions is not None:
                row = self._db.execute("SELECT dimensions FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
                if row["dimensions"] is not None and row["dimensions"] != dimensions:
                    raise RagError(errors.EMBEDDING_MISMATCH, status_code=409)
                table = self._ensure_vec_table(dimensions)
            self._db.execute("BEGIN")
            try:
                self._delete_chunks_locked(document_id)
                if dimensions is not None:
                    self._db.execute(
                        "UPDATE knowledge_bases SET dimensions = ? WHERE id = ? AND dimensions IS NULL",
                        (dimensions, kb_id),
                    )
                for chunk, vector in zip(chunks, vectors, strict=True):
                    cursor = self._db.execute(
                        "INSERT INTO chunks (document_id, knowledge_base_id, ordinal, page, heading, text) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (document_id, kb_id, chunk.ordinal, chunk.page, chunk.heading, chunk.text),
                    )
                    chunk_id = cursor.lastrowid
                    self._db.execute(
                        "INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)", (chunk_id, chunk.embedding_text())
                    )
                    self._db.execute(
                        f"INSERT INTO {table} (chunk_id, knowledge_base_id, embedding) VALUES (?, ?, ?)",
                        (chunk_id, kb_id, sqlite_vec.serialize_float32(vector)),
                    )
                self._db.execute(
                    "UPDATE documents SET status = 'ready', error_code = NULL, page_count = ?, chunk_count = ?, "
                    "char_count = ?, truncated = ?, updated_at = ? WHERE id = ?",
                    (page_count, len(chunks), char_count, int(truncated), _now(), document_id),
                )
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
        return True

    def delete_document(self, document_id: str) -> None:
        with self._lock:
            self._delete_document_locked(document_id)

    def _delete_document_locked(self, document_id: str) -> None:
        self._db.execute("BEGIN")
        try:
            self._delete_chunks_locked(document_id)
            self._db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def _delete_chunks_locked(self, document_id: str) -> None:
        ids = [r["id"] for r in self._db.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,))]
        if not ids:
            return
        marks = _placeholders(ids)
        self._db.execute(f"DELETE FROM chunks_fts WHERE rowid IN ({marks})", ids)
        for table in self._vec_tables:
            self._db.execute(f"DELETE FROM {table} WHERE chunk_id IN ({marks})", ids)
        self._db.execute(f"DELETE FROM chunks WHERE id IN ({marks})", ids)

    def _ensure_vec_table(self, dimensions: int) -> str:
        table = _vec_table(dimensions)
        if table not in self._vec_tables:
            self._db.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {table} USING vec0("
                f"chunk_id INTEGER PRIMARY KEY, knowledge_base_id TEXT PARTITION KEY, "
                f"embedding FLOAT[{int(dimensions)}] distance_metric=cosine)"
            )
            self._vec_tables.add(table)
        return table

    # --- Search ------------------------------------------------------------------------------

    def vector_search(self, kb_ids: list[str], dimensions: int, vector: list[float], k: int) -> list[tuple[int, float]]:
        table = _vec_table(dimensions)
        with self._lock:
            if table not in self._vec_tables:
                return []
            rows = self._db.execute(
                f"SELECT chunk_id, distance FROM {table} WHERE embedding MATCH ? AND k = ? "
                f"AND knowledge_base_id IN ({_placeholders(kb_ids)}) ORDER BY distance",
                (sqlite_vec.serialize_float32(vector), k, *kb_ids),
            ).fetchall()
        return [(row["chunk_id"], row["distance"]) for row in rows]

    def keyword_search(self, kb_ids: list[str], match: str, k: int) -> list[tuple[int, float]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT c.id AS chunk_id, bm25(chunks_fts) AS rank FROM chunks_fts "
                "JOIN chunks c ON c.id = chunks_fts.rowid "
                f"WHERE chunks_fts MATCH ? AND c.knowledge_base_id IN ({_placeholders(kb_ids)}) "
                "ORDER BY rank LIMIT ?",
                (match, *kb_ids, k),
            ).fetchall()
        return [(row["chunk_id"], row["rank"]) for row in rows]

    def sample_chunks(self, kb_id: str, n: int) -> list[sqlite3.Row]:
        """Up to `n` random chunks of a KB — the raw material for generated test questions."""
        with self._lock:
            return self._db.execute(
                "SELECT * FROM chunks WHERE knowledge_base_id = ? ORDER BY random() LIMIT ?", (kb_id, n)
            ).fetchall()

    def chunks_by_id(self, chunk_ids: list[int]) -> dict[int, sqlite3.Row]:
        if not chunk_ids:
            return {}
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM chunks WHERE id IN ({_placeholders(chunk_ids)})", chunk_ids
            ).fetchall()
        return {row["id"]: row for row in rows}
