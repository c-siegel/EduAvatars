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

The code is organised by feature: each folder under `app/features/` holds one area's routes
(`*router.py`), its logic (`service.py` and friends), its database tables (`models.py`) and its
request/response shapes (`schemas.py`). Routers only deal with HTTP; services hold the logic and
raise `DomainError`s (`app/core/errors.py`) instead of HTTP exceptions.

| Path | Contents |
|---|---|
| `app/main.py` | Builds the app (`create_app()`): middleware, error handling, lifespan, `/health` |
| `app/api_router.py` | Mounts every feature's router; the order matters for overlapping paths |
| `app/core/` | Cross-cutting setup: settings (`config.py`), auth dependencies (`deps.py`), cookies, domain errors, middleware, the LLM/TTS/STT provider registry (`providers.py`), rate limiting, security helpers |
| `app/db/` | Database session/engine setup; `base.py` imports every feature's models for Alembic |
| `app/storage/` | Shared upload handling: content sniffing, saving/deleting files, cached file responses |
| `app/tasks/` | Background work: the periodic data-retention purge |
| `app/features/auth/` | Register, login, logout, password reset |
| `app/features/users/` | Own profile (`/profile`), account deletion, admin account management (`/admin/users`) |
| `app/features/site_settings/` | Instance-wide settings: public (`/settings/public`) and admin (`/admin/settings`) |
| `app/features/projects/` | Project CRUD, publishing, YAML export/import, cached start-prompt audio |
| `app/features/chat/` | Public chat (`/public/{slug}`) and the configurator's preview chat; `pipeline.py` combines LLM → save → TTS for both |
| `app/features/ai/` | One package each for LLM, TTS and STT, with one module per provider behind a small interface (`get_llm_client`, `get_tts_client`, `get_stt_client`) |
| `app/features/api_keys/` | The user's stored provider keys (`/api-keys`), the provider registry route, key resolution and encryption |
| `app/features/media/` | Avatar model and background image libraries |
| `app/features/analytics/` | Dashboard stats, the saved-conversation list, CSV/ZIP export |
| `alembic/` | Database migrations; `alembic/versions/` holds one file per schema change |
| `tests/` | Unit tests plus route-level tests (`test_routes_*.py`) and an OpenAPI contract snapshot (`test_openapi_contract.py`) that pins the HTTP interface |

## Adding an AI provider

[`app/core/providers.py`](app/core/providers.py) is the single source of truth for which LLM/TTS
providers a user can connect with their own API key (see the
[root README](../README.md#supported-ai-providers) for the current list). The frontend's
provider dropdown, model list, and validation are all generated from this one registry — adding
a provider is one `ProviderSpec` entry here, not a change in several places. Most providers go
through [litellm](https://github.com/BerriAI/litellm); a provider with a non-standard API (like
Cartesia or GWDG Arcana) gets its own module in `app/features/ai/tts/` or `app/features/ai/llm/`
instead, picked by that package's `get_*_client()` factory.

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
- **Public chat messages are capped** at 8000 characters each (`app/features/chat/schemas.py`),
  including the conversation history a client echoes back on every request — otherwise nothing
  stopped an anonymous visitor from sending arbitrarily large text against the project owner's own
  LLM API key.
- **A stored key's endpoint (`api_base`) is validated** against cloud-metadata addresses
  (`app/features/api_keys/schemas.py`) — see the [root README](../README.md#supported-ai-providers)
  for what this does and doesn't restrict.
- **Data retention** (`app/tasks/retention.py`) is enforced both at startup and
  periodically (every 6 hours, see `app/main.py`) for as long as the process runs, not just once
  per restart.
- **Conversation exports are CSV-injection-safe** (`app/features/analytics/csv_export.py`): a
  visitor name or message starting with `=`, `+`, `-`, or `@` is escaped before being written to
  the exported CSV/ZIP, so it can't turn into a live spreadsheet formula when a teacher opens it.

## Latency monitoring

The public chat endpoints in `app/features/chat/public_router.py` time themselves with `time.perf_counter()`
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