"""
Speech-to-Text (STT) Transcription

Transcribes uploaded audio to German text using faster-whisper, running directly inside the
backend process — no separate Whisper server or cloud service needed.

How to use:
    from app.services.stt_service import transcribe_audio

    text = transcribe_audio(audio_bytes)
"""

import io
from functools import lru_cache

from faster_whisper import WhisperModel

from app.core.config import settings


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
    )


def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe German speech audio to text."""
    # Language is fixed to German (target audience: German schools) — no automatic language
    # detection, no detour through Project.spoken_language anymore. faster-whisper decodes the
    # audio format itself (WebM/Opus from the browser) via its bundled PyAV library; no filename
    # or content type is needed for that.
    segments, _ = _model().transcribe(io.BytesIO(audio_bytes), language="de")
    return " ".join(segment.text.strip() for segment in segments).strip()
