# EduAvatars local TTS (optional)

A self-hosted text-to-speech (TTS) engine that runs next to the cloud TTS providers (OpenAI,
Google Gemini, Cartesia, Google Cloud TTS) — for projects that leave the TTS key unset, so
nobody needs a cloud API key just to hear an avatar speak. Backed by
[sopro](https://github.com/samuel-vitorino/sopro), a small (120M-parameter) voice-cloning model
that runs comfortably on a CPU.

See the [root README](../README.md#local-text-to-speech-optional) for how this fits into the
rest of the app — this file only covers running the sidecar itself.

## Why a separate service?

The main backend (`backend/`) stays lightweight on purpose — no PyTorch, no multi-hundred-MB
model download. This sidecar is its own process (and, eventually, its own optional Docker
container) so a deployment that doesn't want the extra CPU/RAM/disk footprint never pays for it:
the backend only calls out to this service over HTTP, and only when `TTS_LOCAL_ENABLED` (backend
setting; see root README) is turned on.

**Current status**: works today as a manually-run companion process for local development
(Deploy A). It is not yet wired into `docker/docker-compose.yml` as a Deploy B service — that's
tracked as follow-up work, not yet available.

## Running it

```bash
cd local-tts
python3 -m venv .venv

# CPU-only build — the default PyPI torch wheel pulls several GB of unused CUDA/NVIDIA
# libraries even on a machine with no GPU.
./.venv/bin/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
./.venv/bin/pip install -e .

export TTS_MODEL_CACHE_DIR="$PWD/.cache"
export TTS_VOICES_DIR="$PWD/voices"
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 --app-dir .
```

The model (~600MB) downloads from Hugging Face into `TTS_MODEL_CACHE_DIR` on the first request
and is cached there afterwards — the first call takes a few minutes, every one after that is
fast (well under a second to start speaking, on a modest multi-core CPU).

Then point the backend at it (see the [root README](../README.md#local-text-to-speech-optional)):

```bash
export LOCAL_TTS_ENABLED=true
export LOCAL_TTS_URL=http://127.0.0.1:8080
```

## Reference voices

`voices/` ships empty on purpose — see [`voices/README.md`](voices/README.md). Sopro clones a
voice from a short reference clip rather than having voices baked into the model, and picking
whose voice becomes a deployment's default is a licensing/content decision for a human, not
something to bundle into the repo. Drop a `<language>.wav` file in there (5–20 seconds of clear
speech) for each language you want available; a language with no file simply isn't offered.

## API

- `GET /health` — liveness check, always fast (doesn't force the model to load).
- `POST /synthesize` — `{"text": "...", "language": "de"}` → WAV audio bytes. Returns `400` for a
  language with no reference voice, `503` if the concurrency limit (`TTS_MAX_CONCURRENT_SYNTHESIS`)
  is hit and no slot frees up in time.

## Settings

All read from environment variables prefixed `TTS_` (see `app/config.py` for the full list and
defaults): `TTS_MODEL_REPO`, `TTS_MODEL_CACHE_DIR`, `TTS_VOICES_DIR`, `TTS_QUANTIZATION`
(`int8` trades quality for lower CPU/RAM use — untested here, the default full-precision mode is
what's actually been measured), `TTS_MAX_CONCURRENT_SYNTHESIS`,
`TTS_SYNTHESIS_QUEUE_TIMEOUT_SECONDS`.
