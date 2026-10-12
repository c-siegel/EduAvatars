"""
Evaluation (Ragas) Service — Internal HTTP API

An optional sidecar (Compose profile "rag-eval", see docker/docker-compose.yml) that scores how
well an avatar answers from its knowledge base, and drafts test questions from the material. It
keeps no data of its own beyond cached prompt translations: the backend sends the questions,
answers, passages and the judge's key with each request and stores the results itself
(backend/app/features/evaluation/).

Only the backend talks to it: the container publishes no port, and every route except /health
requires the shared RAG_SERVICE_TOKEN as a bearer token.

How to use:
    uvicorn app.main:app --host 0.0.0.0 --port 8091
"""

import hmac
import logging
from importlib.metadata import version

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.judge import JudgeFailed
from app.schemas import GenerateRequest, GenerateResponse, ScoreRequest, ScoreResponse
from app.scoring import score_items
from app.testset import generate_cases

logger = logging.getLogger(__name__)

app = FastAPI(title="EduAvatars Evaluation Service", docs_url=None, redoc_url=None)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default 422 echoes the offending input back, which here can include the judge's
    # API key. Field locations are enough to debug a backend bug.
    fields = [".".join(str(part) for part in error.get("loc", ())) for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": {"code": "INVALID_REQUEST", "fields": fields}})


@app.exception_handler(JudgeFailed)
async def judge_failed_handler(_: Request, __: JudgeFailed) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": {"code": "JUDGE_FAILED"}})


def require_token(request: Request) -> None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token.encode(), settings.rag_service_token.encode()):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED"})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ragas_version": version("ragas")}


@app.post("/score", response_model=ScoreResponse, dependencies=[Depends(require_token)])
async def score(body: ScoreRequest) -> ScoreResponse:
    return ScoreResponse(items=await score_items(body))


@app.post("/generate-testset", response_model=GenerateResponse, dependencies=[Depends(require_token)])
async def generate_testset(body: GenerateRequest) -> GenerateResponse:
    return GenerateResponse(cases=await generate_cases(body))
