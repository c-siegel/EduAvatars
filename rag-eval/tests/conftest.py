"""
Test Setup for the Evaluation Service

No provider call and no knowledge service in any test. The judge is faked at the litellm seam:
instructor (MD_JSON mode) puts the expected reply's JSON schema into the system message, and
FakeJudge answers with a JSON object built from that schema, so every Ragas metric gets a reply
it can parse. Tests steer the verdicts through `FakeJudge.overrides` (field name → value).
The knowledge service's /embed is replaced by a deterministic bag-of-words embedder.
"""

import hashlib
import json
import math
import os
import re

os.environ.setdefault("RAG_SERVICE_TOKEN", "test-token-for-the-eval-service")

import litellm  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import embeddings  # noqa: E402
from app.config import settings  # noqa: E402

TOKEN = os.environ["RAG_SERVICE_TOKEN"]
AUTH = {"Authorization": f"Bearer {TOKEN}"}
JUDGE = {"model": "openai/fake-judge", "api_key": "sk-secret-judge-key"}

_SCHEMA_MARKER = "json_schema:"
_TRANSLATE_MARKER = "Statements to translate:"


def fake_vector(text: str, dimensions: int = 64) -> list[float]:
    vector = [0.0] * dimensions
    for word in re.findall(r"\w+", text.lower()):
        vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % dimensions] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class FakeJudge:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.overrides: dict[str, object] = {}
        self.fail = False
        self.garbage = False

    def _value(self, schema: dict, defs: dict, name: str | None = None):
        if name in self.overrides:
            return self.overrides[name]
        if "$ref" in schema:
            return self._value(defs[schema["$ref"].rsplit("/", 1)[-1]], defs, name)
        if "anyOf" in schema:
            options = [option for option in schema["anyOf"] if option.get("type") != "null"]
            return self._value(options[0], defs, name)
        if "enum" in schema:
            return schema["enum"][0]
        kind = schema.get("type")
        if kind == "object":
            return {key: self._value(sub, defs, key) for key, sub in schema.get("properties", {}).items()}
        if kind == "array":
            return [self._value(schema.get("items", {}), defs, name)]
        if kind == "integer":
            return 1
        if kind == "number":
            return 1.0
        if kind == "boolean":
            return True
        return f"Fake {name or 'text'}"

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise litellm.exceptions.AuthenticationError("bad key", llm_provider="openai", model=kwargs["model"])
        if self.garbage:
            return litellm.ModelResponse(
                model=kwargs["model"], choices=[{"message": {"role": "assistant", "content": "I cannot do that."}}]
            )
        messages = kwargs["messages"]
        user = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        if _TRANSLATE_MARKER in user:
            strings, _ = json.JSONDecoder().raw_decode(user.split(_TRANSLATE_MARKER, 1)[1].strip())
            reply = {"statements": [f"[de] {s}" for s in strings]}
        else:
            system = "\n".join(m["content"] for m in messages if m["role"] == "system")
            schema, _ = json.JSONDecoder().raw_decode(system.split(_SCHEMA_MARKER, 1)[1].strip())
            reply = self._value(schema, schema.get("$defs", {}))
        return litellm.ModelResponse(
            model=kwargs["model"],
            choices=[{"message": {"role": "assistant", "content": f"```json\n{json.dumps(reply)}\n```"}}],
        )


@pytest.fixture(autouse=True)
def isolated_service(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "rag_eval_data_dir", str(tmp_path / "data"))
    yield


@pytest.fixture
def judge(monkeypatch) -> FakeJudge:
    fake = FakeJudge()
    monkeypatch.setattr(litellm, "acompletion", fake)
    return fake


@pytest.fixture
def embed_calls(monkeypatch) -> list[list[str]]:
    calls: list[list[str]] = []

    async def fake_aembed_texts(self, texts, **kwargs):
        calls.append(list(texts))
        return [fake_vector(text) for text in texts]

    monkeypatch.setattr(embeddings.RagServiceEmbedding, "aembed_texts", fake_aembed_texts)
    monkeypatch.setattr(
        embeddings.RagServiceEmbedding, "embed_texts", lambda self, texts, **kw: [fake_vector(t) for t in texts]
    )
    return calls


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
