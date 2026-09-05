"""
Speech-to-Text (STT) Transcription

Transcribes uploaded audio to text. By default this runs locally inside the backend process via
faster-whisper — no separate Whisper server or cloud service needed. A project can instead
configure a "bring your own key" (BYOK) STT provider (currently GWDG SAIA, see
core/providers.py::GWDG_SAIA_PROVIDER); passing that key's record dispatches to _transcribe_saia
instead of the local model.

How to use:
    from app.services.stt_service import transcribe_audio

    text = transcribe_audio(audio_bytes, project.spoken_language, api_key_record=stt_key)
"""

import io
import os
import threading
import wave
from functools import lru_cache

import httpx
from faster_whisper import WhisperModel

from app.core.config import settings
from app.core.providers import GWDG_SAIA_PROVIDER, get_provider
from app.models.api_key import UserApiKey
from app.services.crypto_service import reveal_api_key

_SAIA_TRANSCRIBE_TIMEOUT = 30.0
# Same rationale as tts_service.py/llm_service.py's identical transport: forces IPv4 so httpx
# doesn't eat a full per-address timeout on an unreachable IPv6 candidate before falling back.
_IPV4_ONLY_TRANSPORT = httpx.HTTPTransport(local_address="0.0.0.0")
# One Client, created once and never closed — see tts_service.py's identical comment for why
# (closing a Client that owns a shared transport would close every concurrent caller's pool too).
_client = httpx.Client(transport=_IPV4_ONLY_TRANSPORT)

# Bounds how many transcriptions run at once (see Settings.stt_max_concurrent_transcriptions) —
# Whisper is CPU-bound, so running several at once just makes each one slower rather than
# finishing more work sooner. A BoundedSemaphore (not a plain lock) so a size > 1 is possible
# without code changes here.
_transcription_slots = threading.BoundedSemaphore(max(1, settings.stt_max_concurrent_transcriptions))


@lru_cache(maxsize=1)
def _model() -> WhisperModel:
    """Load (once per process) and cache the faster-whisper model."""
    # Loaded once per process (the model is several hundred MB) and reused for every later
    # transcription. CPU/int8 instead of GPU: the server has no GPU, and int8 quantization is
    # the best speed/accuracy trade-off for CPU inference.
    return WhisperModel(
        settings.stt_model,
        device="cpu",
        compute_type="int8",
        download_root=settings.stt_model_cache_dir,
        # 0 (the setting's default) means "use faster-whisper's own default" — passing 0 through
        # would make CTranslate2 interpret it as "use every core", so fall back to a real count.
        cpu_threads=settings.stt_cpu_threads or (os.cpu_count() or 4),
    )


def transcribe_audio(
    audio_bytes: bytes,
    language: str,
    initial_prompt: str | None = None,
    api_key_record: UserApiKey | None = None,
) -> str:
    """Transcribe speech audio to text, decoded as the given language (project.spoken_language).

    Passing the language explicitly (instead of letting faster-whisper auto-detect) is both
    faster and more reliable — auto-detection is unreliable on short clips, and a wrong guess
    makes the model snap the audio onto plausible-sounding words in the wrong language entirely,
    rather than just mishearing a word or two.

    `initial_prompt` carries the text already transcribed earlier in the same recording (see the
    public chat's pause-triggered segmentation, pages/PublicChat/index.tsx) — without it, each
    segment is decoded with no cross-segment context, which costs accuracy right at the seam
    between two segments. None (the default) is the original, single-shot behavior.

    `api_key_record` is the project's resolved STT key (services/api_key_service.py::
    resolve_stt_key), if any. None (the default) keeps using the local model below; a GWDG SAIA
    key dispatches to _transcribe_saia instead.

    Raises TimeoutError if no transcription slot frees up within
    stt_transcription_queue_timeout_seconds (see _transcription_slots above) — callers should
    treat that the same as any other transcription failure (a 503 to the caller, not a 500),
    since it means the server is legitimately at capacity, not broken.
    """
    if api_key_record is not None and api_key_record.provider == GWDG_SAIA_PROVIDER:
        return _transcribe_saia(audio_bytes, language, initial_prompt, api_key_record)

    acquired = _transcription_slots.acquire(timeout=settings.stt_transcription_queue_timeout_seconds)
    if not acquired:
        raise TimeoutError("Transcription queue is full — no free slot within the timeout.")
    try:
        # faster-whisper decodes the audio format itself (WebM/Opus from the browser) via its
        # bundled PyAV library; no filename or content type is needed for that.
        # vad_filter (voice activity detection) trims silence padding, which a segmented
        # recording has more of at its cut points than one continuous clip.
        segments, _ = _model().transcribe(
            io.BytesIO(audio_bytes), language=language, vad_filter=True, initial_prompt=initial_prompt
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
    finally:
        _transcription_slots.release()


def _transcribe_saia(
    audio_bytes: bytes, language: str, initial_prompt: str | None, api_key_record: UserApiKey
) -> str:
    """Direct HTTP call to GWDG's SAIA speech API — an OpenAI-Whisper-API-shaped endpoint that
    litellm doesn't support. See core/providers.py's GWDG_SAIA_PROVIDER hint for the caveats this
    integration carries (audio-format and language/prompt support unverified against a real
    account).
    """
    spec = get_provider(GWDG_SAIA_PROVIDER)
    api_key = reveal_api_key(api_key_record.encrypted_api_key)
    default_api_base = spec.default_api_base or "https://saia.gwdg.de/v1"
    api_base = (api_key_record.api_base or default_api_base).rstrip("/")

    # language/prompt aren't shown in GWDG's own example, but both are standard fields of the
    # OpenAI Whisper API this endpoint mimics — sent on a best-effort basis, same posture as
    # llm_service.py's _send_chat_arcana sending "enable-tools" without an explicit doc confirmation.
    data = {"model": spec.stt_model, "response_format": "text", "language": language}
    if initial_prompt:
        data["prompt"] = initial_prompt

    response = _client.post(
        f"{api_base}/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "*/*"},
        data=data,
        # The filename's extension is a guess (browsers typically record WebM/Opus) — GWDG's docs
        # don't say whether it's used at all to pick a decoder, or if content-sniffing is enough.
        files={"file": ("audio.webm", audio_bytes, "application/octet-stream")},
        timeout=_SAIA_TRANSCRIBE_TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Attach the response body, otherwise the log only shows "404 Not Found" with no clue
        # what GWDG actually said (same pattern as tts_service.py's Cartesia/Google integrations).
        raise httpx.HTTPStatusError(f"{exc}: {response.text[:500]}", request=exc.request, response=exc.response) from exc
    # response_format="text" returns the transcript as a plain-text body, not a JSON envelope.
    return response.text.strip()


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


def test_stt_key(api_key_record: UserApiKey) -> None:
    """Try a stored STT key with a real (silent) transcription call; raises on an invalid key or
    provider error. Only a GWDG SAIA key reaches here — a plain faster-whisper setup has no stored
    key to test (see api/api_keys.py::test_key)."""
    _transcribe_saia(_silent_wav_bytes(), "en", None, api_key_record)
