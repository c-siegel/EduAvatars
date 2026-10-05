"""
Local TTS Sidecar — HTTP API

A small FastAPI wrapper around sopro (see app/synthesis.py), run as its own optional Docker
container next to the main backend (see docker/local-tts.Dockerfile) so the backend image never
needs PyTorch. The backend calls POST /synthesize instead of running the model in-process,
mirroring how it already calls out to cloud TTS providers.

Custom voices: the backend owns teachers' voice clips and sends one here (PUT /voices/{sha256})
the first time it's needed — POST /synthesize answers 404 VOICE_NOT_STORED until then. Nothing
else is shared between the two services, so this one can run on a different machine.

How to use:
    from app.main import app
    # served via: uvicorn app.main:app --host 0.0.0.0 --port 8080
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import settings
from app.synthesis import (
    InvalidVoiceError,
    UnsupportedLanguageError,
    VoiceNotStoredError,
    delete_voice,
    store_voice,
    synthesize,
)

app = FastAPI(title="EduAvatars Local TTS")


class SynthesizeRequest(BaseModel):
    text: str
    language: str = "de"
    # SHA-256 of a custom reference clip stored via PUT /voices; None uses the language's default.
    voice_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


@app.get("/health")
def health() -> dict:
    """Liveness check — deliberately doesn't force a model load, so it stays fast even before
    the first real synthesis request (the model loads lazily, see app/synthesis.py::_model)."""
    return {"status": "ok"}


@app.post("/synthesize")
def synthesize_endpoint(body: SynthesizeRequest) -> Response:
    """Generate speech for `body.text` in `body.language`, returning a WAV file."""
    try:
        audio_bytes = synthesize(body.text, body.language, body.voice_sha256)
    except VoiceNotStoredError as exc:
        raise HTTPException(status_code=404, detail="VOICE_NOT_STORED") from exc
    except UnsupportedLanguageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=audio_bytes, media_type="audio/wav")


@app.put("/voices/{sha256}", status_code=204)
async def put_voice(sha256: str, request: Request) -> Response:
    """Store a custom reference clip (raw WAV body) under its SHA-256 hash."""
    content = await request.body()
    if len(content) > settings.max_voice_bytes:
        raise HTTPException(status_code=413, detail="Voice clip too large.")
    try:
        store_voice(sha256, content)
    except InvalidVoiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


@app.delete("/voices/{sha256}", status_code=204)
def delete_voice_endpoint(sha256: str) -> Response:
    """Forget a custom reference clip (also fine if it was never stored)."""
    try:
        delete_voice(sha256)
    except InvalidVoiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)
