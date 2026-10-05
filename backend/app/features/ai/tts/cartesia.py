"""
Cartesia Speech Synthesis

Direct HTTP call to Cartesia — litellm doesn't support Cartesia.
"""

import httpx

from app.core.error_codes import ErrorCode
from app.core.providers import CARTESIA_PROVIDER, get_provider
from app.features.ai.http import make_ipv4_client
from app.features.ai.tts.base import VoiceRequiredError
from app.models.api_key import UserApiKey
from app.services.crypto_service import reveal_api_key

_CARTESIA_TTS_TIMEOUT = 30.0

_client = make_ipv4_client()


class CartesiaClient:
    """Path, headers, and field names verified against
    https://docs.cartesia.ai/api-reference/tts/bytes (this was originally just a plausible
    sketch — the auth header and version header were outdated/wrong as a result, causing a 404 on
    /tts/bytes in production). Deliberately isolated in this one module, so a future API change
    doesn't touch any other code path.
    """

    def __init__(self, api_key_record: UserApiKey) -> None:
        self._key = api_key_record

    def synthesize(self, text: str, voice: str | None) -> tuple[bytes, str]:
        if not voice:
            raise VoiceRequiredError("Cartesia braucht eine Stimme (Feld „Stimme“ im Projekt) — es gibt keinen Standardwert.")
        if not self._key.model_id:
            raise ValueError(ErrorCode.CARTESIA_KEY_MISSING_MODEL)

        api_key = reveal_api_key(self._key.encrypted_api_key)
        # From the registry (the single source of truth for provider defaults) instead of a
        # second, independently maintained literal — otherwise the registry's display and the
        # actual call could drift apart if Cartesia's default endpoint ever changes.
        default_api_base = get_provider(CARTESIA_PROVIDER).default_api_base or "https://api.cartesia.ai"
        api_base = (self._key.api_base or default_api_base).rstrip("/")

        response = _client.post(
            f"{api_base}/tts/bytes",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Cartesia-Version": "2026-03-01",
                "Content-Type": "application/json",
            },
            json={
                "model_id": self._key.model_id,
                "transcript": text,
                "voice": {"mode": "id", "id": voice},
                "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000},
            },
            timeout=_CARTESIA_TTS_TIMEOUT,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Attach the response body, otherwise the log only shows "404 Not Found" without
            # Cartesia's actual error message.
            raise httpx.HTTPStatusError(f"{exc}: {response.text[:500]}", request=exc.request, response=exc.response) from exc
        return response.content, "audio/mpeg"
