"""
Speech-to-Text Response Shape

The response shape for the transcription endpoints (app/api/projects.py, app/api/public_chat.py).

How to use:
    from app.models.schemas.speech import TranscriptionOut
"""

from app.core.schema import CamelModel


class TranscriptionOut(CamelModel):
    text: str
    # Wall-clock duration of the whisper call, for the client-side latency log (see
    # pages/PublicChat/index.tsx) — left None by callers that don't measure it (e.g. the
    # configurator preview's transcribe route).
    stt_ms: float | None = None
