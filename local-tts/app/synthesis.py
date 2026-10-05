"""
Sopro Model Loading And Synthesis

Loads the sopro TTS model once per process and turns text into WAV audio. The voice comes from a
reference clip: either a teacher's own clip, sent by the backend and stored by its SHA-256 hash
(see store_voice), or the bundled default clip for the language (see Settings.voices_dir).

How to use:
    from app.synthesis import synthesize

    audio_bytes = synthesize("Hallo, wie kann ich helfen?", "de")
    audio_bytes = synthesize("Hallo!", "de", voice_sha256="3f2a...")  # a stored custom clip
"""

import hashlib
import io
import os
import re
import threading
from functools import lru_cache
from pathlib import Path

import soundfile as sf
from sopro import SoproTTS

from app.config import settings

# Bounds how many synthesis calls run at once — see Settings.max_concurrent_synthesis for why a
# BoundedSemaphore (not a plain lock) instead of just serializing everything.
_synthesis_slots = threading.BoundedSemaphore(max(1, settings.max_concurrent_synthesis))

# Also what keeps a hash from being used as a path (no "/" or ".." can get through).
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class UnsupportedLanguageError(ValueError):
    """Raised when no bundled reference voice exists for the requested language."""


class VoiceNotStoredError(LookupError):
    """Raised when a custom voice hasn't been sent to this service yet — the backend then sends
    it (PUT /voices/{sha256}) and retries."""


class InvalidVoiceError(ValueError):
    """Raised when an uploaded clip doesn't match its hash or isn't readable audio."""


@lru_cache(maxsize=1)
def _model() -> SoproTTS:
    """Load (once per process) and cache the sopro model, downloading it into model_cache_dir on first use."""
    return SoproTTS.from_pretrained(
        settings.model_repo,
        device="cpu",
        cache_dir=settings.model_cache_dir,
        quantization=settings.quantization,
    )


@lru_cache(maxsize=32)
def _reference(voice_path: str):
    """Precompute (once per clip, cached) the reference-voice embedding.

    Cheap (a few hundred ms) but still only worth doing once — every synthesis call with the same
    clip reuses it instead of re-processing the audio file each time. Keyed by path, and a custom
    clip's path contains its content hash, so a changed clip never hits a stale entry.
    """
    return _model().prepare_reference(ref_audio_path=voice_path)


def _custom_voice_path(sha256: str) -> Path:
    if not _SHA256_RE.match(sha256):
        raise InvalidVoiceError("Voice id must be a lowercase SHA-256 hex digest.")
    return Path(settings.custom_voices_dir) / f"{sha256}.wav"


def store_voice(sha256: str, content: bytes) -> None:
    """Keep a custom reference clip under its hash, after checking the hash and that it's audio."""
    path = _custom_voice_path(sha256)
    if hashlib.sha256(content).hexdigest() != sha256:
        raise InvalidVoiceError("Content doesn't match its SHA-256 hash.")
    try:
        sf.info(io.BytesIO(content))
    except Exception as exc:
        raise InvalidVoiceError("Not a readable audio file.") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    # Written under a temporary name and renamed, so a parallel synthesis never reads half a file.
    temp = path.with_suffix(".part")
    temp.write_bytes(content)
    os.replace(temp, path)


def delete_voice(sha256: str) -> None:
    """Forget a custom clip (a no-op if it isn't stored)."""
    path = _custom_voice_path(sha256)
    path.unlink(missing_ok=True)
    _reference.cache_clear()  # drop its embedding too; the others are cheap to recompute


def _wav_bytes(wav) -> bytes:
    """Encode a sopro output tensor as 16-bit PCM WAV bytes, mirroring SoproTTS.save_wav's own
    mono-downmix logic (that method only writes to a path, not to an in-memory buffer)."""
    wav = wav.detach().cpu().float()
    if wav.dim() == 2:
        wav = wav[0] if wav.shape[0] == 1 else wav.mean(dim=0)
    buffer = io.BytesIO()
    sf.write(buffer, wav.numpy(), _model().sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def synthesize(text: str, language: str, voice_sha256: str | None = None) -> bytes:
    """Generate speech for `text` in `language` as WAV bytes.

    Uses the stored custom clip `voice_sha256` if given, otherwise the bundled default clip for
    `language`. Raises VoiceNotStoredError if that custom clip isn't stored here (yet),
    UnsupportedLanguageError if there's no default clip for `language`, or TimeoutError if no
    synthesis slot frees up within synthesis_queue_timeout_seconds — callers should treat a
    TimeoutError as "busy, retry later", not as a real failure (same posture as the backend's
    transcription queue).
    """
    if voice_sha256:
        voice_path = _custom_voice_path(voice_sha256)
        if not voice_path.is_file():
            raise VoiceNotStoredError(voice_sha256)
    else:
        voice_path = Path(settings.voices_dir) / f"{language}.wav"
        if not voice_path.is_file():
            raise UnsupportedLanguageError(
                f"No bundled reference voice for language '{language}' (expected {voice_path})."
            )
    ref = _reference(str(voice_path))
    acquired = _synthesis_slots.acquire(timeout=settings.synthesis_queue_timeout_seconds)
    if not acquired:
        raise TimeoutError("Synthesis queue is full — no free slot within the timeout.")
    try:
        wav = _model().synthesize(text, ref=ref, lang=language)
    finally:
        _synthesis_slots.release()
    return _wav_bytes(wav)
