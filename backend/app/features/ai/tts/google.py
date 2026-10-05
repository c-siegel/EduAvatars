"""
Google Cloud Text-to-Speech

Direct HTTP call to the classic Google Cloud Text-to-Speech API — litellm doesn't support it.

Distinct from the "gemini" provider (Gemini's own newer, token-priced multimodal TTS) — this is
the older, cheaper, per-character WaveNet/Neural2/Standard voice API. Auth is a plain API key,
same as Google allows for this API in the Cloud Console.
"""

import base64

import httpx

from app.core.providers import GOOGLE_CLOUD_TTS_PROVIDER, get_provider
from app.features.ai.http import make_ipv4_client
from app.features.ai.tts.base import VoiceRequiredError
from app.models.api_key import UserApiKey
from app.services.crypto_service import reveal_api_key

_GOOGLE_CLOUD_TTS_TIMEOUT = 30.0

_client = make_ipv4_client()


def _language_code_from_voice(voice: str) -> str:
    """Extract "de-DE" from a Google voice name like "de-DE-Wavenet-F".

    Google's voice names always start with their BCP-47 language code as the first two
    hyphen-separated segments — there's no separate language field in the request, the voice name
    is the only place it's encoded.
    """
    parts = voice.split("-")
    return "-".join(parts[:2])


class GoogleCloudTTSClient:
    def __init__(self, api_key_record: UserApiKey) -> None:
        self._key = api_key_record

    def synthesize(self, text: str, voice: str | None) -> tuple[bytes, str]:
        if not voice:
            raise VoiceRequiredError(
                "Google Cloud TTS braucht eine Stimme (Feld „Stimme“ im Projekt) — die Sprache steckt im "
                "Stimmennamen, es gibt keinen sprachübergreifenden Standardwert."
            )

        api_key = reveal_api_key(self._key.encrypted_api_key)
        default_api_base = get_provider(GOOGLE_CLOUD_TTS_PROVIDER).default_api_base or "https://texttospeech.googleapis.com/v1"
        api_base = (self._key.api_base or default_api_base).rstrip("/")

        response = _client.post(
            f"{api_base}/text:synthesize",
            # Header, not a "?key=" query param — Google supports both, but a header is less
            # likely to end up copied into a proxy/access log verbatim (consistent with every
            # other provider integration here, which all send the key as an Authorization header).
            headers={"X-Goog-Api-Key": api_key, "Content-Type": "application/json"},
            json={
                "input": {"text": text},
                "voice": {"languageCode": _language_code_from_voice(voice), "name": voice},
                "audioConfig": {"audioEncoding": "MP3"},
            },
            timeout=_GOOGLE_CLOUD_TTS_TIMEOUT,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise httpx.HTTPStatusError(f"{exc}: {response.text[:500]}", request=exc.request, response=exc.response) from exc

        # Unlike every other provider integration here, Google's REST API returns the audio
        # base64-encoded inside a JSON envelope rather than as the raw response body.
        audio_content = response.json()["audioContent"]
        return base64.b64decode(audio_content), "audio/mpeg"
