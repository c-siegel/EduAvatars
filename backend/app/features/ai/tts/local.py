"""
Local-TTS Sidecar

The fallback used when a project has TTS enabled but no cloud key configured — the TTS
counterpart to local Whisper for STT (see features/ai/stt/whisper_local.py), just
out-of-process: the model needs more CPU/RAM than fits alongside the request-serving backend, so
it runs in its own optional container (see local-tts/ and docker/local-tts.Dockerfile). Only
used when settings.local_tts_enabled is set.

Voices: without a voice clip, the sidecar speaks with its default clip for the language. With a
teacher's own clip (see features/media/voices_router.py), the clip is identified by its SHA-256
hash; the sidecar answers 404 VOICE_NOT_STORED until it has that clip, in which case it's sent
once (PUT /voices/{sha256}) and the request retried. So the two services share no files.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import settings
from app.features.ai.http import make_ipv4_client

logger = logging.getLogger(__name__)

_client = make_ipv4_client()


@dataclass(frozen=True)
class VoiceReference:
    """A teacher's voice clip (a WAV file in the backend's storage) to clone the voice from."""

    sha256: str
    path: str


def _url(path: str) -> str:
    return f"{settings.local_tts_url.rstrip('/')}{path}"


def _raise_for_status(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise httpx.HTTPStatusError(f"{exc}: {response.text[:500]}", request=exc.request, response=exc.response) from exc


class LocalTTSClient:
    """Synthesizes via the local-TTS sidecar's POST /synthesize; returns real WAV audio."""

    def __init__(self, voice_clip: VoiceReference | None = None, timeout_seconds: float | None = None):
        self.voice_clip = voice_clip
        self.timeout = timeout_seconds or settings.local_tts_request_timeout_seconds

    def _post_synthesize(self, text: str, language: str) -> httpx.Response:
        body = {"text": text, "language": language}
        if self.voice_clip:
            body["voice_sha256"] = self.voice_clip.sha256
        return _client.post(_url("/synthesize"), json=body, timeout=self.timeout)

    def synthesize(self, text: str, voice: str | None, language: str) -> tuple[bytes, str]:
        """`voice` (a cloud provider's voice name) has no meaning here — the voice comes from
        `voice_clip`, or the sidecar's default for `language`."""
        response = self._post_synthesize(text, language)
        if response.status_code == 404 and self.voice_clip:
            upload = _client.put(
                _url(f"/voices/{self.voice_clip.sha256}"),
                content=Path(self.voice_clip.path).read_bytes(),
                timeout=self.timeout,
            )
            _raise_for_status(upload)
            response = self._post_synthesize(text, language)
        _raise_for_status(response)
        return response.content, "audio/wav"


def forget_voice(sha256: str) -> None:
    """Ask the sidecar to drop a deleted clip's copy. Best effort: the sidecar's copies are only a
    cache, so a sidecar that's down or disabled is no reason to fail the delete."""
    if not settings.local_tts_enabled:
        return
    try:
        _client.delete(_url(f"/voices/{sha256}"), timeout=settings.local_tts_request_timeout_seconds)
    except httpx.HTTPError:
        logger.warning("Couldn't remove voice clip %s from the local-TTS sidecar.", sha256, exc_info=True)
