"""
litellm Speech Synthesis

Every TTS provider except Cartesia and Google Cloud TTS goes through litellm.speech.
"""

import litellm

from app.core.error_codes import ErrorCode
from app.core.providers import OPENAI_COMPATIBLE_PROVIDER, build_model_string, get_provider
from app.features.ai.tts.base import VoiceRequiredError
from app.features.api_keys.crypto import reveal_api_key
from app.features.api_keys.models import UserApiKey
from app.features.api_keys.resolve import effective_api_base


class LiteLLMSpeechClient:
    """Generate speech via litellm, for every provider except Cartesia and Google Cloud TTS."""

    def __init__(self, api_key_record: UserApiKey) -> None:
        self._key = api_key_record

    def synthesize(self, text: str, voice: str | None) -> tuple[bytes, str]:
        spec = get_provider(self._key.provider)
        if spec is None:
            raise ValueError(ErrorCode.UNKNOWN_PROVIDER)

        if self._key.provider == OPENAI_COMPATIBLE_PROVIDER:
            if not self._key.model_id:
                raise ValueError(ErrorCode.TTS_KEY_MISSING_MODEL)
            model = build_model_string(self._key.provider, self._key.model_id)
        elif spec.tts_model:
            model = spec.tts_model
        else:
            raise ValueError(ErrorCode.TTS_PROVIDER_UNSUPPORTED)

        api_key = reveal_api_key(self._key.encrypted_api_key)
        # Only a deliberately different address is passed to litellm (see
        # features/api_keys/resolve.py::effective_api_base) — previously it wasn't called for TTS
        # at all, so a custom endpoint (e.g. openai_compatible) never had any effect.
        api_base = effective_api_base(self._key)
        voice = voice or spec.default_voice

        try:
            response = litellm.speech(
                model=model,
                input=text,
                api_key=api_key or None,
                response_format="mp3",
                **({"voice": voice} if voice else {}),
                **({"api_base": api_base} if api_base else {}),
            )
        except litellm.BadRequestError as exc:
            # litellm itself requires a voice for OpenAI-shaped speech synthesis (which includes
            # our "openai_compatible" path, since it goes through the "openai/" prefix) and aborts
            # locally without even contacting the provider (verified in litellm/main.py: "'voice'
            # is required to be passed as a string for OpenAI TTS"). This is not a sign of an
            # invalid key — without a voice (e.g. during a plain key test), this simply can't be
            # checked.
            if "voice" in str(exc).lower():
                raise VoiceRequiredError(
                    f"{spec.label} braucht für die Sprachausgabe eine Stimme, die hier nicht bekannt ist."
                ) from exc
            raise
        return response.content, "audio/mpeg"
