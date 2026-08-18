"""
Text-to-Speech (TTS) Synthesis

Turns text into spoken audio using the API key configured for a project. Most providers go
through litellm; Cartesia has its own direct HTTP integration (see _synthesize_cartesia)
because litellm doesn't support it.

How to use:
    from app.services.tts_service import synthesize_speech

    audio_bytes, content_type = synthesize_speech(text, project.tts_voice, api_key)
"""

import httpx
import litellm

from app.core.providers import CARTESIA_PROVIDER, OPENAI_COMPATIBLE_PROVIDER, build_model_string, get_provider
from app.models.api_key import UserApiKey
from app.services.api_key_service import effective_api_base
from app.services.crypto_service import reveal_api_key

_CARTESIA_TTS_TIMEOUT = 30.0


class VoiceRequiredError(ValueError):
    """The provider strictly requires a voice for speech synthesis, but none was given.

    Happens in particular during a plain key test (api/api_keys.py::test_key) — there's no
    project yet at that point, and therefore no project voice. This is its own type instead of a
    generic ValueError so the caller can specifically distinguish it from a real
    configuration/access error, instead of incorrectly marking the key as "error".
    """


def synthesize_speech(text: str, tts_voice: str | None, api_key_record: UserApiKey) -> tuple[bytes, str]:
    """Generate speech for `text` using the given key, dispatching to the right provider integration."""
    if api_key_record.provider == CARTESIA_PROVIDER:
        return _synthesize_cartesia(text, tts_voice, api_key_record)
    return _synthesize_litellm(text, tts_voice, api_key_record)


def _synthesize_litellm(text: str, tts_voice: str | None, api_key_record: UserApiKey) -> tuple[bytes, str]:
    """Generate speech via litellm, for every provider except Cartesia."""
    spec = get_provider(api_key_record.provider)
    if spec is None:
        raise ValueError(f"Unbekannter Anbieter '{api_key_record.provider}'.")

    if api_key_record.provider == OPENAI_COMPATIBLE_PROVIDER:
        if not api_key_record.model_id:
            raise ValueError("Für diesen TTS-Key ist kein Modell hinterlegt.")
        model = build_model_string(api_key_record.provider, api_key_record.model_id)
    elif spec.tts_model:
        model = spec.tts_model
    else:
        raise ValueError(f"Sprachausgabe wird für Anbieter '{spec.label}' (noch) nicht unterstützt.")

    api_key = reveal_api_key(api_key_record.encrypted_api_key)
    # Only a deliberately different address is passed to litellm (see api_key_service.py) —
    # previously effective_api_base() wasn't called for TTS at all, so a custom endpoint (e.g.
    # openai_compatible) never had any effect.
    api_base = effective_api_base(api_key_record)
    voice = tts_voice or spec.default_voice

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
        # litellm itself requires a voice for OpenAI-shaped speech synthesis (which includes our
        # "openai_compatible" path, since it goes through the "openai/" prefix) and aborts
        # locally without even contacting the provider (verified in litellm/main.py: "'voice' is
        # required to be passed as a string for OpenAI TTS"). This is not a sign of an invalid
        # key — without a voice (e.g. during a plain key test), this simply can't be checked.
        if "voice" in str(exc).lower():
            raise VoiceRequiredError(
                f"{spec.label} braucht für die Sprachausgabe eine Stimme, die hier nicht bekannt ist."
            ) from exc
        raise
    return response.content, "audio/mpeg"


def _synthesize_cartesia(text: str, tts_voice: str | None, api_key_record: UserApiKey) -> tuple[bytes, str]:
    """Direct HTTP call to Cartesia — litellm doesn't support Cartesia.

    Path, headers, and field names verified against
    https://docs.cartesia.ai/api-reference/tts/bytes (this was originally just a plausible
    sketch — the auth header and version header were outdated/wrong as a result, causing a 404 on
    /tts/bytes in production). Deliberately isolated in this one, clearly named function, so a
    future API change doesn't touch any other code path.
    """
    if not tts_voice:
        raise VoiceRequiredError("Cartesia braucht eine Stimme (Feld „Stimme“ im Projekt) — es gibt keinen Standardwert.")
    if not api_key_record.model_id:
        raise ValueError("Für diesen Cartesia-Key ist kein Modell hinterlegt.")

    api_key = reveal_api_key(api_key_record.encrypted_api_key)
    # From the registry (the single source of truth for provider defaults) instead of a second,
    # independently maintained literal — otherwise the registry's display and the actual call
    # could drift apart if Cartesia's default endpoint ever changes.
    default_api_base = get_provider(CARTESIA_PROVIDER).default_api_base or "https://api.cartesia.ai"
    api_base = (api_key_record.api_base or default_api_base).rstrip("/")

    response = httpx.post(
        f"{api_base}/tts/bytes",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Cartesia-Version": "2026-03-01",
            "Content-Type": "application/json",
        },
        json={
            "model_id": api_key_record.model_id,
            "transcript": text,
            "voice": {"mode": "id", "id": tts_voice},
            "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000},
        },
        timeout=_CARTESIA_TTS_TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Attach the response body, otherwise the log (see
        # public_chat.py::_synthesize_if_enabled) only shows "404 Not Found" without Cartesia's
        # actual error message.
        raise httpx.HTTPStatusError(f"{exc}: {response.text[:500]}", request=exc.request, response=exc.response) from exc
    return response.content, "audio/mpeg"
