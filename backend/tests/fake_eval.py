"""
An In-Memory Stand-In for the Evaluation Service

Implements the routes of rag-eval/app/main.py that the backend calls: every answer gets the same
configurable score per metric, drafts are made from the passages' first sentence, every call is
recorded. Installed at the backend's one seam to the real service, eval_client._client.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from tests.fake_rag import TOKEN


class FakeEval:
    def __init__(self) -> None:
        self.score_calls: list[dict] = []
        self.generate_calls: list[dict] = []
        self.value = 0.8
        # Set to a status code (e.g. 502) to fail every call with it.
        self.fail_with: int | None = None
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
            if fake.fail_with:
                return JSONResponse(status_code=fake.fail_with, content={"detail": {"code": "JUDGE_FAILED"}})
            return await call_next(request)

        @app.get("/health")
        def health():
            return {"status": "ok", "ragas_version": "0.4.3"}

        @app.post("/score")
        def score(body: dict):
            fake.score_calls.append(body)
            items = []
            for item in body["items"]:
                scores = {}
                for metric in body["metrics"]:
                    if metric in ("context_recall", "factual_correctness") and not item.get("reference"):
                        scores[metric] = {"value": None, "error": "NO_REFERENCE"}
                    else:
                        scores[metric] = {"value": fake.value, "error": None}
                items.append({"id": item["id"], "scores": scores})
            return {"items": items}

        @app.post("/generate-testset")
        def generate(body: dict):
            fake.generate_calls.append(body)
            return {
                "cases": [
                    {"question": f"Was steht in Abschnitt {c['chunk_id']}?", "reference": c["text"][:80], "chunk_id": c["chunk_id"]}
                    for c in body["chunks"][: body["size"]]
                ]
            }

        return app
