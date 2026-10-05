"""Route-level tests for the key-less speech options: the local-TTS sidecar fallback (when a
project has TTS enabled but no cloud TTS key) and browser-side (WebGPU) transcription."""

import base64

import httpx
import pytest

from app.core.config import settings
from app.features.ai.tts import local
from conftest import browser_url, create_key, create_project, parse_sse, publish

WAV = b"RIFF-fake-wav"


@pytest.fixture
def sidecar(monkeypatch):
    """A fake local-TTS sidecar; returns the list of JSON bodies it received."""
    received: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://tts-local:8080/synthesize"
        import json

        received.append(json.loads(request.content))
        return httpx.Response(200, content=WAV)

    monkeypatch.setattr(local, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    return received


@pytest.fixture
def keyless_tts_project(client, teacher, fake_ai):
    """A published project with an LLM key and TTS enabled, but no TTS key."""
    llm_key = create_key(client)
    project = create_project(client, llmApiKeyId=llm_key["id"], ttsEnabled=True, startPrompt="Hallo")
    project["shareSlug"] = publish(client, project["id"])
    return project


def test_status_endpoints(client, teacher, monkeypatch):
    monkeypatch.setattr(settings, "local_tts_enabled", False)
    monkeypatch.setattr(settings, "browser_stt_enabled", False)
    assert client.get("/providers/local-tts-status").json() == {"available": False}
    assert client.get("/providers/browser-stt-status").json() == {"available": False}
    monkeypatch.setattr(settings, "local_tts_enabled", True)
    monkeypatch.setattr(settings, "browser_stt_enabled", True)
    assert client.get("/providers/local-tts-status").json() == {"available": True}
    assert client.get("/providers/browser-stt-status").json() == {"available": True}


def test_without_sidecar_a_keyless_tts_project_replies_text_only(anon, keyless_tts_project):
    body = anon.post(f"/public/{keyless_tts_project['shareSlug']}/messages", json={"message": "Hi"}).json()
    assert body["audioBase64"] is None
    assert body["ttsMs"] is None


def test_sidecar_synthesizes_for_a_keyless_tts_project(anon, keyless_tts_project, sidecar, monkeypatch):
    monkeypatch.setattr(settings, "local_tts_enabled", True)
    slug = keyless_tts_project["shareSlug"]

    body = anon.post(f"/public/{slug}/messages", json={"message": "Hi"}).json()
    assert base64.b64decode(body["audioBase64"]) == WAV
    assert body["contentType"] == "audio/wav"
    assert sidecar[-1]["language"] == "de"

    chunks = [data for name, data in parse_sse(anon.post(f"/public/{slug}/messages/stream", json={"message": "Hi"}).text) if name == "chunk"]
    assert chunks and all(c["contentType"] == "audio/wav" for c in chunks)


def test_start_audio_via_sidecar_is_stored_and_served_as_wav(client, keyless_tts_project, sidecar, monkeypatch):
    pid = keyless_tts_project["id"]
    not_configured = client.post(f"/projects/{pid}/start-audio")
    assert not_configured.status_code == 400
    assert not_configured.json() == {"detail": "TTS_NOT_CONFIGURED"}

    monkeypatch.setattr(settings, "local_tts_enabled", True)
    generated = client.post(f"/projects/{pid}/start-audio").json()
    served = client.get(browser_url(generated["startAudioUrl"]))
    assert served.content == WAV
    assert served.headers["content-type"] == "audio/wav"


def test_browser_stt_is_on_by_default_and_each_side_can_opt_out(client, anon, keyless_tts_project, monkeypatch):
    slug = keyless_tts_project["shareSlug"]
    monkeypatch.setattr(settings, "browser_stt_enabled", True)
    assert client.get(f"/projects/{keyless_tts_project['id']}").json()["sttBrowserEnabled"] is True
    assert anon.get(f"/public/{slug}").json()["browserSttModelUrl"] == settings.browser_stt_model_url

    client.put(f"/projects/{keyless_tts_project['id']}", json={"sttBrowserEnabled": False})
    assert anon.get(f"/public/{slug}").json()["browserSttModelUrl"] is None

    client.put(f"/projects/{keyless_tts_project['id']}", json={"sttBrowserEnabled": True})
    monkeypatch.setattr(settings, "browser_stt_enabled", False)
    assert anon.get(f"/public/{slug}").json()["browserSttModelUrl"] is None
