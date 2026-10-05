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

In production it runs as the optional `tts-local` service in `docker/docker-compose.yml` (image
`chsiegel/eduavatars:local-tts`, enabled with the `local-tts` Compose profile — see
[docker/README.md](../docker/README.md#local-text-to-speech-optional)); in development, run it by
hand as below.

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

Two kinds of reference clip:

- **Teachers' own clips** (Dashboard → Voices): the backend stores them and sends one here the
  first time a project or preview needs it — see "API" below. Nothing to set up on this side.
- **Default voices**, for projects that haven't picked a clip:

`voices/` ships empty on purpose — see [`voices/README.md`](voices/README.md). Sopro clones a
voice from a short reference clip rather than having voices baked into the model, and picking
whose voice becomes a deployment's default is a licensing/content decision for a human, not
something to bundle into the repo. Drop a `<language>.wav` file in there (5–20 seconds of clear
speech) for each language you want available; a language with no file simply isn't offered.

## API

- `GET /health` — liveness check, always fast (doesn't force the model to load).
- `POST /synthesize` — `{"text": "...", "language": "de", "voice_sha256": null}` → WAV audio
  bytes. With `voice_sha256`, the voice is cloned from that stored clip; without it, from the
  default clip for `language`. Returns `404 VOICE_NOT_STORED` for a clip this service doesn't
  have (yet), `400` for a language with no default voice, `503` if the concurrency limit
  (`TTS_MAX_CONCURRENT_SYNTHESIS`) is hit and no slot frees up in time.
- `PUT /voices/{sha256}` — raw WAV body; stores a clip under its SHA-256 hash (checked). The
  backend calls this after a `404 VOICE_NOT_STORED` and retries, so the two services share no
  files and this one can run on another machine.
- `DELETE /voices/{sha256}` — forgets a stored clip (sent when a teacher deletes it).

## Settings

All read from environment variables prefixed `TTS_` (see `app/config.py` for the full list and
defaults): `TTS_MODEL_REPO`, `TTS_MODEL_CACHE_DIR`, `TTS_VOICES_DIR`, `TTS_QUANTIZATION`
(`int8` trades quality for lower CPU/RAM use — untested here, the default full-precision mode is
what's actually been measured), `TTS_MAX_CONCURRENT_SYNTHESIS`,
`TTS_SYNTHESIS_QUEUE_TIMEOUT_SECONDS`, `TTS_CUSTOM_VOICES_DIR` (where teachers' clips are cached —
safe to clear), `TTS_MAX_VOICE_BYTES`.
