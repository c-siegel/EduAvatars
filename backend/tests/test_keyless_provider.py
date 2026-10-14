"""Keys stored without a secret (an OpenAI-compatible or Ollama server that needs none) must still
reach the provider with *some* key, never None: litellm fills a missing key from the server's own
environment (OPENAI_API_KEY for the "openai/" route), which would send the operator's key to the
endpoint a teacher typed in — or, without one, fail with "missing credentials"."""

import pytest
from conftest import create_key, create_project, publish

from app.features.api_keys.crypto import KEYLESS_API_KEY

SERVER_SECRET = "sk-operator-own-secret"
ENDPOINT = "https://llm.school.example/v1"


@pytest.fixture
def server_key_in_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SERVER_SECRET)


def _keyless(client, key_type: str, **extra) -> dict:
    return create_key(client, key_type=key_type, provider="openai_compatible", apiKey="", apiBase=ENDPOINT, **extra)


def test_keyless_chat_sends_the_placeholder_not_the_servers_key(client, anon, teacher, fake_ai, server_key_in_env):
    project = create_project(client, llmApiKeyId=_keyless(client, "llm", modelId="llama3")["id"])
    slug = publish(client, project["id"])

    assert anon.post(f"/public/{slug}/messages", json={"message": "Hallo", "history": []}).status_code == 200
    assert anon.post(f"/public/{slug}/messages/stream", json={"message": "Hallo", "history": []}).status_code == 200

    assert len(fake_ai.completion_calls) == 2
    assert all(call["api_key"] == KEYLESS_API_KEY for call in fake_ai.completion_calls)


def test_keyless_key_test_sends_the_placeholder(client, teacher, fake_ai, server_key_in_env):
    key = _keyless(client, "llm", modelId="llama3")
    assert client.post(f"/api-keys/{key['id']}/test").json()["status"] == "active"
    assert fake_ai.completion_calls[-1]["api_key"] == KEYLESS_API_KEY


def test_keyless_tts_sends_the_placeholder(client, anon, teacher, fake_ai, server_key_in_env):
    project = create_project(
        client,
        llmApiKeyId=create_key(client)["id"],
        ttsApiKeyId=_keyless(client, "tts", modelId="tts-1")["id"],
        ttsEnabled=True,
    )
    slug = publish(client, project["id"])

    assert anon.post(f"/public/{slug}/messages", json={"message": "Hallo", "history": []}).status_code == 200
    assert fake_ai.speech_calls and all(call["api_key"] == KEYLESS_API_KEY for call in fake_ai.speech_calls)


def test_a_stored_key_is_passed_unchanged(client, teacher, fake_ai, server_key_in_env):
    key = create_key(client, provider="openai_compatible", apiBase=ENDPOINT, modelId="llama3")
    client.post(f"/api-keys/{key['id']}/test")
    assert fake_ai.completion_calls[-1]["api_key"] == "sk-test-secret-1234"
