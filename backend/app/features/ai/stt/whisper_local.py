"""
Local faster-whisper Transcription

The default STT engine: runs inside the backend process via faster-whisper — no separate Whisper
server or cloud service needed. Used whenever a project has no STT key configured.
"""

import io
import os
from functools import lru_cache

from faster_whisper import WhisperModel

from app.core.config import settings
from app.features.ai.stt.capacity import transcription_slot


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


class LocalWhisperClient:
    """Transcribes with the process-wide faster-whisper model."""

    def transcribe(self, audio_bytes: bytes, language: str, initial_prompt: str | None = None) -> str:
        """Passing the language explicitly (instead of letting faster-whisper auto-detect) is both
        faster and more reliable — auto-detection is unreliable on short clips, and a wrong guess
        makes the model snap the audio onto plausible-sounding words in the wrong language
        entirely, rather than just mishearing a word or two.

        Raises TimeoutError if the server is at capacity (see capacity.py::transcription_slot).
        """
        with transcription_slot():
            # faster-whisper decodes the audio format itself (WebM/Opus from the browser) via its
            # bundled PyAV library; no filename or content type is needed for that.
            # vad_filter (voice activity detection) trims silence padding, which a segmented
            # recording has more of at its cut points than one continuous clip.
            segments, _ = _model().transcribe(
                io.BytesIO(audio_bytes), language=language, vad_filter=True, initial_prompt=initial_prompt
            )
            return " ".join(segment.text.strip() for segment in segments).strip()
