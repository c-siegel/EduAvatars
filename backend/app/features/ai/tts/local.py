"""
Local-TTS Sidecar

The fallback used when a project has TTS enabled but no cloud key configured — the TTS
counterpart to local Whisper for STT (see features/ai/stt/whisper_local.py), just
out-of-process: the model needs more CPU/RAM than fits alongside the request-serving backend, so
it runs in its own optional container (see local-tts/ and docker/local-tts.Dockerfile). Only
used when settings.local_tts_enabled is set.
"""

import httpx

from app.core.config import settings
from app.features.ai.http import make_ipv4_client

_client = make_ipv4_client()


class LocalTTSClient:
    """Synthesizes via the local-TTS sidecar's POST /synthesize; returns real WAV audio."""

    def synthesize(self, text: str, voice: str | None, language: str) -> tuple[bytes, str]:
        response = _client.post(
            f"{settings.local_tts_url.rstrip('/')}/synthesize",
            json={"text": text, "language": language},
            timeout=settings.local_tts_request_timeout_seconds,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise httpx.HTTPStatusError(f"{exc}: {response.text[:500]}", request=exc.request, response=exc.response) from exc
        return response.content, "audio/wav"
