"""
Local TTS Sidecar — HTTP API

A small FastAPI wrapper around sopro (see app/synthesis.py), run as its own optional Docker
container next to the main backend (see docker/local-tts.Dockerfile) so the backend image never
needs PyTorch. The backend calls POST /synthesize instead of running the model in-process,
mirroring how it already calls out to cloud TTS providers.

How to use:
    from app.main import app
    # served via: uvicorn app.main:app --host 0.0.0.0 --port 8080
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.synthesis import UnsupportedLanguageError, synthesize

app = FastAPI(title="EduAvatars Local TTS")


class SynthesizeRequest(BaseModel):
    text: str
    language: str = "de"


@app.get("/health")
def health() -> dict:
    """Liveness check — deliberately doesn't force a model load, so it stays fast even before
    the first real synthesis request (the model loads lazily, see app/synthesis.py::_model)."""
    return {"status": "ok"}


@app.post("/synthesize")
def synthesize_endpoint(body: SynthesizeRequest) -> Response:
    """Generate speech for `body.text` in `body.language`, returning a WAV file."""
    try:
        audio_bytes = synthesize(body.text, body.language)
    except UnsupportedLanguageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=audio_bytes, media_type="audio/wav")
