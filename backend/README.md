# EduAvatars backend

EduAvatars' backend uses FastAPI as framework for building APIs with Python: user auth, avatar/project management, and calls out to LLM, text-to-speech (TTS), and speech-to-text (STT) providers.

See the [root README](../README.md) for what the app does and how to run it end to end — this
file only covers backend-specific details.

## Stack

- **FastAPI** — the web framework serving the API.
- **SQLModel** (SQLAlchemy + Pydantic) — database models, backed by **SQLite**.
- **Alembic** — database schema migrations (`alembic/versions/`).
- **litellm** — a single client that talks to different LLM/TTS providers, so the app isn't
  locked to one vendor.
- **faster-whisper** — runs speech-to-text directly inside the backend process (no separate
  service needed).
- **JWT (JSON Web Tokens) + bcrypt** — authentication and password hashing.

## Folder map

| Path | Contents |
|---|---|
| `app/api/` | HTTP routes, one file per area (`auth`, `projects`, `avatar_library`, `background_library`, `analytics`, `api_keys`, `profile`, `public_chat`) |
| `app/core/` | Cross-cutting setup: settings (`config.py`), auth dependencies (`deps.py`), LLM/TTS provider wiring (`providers.py`), rate limiting, security helpers |
| `app/db/` | Database session/engine setup |
| `app/models/` | SQLModel database tables, plus request/response shapes in `models/schemas/` |
| `app/services/` | Business logic used by the routes (e.g. `llm_service.py`, `tts_service.py`, `stt_service.py`, `auth_service.py`) |
| `alembic/` | Database migrations; `alembic/versions/` holds one file per schema change |

## Adding an AI provider

[`app/core/providers.py`](app/core/providers.py) is the single source of truth for which LLM/TTS
providers a user can connect with their own API key (see the
[root README](../README.md#supported-ai-providers) for the current list). The frontend's
provider dropdown, model list, and validation are all generated from this one registry — adding
a provider is one `ProviderSpec` entry here, not a change in several places. Most providers go
through [litellm](https://github.com/BerriAI/litellm); a provider with a non-standard API (like
Cartesia or GWDG Arcana) gets its own direct integration in `app/services/tts_service.py` or
`app/services/llm_service.py` instead.

## Security & limits

A few backend behaviors worth knowing about if you're deploying or extending this:

- **Startup validation.** `JWT_SECRET` and `API_KEY_ENCRYPTION_SECRET` (`app/core/config.py`) are
  checked at process startup, not just required to be present — a placeholder, too-short, or
  invalid-Fernet-key value fails the boot with a clear error instead of running with a guessable
  or broken secret.
- **Rate limiting** (`app/core/rate_limit.py`) protects every endpoint that doesn't require login:
  public chat messages, voice transcription, chat-password unlock attempts, and login/register/
  password-reset — each limited per visitor/IP (public chat) or per IP/email (auth), sized for a
  school-class-sized burst of traffic. It's an in-memory sliding window, sized for a single
  process — swap it for something shared (e.g. Redis) before running more than one backend worker.
- **Public chat messages are capped** at 8000 characters each (`app/models/schemas/chat.py`),
  including the conversation history a client echoes back on every request — otherwise nothing
  stopped an anonymous visitor from sending arbitrarily large text against the project owner's own
  LLM API key.
- **A stored key's endpoint (`api_base`) is validated** against cloud-metadata addresses
  (`app/models/schemas/api_key.py`) — see the [root README](../README.md#supported-ai-providers)
  for what this does and doesn't restrict.
- **Data retention** (`app/services/retention_service.py`) is enforced both at startup and
  periodically (every 6 hours, see `app/main.py`) for as long as the process runs, not just once
  per restart.
- **Conversation exports are CSV-injection-safe** (`app/services/analytics_service.py`): a
  visitor name or message starting with `=`, `+`, `-`, or `@` is escaped before being written to
  the exported CSV/ZIP, so it can't turn into a live spreadsheet formula when a teacher opens it.

## Latency monitoring

The public chat endpoints in `app/api/public_chat.py` time themselves with `time.perf_counter()`
and ride the results along as extra fields in their normal JSON responses — there's no separate
metrics endpoint or database, just numbers the frontend console-logs for debugging. `None` always
means a stage didn't run at all (e.g. TTS disabled or no key configured), never "it was instant".

| Endpoint | Field(s) | What it measures |
|---|---|---|
| `POST /{slug}/message` | `llmMs` | Wall-clock time inside the LLM (large language model) call. |
| | `ttsMs` | Wall-clock time inside the TTS (text-to-speech) call. `null` if TTS didn't run. |
| `POST /{slug}/message/stream` (SSE `done` event) | `llmMs` | Time from request start to the full LLM reply being assembled. |
| | `firstChunkTextReadyMs` | Time until the first sentence chunk was handed to TTS (isolates LLM/chunking speed from TTS speed). |
| | `firstChunkMs` | Time until that first chunk's TTS synthesis *finished*. |
| | `ttsMs` | Summed synthesis time across all chunks. |
| `POST /{slug}/transcribe` | `sttMs` | Wall-clock time inside the STT (speech-to-text, via faster-whisper) call. |

How to use: open the public chat page with `?latencyTest=1` appended to the URL — the frontend logs
these numbers to the browser console, combined with client-side timings (network round trip, audio
decode/playback, time to first spoken word). See [frontend/README.md](../frontend/README.md#debugging)
for the full breakdown and what each logged field means.

## Tests

`tests/` covers the pure-function/schema-validation pieces of the codebase — text-stream parsers
(`SentenceChunker`/`chunk_text`, `ArcanaReferenceGuard`), request-schema validators (password/
message length limits, the `api_base` SSRF guard), rate limiting, the retention loop, and a few
service-level checks (project deletion cleanup, duplicate-email handling, admin bootstrap). Run
them with:

```bash
cd backend && pytest
```

Tests need a `JWT_SECRET`/`API_KEY_ENCRYPTION_SECRET` in the environment (the repo root `.env` from
[Deploy A](../README.md#deploy-a-local-development) already has both, so local runs need no extra
setup) — see `app/core/config.py`'s startup validation above.

Most of the app (routes, DB access, provider calls) still has no test coverage — this is a start,
not full coverage. CI (`.github/workflows/docker-publish.yml`) runs this suite, plus the frontend
build, before a tagged release's Docker images are published.