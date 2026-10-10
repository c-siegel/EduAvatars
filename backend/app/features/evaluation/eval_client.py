"""
Client for the Evaluation Service

Thin HTTP wrapper around the optional evaluation (Ragas) service's internal API
(rag-eval/app/main.py), with the shared RAG_SERVICE_TOKEN. Like the knowledge service's client,
two kinds of failure:

- EvalUnavailable: the service couldn't be reached or failed on its side.
- EvalRejected: it refused the request on purpose; `code` is a backend EVALUATION_* code.

Requests carry the judge's decrypted API key. They go to the internal Compose network only
(trust_env=False keeps them away from an outbound proxy), and nothing here logs a body.

How to use:
    from app.features.evaluation import eval_client

    items = eval_client.score({...})
"""

import logging

import httpx

from app.core.config import settings
from app.core.error_codes import ErrorCode

logger = logging.getLogger(__name__)

_client = httpx.Client(trust_env=False)


class EvalUnavailable(Exception):
    """The evaluation service couldn't be reached, or failed on its side."""


class EvalRejected(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# Drafting runs inside a dashboard request (one judge call per passage, four at a time), so it
# gets a budget a teacher can wait for; scoring runs in the background with the long timeout.
GENERATE_TIMEOUT_SECONDS = 180.0
HEALTH_TIMEOUT_SECONDS = 5.0


def _request(method: str, path: str, *, timeout: float | None = None, **kwargs) -> httpx.Response:
    try:
        response = _client.request(
            method,
            f"{settings.rag_eval_service_url.rstrip('/')}{path}",
            headers={"Authorization": f"Bearer {settings.rag_service_token}"},
            timeout=timeout or settings.rag_eval_request_timeout_seconds,
            **kwargs,
        )
    except httpx.HTTPError as exc:
        raise EvalUnavailable(type(exc).__name__) from exc
    if response.status_code == 502:
        # The judge failed every call (wrong key, unknown model) — the teacher's to fix.
        raise EvalRejected(ErrorCode.EVALUATION_JUDGE_FAILED)
    if response.status_code >= 500 or response.status_code == 401:
        logger.warning("Evaluation service answered %s for %s %s", response.status_code, method, path)
        raise EvalUnavailable(str(response.status_code))
    if response.status_code >= 400:
        # Only a backend bug sends an invalid request; the service names the fields, not values.
        logger.warning("Evaluation service refused %s %s: %s", method, path, response.text[:500])
        raise EvalUnavailable(str(response.status_code))
    return response


def health() -> dict:
    return _request("GET", "/health", timeout=HEALTH_TIMEOUT_SECONDS).json()


def score(body: dict) -> list[dict]:
    return _request("POST", "/score", json=body).json()["items"]


def generate_testset(body: dict) -> list[dict]:
    return _request("POST", "/generate-testset", json=body, timeout=GENERATE_TIMEOUT_SECONDS).json()["cases"]
