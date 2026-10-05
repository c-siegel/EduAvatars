"""
Sopro Model Loading And Synthesis

Loads the sopro TTS model once per process and turns text into WAV audio, using a bundled
reference clip to pick the voice for each language (see Settings.voices_dir).

How to use:
    from app.synthesis import synthesize

    audio_bytes = synthesize("Hallo, wie kann ich helfen?", "de")
"""

import io
import threading
from functools import lru_cache
from pathlib import Path

import soundfile as sf
from sopro import SoproTTS

from app.config import settings

# Bounds how many synthesis calls run at once — see Settings.max_concurrent_synthesis for why a
# BoundedSemaphore (not a plain lock) instead of just serializing everything.
_synthesis_slots = threading.BoundedSemaphore(max(1, settings.max_concurrent_synthesis))


class UnsupportedLanguageError(ValueError):
    """Raised when no bundled reference voice exists for the requested language."""


@lru_cache(maxsize=1)
def _model() -> SoproTTS:
    """Load (once per process) and cache the sopro model, downloading it into model_cache_dir on first use."""
    return SoproTTS.from_pretrained(
        settings.model_repo,
        device="cpu",
        cache_dir=settings.model_cache_dir,
        quantization=settings.quantization,
    )


@lru_cache(maxsize=None)
def _reference(language: str):
    """Precompute (once per language, cached for the process lifetime) the reference-voice embedding.

    Cheap (a few hundred ms, see the project's Phase 0 validation) but still only worth doing
    once — every synthesis call for a language reuses the same precomputed reference instead of
    re-processing its audio file each time.
    """
    voice_path = Path(settings.voices_dir) / f"{language}.wav"
    if not voice_path.is_file():
        raise UnsupportedLanguageError(
            f"No bundled reference voice for language '{language}' (expected {voice_path})."
        )
    return _model().prepare_reference(ref_audio_path=str(voice_path))


def _wav_bytes(wav) -> bytes:
    """Encode a sopro output tensor as 16-bit PCM WAV bytes, mirroring SoproTTS.save_wav's own
    mono-downmix logic (that method only writes to a path, not to an in-memory buffer)."""
    wav = wav.detach().cpu().float()
    if wav.dim() == 2:
        wav = wav[0] if wav.shape[0] == 1 else wav.mean(dim=0)
    buffer = io.BytesIO()
    sf.write(buffer, wav.numpy(), _model().sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def synthesize(text: str, language: str) -> bytes:
    """Generate speech for `text` in `language` as WAV bytes, using the bundled reference voice.

    Raises UnsupportedLanguageError if no reference clip exists for `language`, or TimeoutError
    if no synthesis slot frees up within synthesis_queue_timeout_seconds — callers should treat
    a TimeoutError as "busy, retry later", not as a real failure (same posture as the backend's
    transcription queue).
    """
    ref = _reference(language)
    acquired = _synthesis_slots.acquire(timeout=settings.synthesis_queue_timeout_seconds)
    if not acquired:
        raise TimeoutError("Synthesis queue is full — no free slot within the timeout.")
    try:
        wav = _model().synthesize(text, ref=ref, lang=language)
    finally:
        _synthesis_slots.release()
    return _wav_bytes(wav)
