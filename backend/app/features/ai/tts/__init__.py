"""
Text-to-Speech (TTS) Synthesis

Turns text into spoken audio using the API key configured for a project. Most providers go
through litellm (litellm_provider.py); Cartesia and Google Cloud TTS have their own direct HTTP
integrations because litellm doesn't support them. With no key configured, synthesis falls back
to the optional local-TTS sidecar (local.py) — the TTS counterpart to the local Whisper fallback
for STT.

How to use:
    from app.features.ai.tts import synthesize_speech

    audio_bytes, content_type = synthesize_speech(text, project.tts_voice, api_key, project.spoken_language)
"""

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.providers import CARTESIA_PROVIDER, GOOGLE_CLOUD_TTS_PROVIDER
from app.features.ai.tts.base import TTSClient, VoiceRequiredError
from app.features.ai.tts.cartesia import CartesiaClient
from app.features.ai.tts.google import GoogleCloudTTSClient
from app.features.ai.tts.litellm_provider import LiteLLMSpeechClient
from app.features.ai.tts.local import LocalTTSClient
from app.features.ai.tts.normalizer import normalize_for_speech
from app.features.api_keys.models import UserApiKey

__all__ = ["TTSClient", "VoiceRequiredError", "get_tts_client", "synthesize_speech"]


def get_tts_client(api_key_record: UserApiKey | None) -> TTSClient:
    """The client for the provider of `api_key_record`, or the local-TTS sidecar for None.

    Raises ValueError(TTS_NOT_CONFIGURED) for None when the sidecar isn't enabled either
    (settings.local_tts_enabled) — callers treat that like any other TTS failure.
    """
    if api_key_record is None:
        if not settings.local_tts_enabled:
            raise ValueError(ErrorCode.TTS_NOT_CONFIGURED)
        return LocalTTSClient()
    if api_key_record.provider == CARTESIA_PROVIDER:
        return CartesiaClient(api_key_record)
    if api_key_record.provider == GOOGLE_CLOUD_TTS_PROVIDER:
        return GoogleCloudTTSClient(api_key_record)
    return LiteLLMSpeechClient(api_key_record)


def synthesize_speech(
    text: str, tts_voice: str | None, api_key_record: UserApiKey | None, language: str = "de"
) -> tuple[bytes, str]:
    """Generate speech for `text`, dispatching to the right provider integration for the given key.

    `text` is normalized for speech first (see normalizer.py) — decimal numbers and math symbols
    read correctly, but this only affects what's spoken, never what's displayed.

    `api_key_record` is None when the caller has TTS enabled but no cloud key configured — same
    convention as features/ai/stt/__init__.py::transcribe_audio's `api_key_record` (see get_tts_client).
    """
    text = normalize_for_speech(text, language)
    return get_tts_client(api_key_record).synthesize(text, tts_voice, language)
