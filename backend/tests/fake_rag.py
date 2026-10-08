"""
An In-Memory Stand-In for the Knowledge Service

Implements the routes of rag/app/main.py that the backend calls, closely enough for route tests:
uploads are "indexed" instantly into word-matching passages, statuses can be steered, every call
is recorded. Installed at the backend's one seam to the real service, rag_client._client (see the
`fake_rag` fixture in test_routes_knowledge.py) — nothing above it is faked.
"""

import json
import re

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

LOCAL_MODEL = "jinaai/jina-embeddings-v2-base-de"
TOKEN = "test-rag-token"


class FakeRag:
    def __init__(self) -> None:
        self.uploads: list[dict] = []
        self.documents: dict[str, dict] = {}
        self.chunks: list[dict] = []
        self.deleted_documents: list[str] = []
        self.deleted_kbs: list[str] = []
        self.queries: list[dict] = []
        self.embedding_tests: list[dict] = []
        self.retries: list[dict] = []
        # Set to a code (e.g. "DOCX_MACROS") to refuse the next uploads with it.
        self.reject_upload_with: str | None = None
        # Status new uploads get; "ready" indexes them immediately.
        self.upload_status = "ready"
        self.hard_limits = {"max_upload_mb": 100, "max_pages": 2000, "max_chars": 10_000_000}
        self.app = self._build_app()

    def client(self) -> TestClient:
        return TestClient(self.app)

    def _build_app(self) -> FastAPI:
        app = FastAPI()
        fake = self

        @app.middleware("http")
        async def check_token(request: Request, call_next):
            if request.headers.get("authorization") != f"Bearer {TOKEN}":
                return JSONResponse(status_code=401, content={"detail": {"code": "UNAUTHORIZED"}})
            return await call_next(request)

        @app.get("/capabilities")
        def capabilities():
            return {
                "local_model": LOCAL_MODEL,
                "local_model_dimensions": 768,
                "file_types": ["pdf", "docx", "txt", "md"],
                "hard_limits": fake.hard_limits,
                "docling_available": False,
            }

        @app.post("/documents", status_code=202)
        def upload(file: UploadFile = File(...), meta: str = Form(...)):
            parsed = json.loads(meta)
            data = file.file.read()
            fake.uploads.append({"meta": parsed, "data": data, "filename": file.filename})
            if fake.reject_upload_with:
                return JSONResponse(status_code=422, content={"detail": {"code": fake.reject_upload_with}})
            document_id = parsed["document_id"]
            status = {"document_id": document_id, "status": fake.upload_status, "error_code": None,
                      "page_count": 1, "chunk_count": 1, "char_count": len(data), "truncated": False}
            fake.documents[document_id] = status
            if fake.upload_status == "ready":
                fake.chunks.append({
                    "chunk_id": len(fake.chunks) + 1,
                    "document_id": document_id,
                    "knowledge_base_id": parsed["knowledge_base_id"],
                    "text": data.decode("utf-8", errors="replace"),
                    "page": 1,
                    "heading": None,
                })
            return {"document_id": document_id, "status": "queued"}

        @app.post("/documents/status")
        def statuses(body: dict):
            return [fake.documents[i] for i in body["document_ids"] if i in fake.documents]

        @app.post("/documents/{document_id}/retry", status_code=202)
        def retry(document_id: str, body: dict):
            fake.retries.append({"document_id": document_id, **body})
            status = fake.documents.get(document_id)
            if status is None or not status.get("retryable"):
                return JSONResponse(status_code=409, content={"detail": {"code": "RETRY_NOT_POSSIBLE"}})
            status.update(status="queued", error_code=None, retryable=False)
            return {"document_id": document_id, "status": "queued"}

        @app.delete("/documents/{document_id}", status_code=204)
        def delete_document(document_id: str):
            fake.deleted_documents.append(document_id)
            fake.documents.pop(document_id, None)
            fake.chunks = [c for c in fake.chunks if c["document_id"] != document_id]

        @app.delete("/knowledge-bases/{kb_id}", status_code=204)
        def delete_kb(kb_id: str):
            fake.deleted_kbs.append(kb_id)
            fake.chunks = [c for c in fake.chunks if c["knowledge_base_id"] != kb_id]

        @app.post("/query")
        def query(body: dict):
            fake.queries.append(body)
            words = set(re.findall(r"\w{4,}", body["query"].lower()))
            hits = [
                {**c, "score": 0.03}
                for c in fake.chunks
                if c["knowledge_base_id"] in body["knowledge_base_ids"] and words & set(re.findall(r"\w{4,}", c["text"].lower()))
            ]
            return {"passages": hits[: body["top_k"]]}

        @app.post("/embedding-test")
        def embedding_test(body: dict):
            fake.embedding_tests.append(body)
            return {"dimensions": 1536}

        return app
