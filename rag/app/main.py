"""
Knowledge (RAG) Service — Internal HTTP API

An optional sidecar (Compose profile "rag", see docker/docker-compose.yml) that parses teachers'
documents, indexes them and answers retrieval queries for the backend. Only the backend talks to
it: the container publishes no port, and every route except /health requires the shared
RAG_SERVICE_TOKEN as a bearer token. It knows knowledge bases and documents only by the backend's
opaque IDs — ownership, quotas and the dashboard all live in the backend
(backend/app/features/knowledge/).

See docs/rag-plan.md for the design and rag/README.md for running it.

How to use:
    uvicorn app.main:app --host 0.0.0.0 --port 8090
"""

import hmac
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app import errors
from app.config import settings
from app.embedding import get_embedder, local_model_loaded, local_model_spec
from app.errors import RagError
from app.ingest import Ingestor, Job, write_incoming
from app.parsing.checks import FILE_TYPES, detect_file_type
from app.parsing.docling import docling_available
from app.parsing.sandbox import warn_if_unsandboxed
from app.schemas import (
    Capabilities,
    DocumentMeta,
    DocumentStatus,
    EmbeddingTestRequest,
    EmbeddingTestResponse,
    HardLimits,
    QueryRequest,
    QueryResponse,
    StatusRequest,
)
from app.search import hybrid_search
from app.store import Store

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    local_model_spec()  # fail at startup, not at the first upload, if the model isn't allowed
    warn_if_unsandboxed()
    Path(settings.rag_data_dir).mkdir(parents=True, exist_ok=True)
    store = Store(str(Path(settings.rag_data_dir) / "rag.db"))
    ingestor = Ingestor(store, settings.rag_data_dir)
    ingestor.start()
    app.state.store = store
    app.state.ingestor = ingestor
    try:
        yield
    finally:
        ingestor.stop()
        store.close()


app = FastAPI(title="EduAvatars Knowledge (RAG) Service", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.exception_handler(RagError)
async def rag_error_handler(_: Request, exc: RagError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": {"code": exc.code}})


def require_token(request: Request) -> None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token.encode(), settings.rag_service_token.encode()):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED"})


def _store(request: Request) -> Store:
    return request.app.state.store


@app.get("/health")
def health() -> dict:
    """Liveness only — doesn't load the embedding model, so it stays fast on a cold start."""
    return {"status": "ok", "local_model_loaded": local_model_loaded(), "docling_configured": docling_available()}


@app.get("/capabilities", response_model=Capabilities, dependencies=[Depends(require_token)])
def capabilities() -> Capabilities:
    return Capabilities(
        local_model=settings.rag_local_embedding_model,
        local_model_dimensions=local_model_spec().dimensions,
        file_types=list(FILE_TYPES),
        hard_limits=HardLimits(
            max_upload_mb=settings.rag_hard_max_upload_mb,
            max_pages=settings.rag_hard_max_pages,
            max_chars=settings.rag_hard_max_chars,
        ),
        docling_available=docling_available(),
    )


@app.post("/documents", status_code=202, response_model=DocumentStatus, dependencies=[Depends(require_token)])
def upload_document(request: Request, file: UploadFile = File(...), meta: str = Form(...)) -> DocumentStatus:
    """Accept a document for indexing. The checks that need no parser run right here (a bad file
    is refused before it's stored); parsing and embedding happen in the background."""
    try:
        parsed = DocumentMeta.model_validate(json.loads(meta))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_META"}) from exc
    limits = parsed.limits.clamped()

    max_bytes = limits.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise RagError(errors.FILE_TOO_LARGE, status_code=413)
    file_type = detect_file_type(parsed.filename, data)
    if parsed.embedding.mode == "local" and parsed.embedding.model != settings.rag_local_embedding_model:
        raise RagError(errors.EMBEDDING_MODEL_NOT_ALLOWED)
    if parsed.parser == "docling" and not docling_available():
        raise RagError(errors.DOCLING_UNAVAILABLE)

    store = _store(request)
    ingestor: Ingestor = request.app.state.ingestor
    store.register_knowledge_base(parsed.knowledge_base_id, parsed.embedding)
    store.create_document(parsed.document_id, parsed.knowledge_base_id, file_type, parsed.parser)
    try:
        write_incoming(ingestor.incoming_path(parsed.document_id), data)
    except OSError:
        store.delete_document(parsed.document_id)
        raise
    ingestor.submit(
        Job(parsed.document_id, parsed.knowledge_base_id, file_type, parsed.parser, parsed.embedding, limits)
    )
    return DocumentStatus(document_id=parsed.document_id, status="queued")


@app.post("/documents/status", response_model=list[DocumentStatus], dependencies=[Depends(require_token)])
def document_statuses(body: StatusRequest, request: Request) -> list[DocumentStatus]:
    return _store(request).statuses(body.document_ids)


@app.delete("/documents/{document_id}", status_code=204, dependencies=[Depends(require_token)])
def delete_document(document_id: str, request: Request) -> None:
    """Idempotent: deleting an unknown document succeeds, so the backend can retry freely."""
    _store(request).delete_document(document_id)
    request.app.state.ingestor.incoming_path(document_id).unlink(missing_ok=True)


@app.delete("/knowledge-bases/{knowledge_base_id}", status_code=204, dependencies=[Depends(require_token)])
def delete_knowledge_base(knowledge_base_id: str, request: Request) -> None:
    _store(request).delete_knowledge_base(knowledge_base_id)


@app.post("/query", response_model=QueryResponse, dependencies=[Depends(require_token)])
def query(body: QueryRequest, request: Request) -> QueryResponse:
    passages = hybrid_search(_store(request), body.knowledge_base_ids, body.query, body.top_k, body.embedding)
    return QueryResponse(passages=passages)


@app.post("/embedding-test", response_model=EmbeddingTestResponse, dependencies=[Depends(require_token)])
def embedding_test(body: EmbeddingTestRequest) -> EmbeddingTestResponse:
    """Embed one word with the given config — the API dashboard's "Test key" for embedding keys."""
    return EmbeddingTestResponse(dimensions=len(get_embedder(body.embedding).embed_query("test")))
