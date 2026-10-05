"""
GWDG SAIA Transcription

Direct HTTP call to GWDG's SAIA speech API — an OpenAI-Whisper-API-shaped endpoint that litellm
doesn't support. See core/providers.py's GWDG_SAIA_PROVIDER hint for the caveats this integration
carries (audio-format and language/prompt support unverified against a real account).
"""

import io
import wave

import httpx

from app.core.providers import GWDG_SAIA_PROVIDER, get_provider
from app.features.ai.http import make_ipv4_client
from app.features.api_keys.crypto import reveal_api_key
from app.features.api_keys.models import UserApiKey

_SAIA_TRANSCRIBE_TIMEOUT = 30.0

_client = make_ipv4_client()

_TEST_SILENCE_SECONDS = 0.3
_TEST_SILENCE_SAMPLE_RATE = 16000


def _silent_wav_bytes() -> bytes:
    """A few hundred ms of silence as a minimal WAV file — enough to exercise a real transcription
    call for the API-key "Test" button without needing an actual recorded voice sample."""
    buffer = io.BytesIO()
    frame_count = int(_TEST_SILENCE_SECONDS * _TEST_SILENCE_SAMPLE_RATE)
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(_TEST_SILENCE_SAMPLE_RATE)
        wav_file.writeframes(b"\x00\x00" * frame_count)
    return buffer.getvalue()


class SaiaClient:
    def __init__(self, api_key_record: UserApiKey) -> None:
        self._key = api_key_record

    def transcribe(self, audio_bytes: bytes, language: str, initial_prompt: str | None = None) -> str:
        spec = get_provider(GWDG_SAIA_PROVIDER)
        api_key = reveal_api_key(self._key.encrypted_api_key)
        default_api_base = spec.default_api_base or "https://saia.gwdg.de/v1"
        api_base = (self._key.api_base or default_api_base).rstrip("/")

        # language/prompt aren't shown in GWDG's own example, but both are standard fields of the
        # OpenAI Whisper API this endpoint mimics — sent on a best-effort basis, same posture as
        # the Arcana integration sending "enable-tools" without an explicit doc confirmation.
        data = {"model": spec.stt_model, "response_format": "text", "language": language}
        if initial_prompt:
            data["prompt"] = initial_prompt

        response = _client.post(
            f"{api_base}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "*/*"},
            data=data,
            # The filename's extension is a guess (browsers typically record WebM/Opus) — GWDG's
            # docs don't say whether it's used at all to pick a decoder, or if content-sniffing is
            # enough.
            files={"file": ("audio.webm", audio_bytes, "application/octet-stream")},
            timeout=_SAIA_TRANSCRIBE_TIMEOUT,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Attach the response body, otherwise the log only shows "404 Not Found" with no clue
            # what GWDG actually said (same pattern as the Cartesia/Google TTS integrations).
            raise httpx.HTTPStatusError(f"{exc}: {response.text[:500]}", request=exc.request, response=exc.response) from exc
        # response_format="text" returns the transcript as a plain-text body, not a JSON envelope.
        return response.text.strip()

    def test(self) -> None:
        """Try the stored key with a real (silent) transcription call; raises on an invalid key or
        provider error."""
        self.transcribe(_silent_wav_bytes(), "en", None)
