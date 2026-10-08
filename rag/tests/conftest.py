"""
Test Setup for the Knowledge Service

No model download and no provider call in any test: the local embedding model is replaced by a
deterministic bag-of-words embedder (similar texts → similar vectors, so search tests are
meaningful), and API embeddings are faked at the litellm seam. Test documents are generated in
code (fixtures.py), never downloaded.
"""

import hashlib
import math
import os
import re

os.environ.setdefault("RAG_SERVICE_TOKEN", "test-token-for-the-rag-service")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import embedding  # noqa: E402
from app.config import settings  # noqa: E402

TOKEN = os.environ["RAG_SERVICE_TOKEN"]
AUTH = {"Authorization": f"Bearer {TOKEN}"}
LOCAL_MODEL = settings.rag_local_embedding_model
DIMENSIONS = embedding.LOCAL_MODELS[LOCAL_MODEL].dimensions


def fake_vector(text: str, dimensions: int = DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    for word in re.findall(r"\w+", text.lower()):
        vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % dimensions] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class FakeLocalModel:
    def embed(self, texts, batch_size=16):
        for text in texts:
            yield fake_vector(text)


@pytest.fixture(autouse=True)
def isolated_service(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "rag_data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(settings, "docling_url", None)
    monkeypatch.setattr(embedding, "_load_local_model", lambda model_id: FakeLocalModel())
    monkeypatch.setattr(embedding, "_local_embedder", None)
    yield


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def local_config() -> dict:
    return {"mode": "local", "model": LOCAL_MODEL}


def upload(client, filename: str, data: bytes, *, document_id="doc-1", kb_id="kb-1", embedding=None, limits=None, parser="light"):
    meta = {
        "document_id": document_id,
        "knowledge_base_id": kb_id,
        "filename": filename,
        "parser": parser,
        "embedding": embedding or local_config(),
    }
    if limits:
        meta["limits"] = limits
    import json

    return client.post(
        "/documents", headers=AUTH, files={"file": (filename, data)}, data={"meta": json.dumps(meta)}
    )


def wait_and_status(client, document_id="doc-1") -> dict:
    client.app.state.ingestor.wait_idle()
    response = client.post("/documents/status", headers=AUTH, json={"document_ids": [document_id]})
    assert response.status_code == 200
    return response.json()[0]
