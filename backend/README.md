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
| `app/api/` | HTTP routes, one file per area (`auth`, `projects`, `avatar_library`, `background_library`, `analytics`, `api_keys`, `profile`, `public_chat`, `admin`, `site_settings`) — see [API Reference](#api-reference) below |
| `app/core/` | Cross-cutting setup: settings (`config.py`), auth dependencies (`deps.py`), LLM/TTS provider wiring (`providers.py`), rate limiting, security helpers |
| `app/db/` | Database session/engine setup |
| `app/models/` | SQLModel database tables, plus request/response shapes in `models/schemas/` |
| `app/services/` | Business logic used by the routes (e.g. `llm_service.py`, `tts_service.py`, `stt_service.py`, `auth_service.py`) |
| `alembic/` | Database migrations; `alembic/versions/` holds one file per schema change |

## API Reference

Every route below lives in an `APIRouter` under `app/api/`, mounted in `app/main.py`. There's no
global `/api` prefix — each router adds its own (`/auth`, `/projects`, ...), and `main.py` adds
`GET /health` directly. Request/response shapes are Pydantic models in `app/models/schemas/`;
the route's `response_model=` in each file below names the one it returns.

**Auth column values:**

| Value | Meaning |
|---|---|
| Public | No login needed. |
| Public, rate-limited | No login, but capped per IP/email (`app/core/rate_limit.py`) against brute-forcing or spam. |
| Login required | Needs the `access_token` cookie set by `/auth/login` or `/auth/register` (`app/core/deps.py::get_current_user`). |
| Login required, own resource | Same, but also 404s (not 403) if the resource belongs to someone else — this hides whether it even exists, an IDOR (Insecure Direct Object Reference) defense. |
| Admin only | Login required, and the account's `is_admin` flag must be set (`get_current_admin`). |
| Owner, or public if published | 404 unless you own the resource — *or* it's attached to a published project, in which case anonymous visitors can fetch it too (e.g. an avatar file the public chat needs to display). |
| Visitor, rate-limited | No login — a published project's public chat. Visitors are tracked by an anonymous `ah_visitor_id` cookie, not a `User` account, and every route here is rate-limited per visitor. |

Every error response is `{"detail": "<CODE>"}` (a few routes nest it as
`{"detail": {"code": "<CODE>", "message": "..."}}` to add provider error text) — see
`app/core/error_codes.py`. The frontend translates the code into user-facing text; the backend
never sends prose directly, except for two fixed German success messages on the forgot-password
and reset-password routes.

### Health

| Method & path | Auth | Description |
|---|---|---|
| `GET /health` | Public | Liveness check for load balancers and monitoring. |

### Auth — `app/api/auth.py` (prefix `/auth`)

Registration, login/logout, the current-user check, and the password-reset flow. Login sets an
httponly cookie holding a signed JWT (JSON Web Token); there's no bearer token for the frontend
to manage.

| Method & path | Auth | Description |
|---|---|---|
| `GET /auth/registration-status` | Public | Whether self-registration is currently enabled. |
| `POST /auth/register` | Public, rate-limited | Create an account and log in, unless registration is disabled. |
| `POST /auth/login` | Public, rate-limited | Authenticate with email + password; sets the auth cookie. |
| `POST /auth/logout` | Public | Clear the auth cookie. |
| `GET /auth/me` | Login required | The currently authenticated user. |
| `POST /auth/forgot-password` | Public, rate-limited | Start a password reset for an email, if an account with it exists. |
| `POST /auth/reset-password` | Public | Complete a password reset using the token from the reset email. |

### Projects — `app/api/projects.py` (prefix `/projects`)

CRUD (create/read/update/delete) for a user's projects, plus publishing, YAML export/import, a
live preview chat used while configuring a project, and voice-message transcription for that
preview. A project is one configured AI persona — avatar, system prompt, LLM, optionally
TTS/STT — see [public_chat](#public-chat--appapipublic_chatpy-prefix-public) for the routes its visitors use once published.

| Method & path | Auth | Description |
|---|---|---|
| `POST /projects` | Login required | Create a new project. |
| `GET /projects` | Login required | List the current user's projects. |
| `GET /projects/stats` | Login required | Summary stats: project/published counts, sessions/messages in the last 7 days. |
| `POST /projects/import` | Login required | Create a new draft project from a previously exported YAML file. |
| `GET /projects/{project_id}` | Login required, own resource | A single project. |
| `GET /projects/{project_id}/export` | Login required, own resource | Download the project's config as a YAML file (no API keys, publish state, or chat password). |
| `PUT /projects/{project_id}` | Login required, own resource | Update a project. |
| `DELETE /projects/{project_id}` | Login required, own resource | Delete a project, its saved conversations, and its access logs. |
| `POST /projects/{project_id}/publish` | Login required, own resource | Publish a project, giving it a public share link. |
| `POST /projects/{project_id}/unpublish` | Login required, own resource | Unpublish a project. |
| `POST /projects/{project_id}/preview-message` | Login required, own resource | Send a message to the project's LLM and return the reply, for the in-app preview chat. |
| `POST /projects/{project_id}/start-audio` | Login required, own resource | Synthesize and store the project's start-prompt audio once, ahead of visitor traffic. |
| `GET /projects/{project_id}/start-audio` | Owner, or public if published | Serve the pre-generated start-prompt audio file. |
| `POST /projects/{project_id}/transcribe` | Login required, own resource | Transcribe a voice message for the in-app preview chat. |

### Avatar library — `app/api/avatar_library.py` (prefix `/avatar-models`)

Upload, list, and delete a user's 3D avatar models (`.glb` files, the glTF binary format the
frontend's three.js renderer loads) and their thumbnails. Uploads are checked by their actual
file content (magic bytes), not just the extension.

| Method & path | Auth | Description |
|---|---|---|
| `GET /avatar-models` | Login required | List the current user's avatar models. |
| `POST /avatar-models` | Login required | Upload a new `.glb` avatar model. |
| `GET /avatar-models/{avatar_id}/file` | Owner, or public if used by a published project | Serve the `.glb` model file. |
| `POST /avatar-models/{avatar_id}/thumbnail` | Login required, own resource | Attach a thumbnail image to an avatar model. |
| `GET /avatar-models/{avatar_id}/thumbnail` | Login required, own resource | Serve an avatar's thumbnail image. |
| `DELETE /avatar-models/{avatar_id}` | Login required, own resource | Delete an avatar model and its thumbnail. |

### Background library — `app/api/background_library.py` (prefix `/backgrounds`)

Upload, list, and delete background images shown behind the avatar in a project's chat. Same
content-sniffing validation as the avatar library.

| Method & path | Auth | Description |
|---|---|---|
| `GET /backgrounds` | Login required | List the current user's background images. |
| `POST /backgrounds` | Login required | Upload a new background image (PNG/JPEG). |
| `GET /backgrounds/{background_id}/file` | Owner, or public if used by a published project | Serve the background image file. |
| `DELETE /backgrounds/{background_id}` | Login required, own resource | Delete a background image. |

### Analytics — `app/api/analytics.py` (prefix `/analytics`)

Read-only endpoints for the teacher-facing analytics dashboard, scoped to the current user's own
projects. A "session" here means one visitor's conversation with a published project, not an
HTTP/login session.

| Method & path | Auth | Description |
|---|---|---|
| `GET /analytics/stats` | Login required | Aggregate stats (session/message counts, ...), optionally filtered by project/period/model. |
| `GET /analytics/sessions` | Login required | Paginated list of individual chat sessions. |
| `GET /analytics/sessions/ids` | Login required | Every session id matching the current filters, ignoring pagination — backs "select all" before a bulk export. |
| `GET /analytics/sessions/{conversation_id}` | Login required, own resource | Full message-by-message transcript of one saved conversation. |
| `GET /analytics/timeseries` | Login required | Session/message counts over time, bucketed by day/week/month, for charts. |
| `POST /analytics/export` | Login required | Export the given conversations as CSV (a single file) or a ZIP of CSVs (multiple). |
| `POST /analytics/delete` | Login required | Permanently delete the given saved conversations. |

### API keys — `app/api/api_keys.py` (prefix `/api-keys`)

Store, edit, test, and delete a user's own LLM/TTS/STT provider API keys — the "bring your own
key" feature — plus the provider registry so the frontend can build its key form without
duplicating that data. Keys are encrypted at rest.

| Method & path | Auth | Description |
|---|---|---|
| `GET /api-keys/providers` | Login required | List all supported providers and their config. |
| `GET /api-keys/local-tts-status` | Login required | Whether this deployment's local-TTS sidecar is enabled. |
| `GET /api-keys/browser-stt-status` | Login required | Whether browser-side (WebGPU) transcription is enabled for this deployment. |
| `GET /api-keys` | Login required | List the current user's stored keys, with how many projects use each one. |
| `POST /api-keys` | Login required | Store a new API key. |
| `PUT /api-keys/{key_id}` | Login required, own resource | Update a stored key; re-syncs any projects using it as their LLM source. |
| `DELETE /api-keys/{key_id}` | Login required, own resource | Delete a key; projects using it fall back to "no key configured". |
| `POST /api-keys/{key_id}/test` | Login required, own resource | Try the stored key against its provider and record whether it works. |

### Profile — `app/api/profile.py` (prefix `/profile`)

View and edit the logged-in user's own profile: basic fields, a profile picture, password
changes, signing out of all sessions, and account deletion.

| Method & path | Auth | Description |
|---|---|---|
| `GET /profile` | Login required | The current user's profile. |
| `PUT /profile` | Login required | Update profile fields. |
| `POST /profile/picture` | Login required | Upload or replace the profile picture. |
| `DELETE /profile/picture` | Login required | Remove the profile picture. |
| `GET /profile/picture` | Login required | Serve the current user's own profile picture. |
| `PUT /profile/password` | Login required | Change password; other sessions are signed out, this one stays signed in. |
| `POST /profile/logout-everywhere` | Login required | Sign out of every session while keeping this one signed in. |
| `DELETE /profile` | Login required | Permanently delete the account and everything belonging to it. |

### Public chat — `app/api/public_chat.py` (prefix `/public`)

The unauthenticated endpoints a published project's visitors actually use. See
[Latency monitoring](#latency-monitoring) below for the timing fields `/message`,
`/message/stream`, and `/transcribe` ride along in their responses.

| Method & path | Auth | Description |
|---|---|---|
| `GET /public/{slug}` | Visitor, rate-limited | Load a published project's public info and record the visit. |
| `POST /public/{slug}/unlock` | Visitor, rate-limited | Verify a chat password and issue an unlock token for this project + visitor. |
| `POST /public/{slug}/message` | Visitor, rate-limited | Send a chat message and get the full reply (text + optional audio) back at once. |
| `POST /public/{slug}/message/stream` | Visitor, rate-limited | Same, but streamed as SSE (Server-Sent Events): sentence-sized chunks, each with its own audio, as soon as ready. |
| `POST /public/{slug}/transcribe` | Visitor, rate-limited | Transcribe a visitor's voice message. |

### Admin — `app/api/admin.py` (prefix `/admin`)

Account management for the admin dashboard. There's deliberately no admin-initiated delete
endpoint — disabling (`User.enabled`) is how an admin removes access; the only way an account is
actually deleted is the self-service `DELETE /profile` above.

| Method & path | Auth | Description |
|---|---|---|
| `GET /admin/users` | Admin only | List every account on this instance. |
| `POST /admin/users` | Admin only | Create an account with a temporary password the new user must change on first login. |
| `PUT /admin/users/{user_id}` | Admin only | Promote/demote or enable/disable an account. |
| `POST /admin/users/{user_id}/reset-password` | Admin only | Set a user's password on their behalf; they must change it on next login. |
| `GET /admin/settings` | Admin only | The instance-wide site settings (contact email, self-registration toggle). |
| `PUT /admin/settings` | Admin only | Update the instance-wide site settings. |

### Site settings — `app/api/site_settings.py` (prefix `/settings`)

| Method & path | Auth | Description |
|---|---|---|
| `GET /settings/public` | Public | The public-facing site settings (imprint details, whether self-registration is open) — see `/admin/settings` for the full, admin-only version. |

## Service-layer functions

Route handlers in `app/api/` stay thin — they read the request, check auth, and delegate the
actual work to a function in `app/services/`. This is the API a rookie extending the backend
(or writing a script/test against it directly, without going through HTTP) will actually call.
Every function below is public (no leading underscore); helpers named `_like_this` are
file-private and left out.

| File | Purpose | Key functions |
|---|---|---|
| `llm_service.py` | LLM chat completion (via litellm, plus a direct integration for GWDG Arcana) | `send_chat_message(preprompt, message, api_key_record, temperature, top_p, start_prompt, history)` — one-shot reply.<br>`stream_chat_message(...)` — same, yielding text deltas.<br>`test_api_key(api_key_record)` — validate a stored key with a minimal real call. |
| `tts_service.py` | Text-to-speech (TTS) synthesis | `synthesize_speech(text, tts_voice, api_key_record, language)` — routes to the right provider (or the local-TTS sidecar) and returns `(audio_bytes, content_type)`. Raises `VoiceRequiredError` if the provider needs a voice that wasn't given. |
| `stt_service.py` | Speech-to-text (STT) transcription | `transcribe_audio(audio_bytes, language, initial_prompt, api_key_record)` — via faster-whisper locally, or a cloud provider if configured.<br>`test_stt_key(api_key_record)` — validate a stored key with a real (silent) transcription. |
| `api_key_service.py` | Resolving which of a project's API keys to use | `resolve_llm_key(session, project)`, `resolve_tts_key(...)`, `resolve_stt_key(...)` — find the configured key for each purpose.<br>`get_user_api_key(session, user_id, provider, key_type)`, `get_key_by_id(...)`, `get_owned_key_of_type(...)` — lookups.<br>`provider_from_model(llm_model)`, `browser_stt_model_for(project)`, `effective_api_base(key)`. |
| `auth_service.py` | Authentication helpers | `register_user(session, name, email, password)`, `authenticate_user(session, email, password)`.<br>`issue_token_for(user)` — sign a JWT.<br>`set_auth_cookie(response, user)` — issue + set the cookie.<br>`user_to_out(user)` — convert to the public `UserOut` shape. |
| `project_service.py` | Project CRUD helpers | `list_projects(session, user_id)`, `update_project(session, project, data)`, `delete_project(session, project)`.<br>`sync_llm_model(session, project)` — derive `llm_model` from the project's linked API key.<br>`set_or_clear_chat_password(project, password)`. |
| `publish_service.py` | Publishing projects | `publish_project(session, project)` — assigns a fresh share-link slug.<br>`unpublish_project(session, project)` — the old slug is never reused. |
| `analytics_service.py` | Analytics queries behind the dashboard | `get_stats(...)`, `get_sessions_paginated(...)`, `get_session_ids(...)`, `get_timeseries_data(...)`.<br>`get_conversation_detail(...)`, `get_conversations_for_export(...)`, `delete_conversations(...)`.<br>`build_conversation_csv(conversation, project)`, `conversation_export_filename(...)`. |
| `crypto_service.py` | Encrypting and masking stored API keys | `store_api_key(plaintext)` / `reveal_api_key(ciphertext)` — encrypt/decrypt for storage.<br>`mask_key(plaintext)` — e.g. `"••••••••1234"`.<br>`scrub_key_from_text(text, encrypted_api_key)` — redact a key out of error text before it's shown or logged. |
| `account_service.py` | Account deletion | `delete_user_account(session, user)` — cascades to projects, keys, conversations, and uploaded files. |
| `admin_service.py` | Admin account management | `create_user_as_admin(...)`, `admin_reset_password(...)`, `admin_update_user(session, admin, target, data)` — guards against self-lockout and removing the last admin.<br>`count_active_admins(session)`. |
| `password_reset_service.py` | Password reset flow | `request_password_reset(session, email)` — issues a token and emails the link.<br>`reset_password(session, raw_token, new_password)`. |
| `site_settings_service.py` | Instance-wide site settings | `get_or_create_site_settings(session)`, `update_site_settings(session, data)`. |
| `text_chunk_service.py` | Splits streamed LLM text into speakable sentence chunks | `SentenceChunker` — `feed()`/`flush()` for a live stream.<br>`chunk_text(text)` — convenience wrapper for an already-complete string. |
| `visitor_service.py` | Visitor access logging | `log_access(session, project_id, visitor_id)` — records one visit to a public chat page. |
| `visitor_name_service.py` | Enforces "visitor must give a name" projects | `clean_visitor_name(x_visitor_name)`, `assert_visitor_name_provided(project, visitor_name)`. |
| `chat_password_service.py` | Chat password verification | `verify_chat_password(project, password)`, `issue_unlock_token(project, visitor_id)`.<br>`is_unlocked(...)` / `assert_unlocked(...)` — check vs. raise HTTP 401 variants. |
| `project_export_service.py` | Project YAML export/import | `export_project_yaml(project)`, `parse_project_yaml(raw)`, `import_project(session, user_id, data)`. |
| `retention_service.py` | Data-retention cleanup | `purge_expired_data(session)` — deletes conversations/access logs past the configured retention period. |
| `email_service.py` | Transactional email | `send_password_reset_email(to_email, reset_link)`. |

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