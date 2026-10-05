"""
Text-to-Speech (TTS) Synthesis

Turns text into spoken audio using the API key configured for a project. Most providers go
through litellm (litellm_provider.py); Cartesia and Google Cloud TTS have their own direct HTTP
integrations because litellm doesn't support them.

How to use:
    from app.features.ai.tts import synthesize_speech

    audio_bytes, content_type = synthesize_speech(text, project.tts_voice, api_key, project.spoken_language)
"""

from app.core.providers import CARTESIA_PROVIDER, GOOGLE_CLOUD_TTS_PROVIDER
from app.features.ai.tts.base import TTSClient, VoiceRequiredError
from app.features.ai.tts.cartesia import CartesiaClient
from app.features.ai.tts.google import GoogleCloudTTSClient
from app.features.ai.tts.litellm_provider import LiteLLMSpeechClient
from app.features.ai.tts.normalizer import normalize_for_speech
from app.models.api_key import UserApiKey

__all__ = ["TTSClient", "VoiceRequiredError", "get_tts_client", "synthesize_speech"]


def get_tts_client(api_key_record: UserApiKey) -> TTSClient:
    """The client for the provider of `api_key_record`."""
    if api_key_record.provider == CARTESIA_PROVIDER:
        return CartesiaClient(api_key_record)
    if api_key_record.provider == GOOGLE_CLOUD_TTS_PROVIDER:
        return GoogleCloudTTSClient(api_key_record)
    return LiteLLMSpeechClient(api_key_record)


def synthesize_speech(
    text: str, tts_voice: str | None, api_key_record: UserApiKey, language: str = "de"
) -> tuple[bytes, str]:
    """Generate speech for `text` using the given key, dispatching to the right provider integration.

    `text` is normalized for speech first (see normalizer.py) — decimal numbers and math symbols
    read correctly, but this only affects what's spoken, never what's displayed.
    """
    text = normalize_for_speech(text, language)
    return get_tts_client(api_key_record).synthesize(text, tts_voice)
