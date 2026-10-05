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
  service needed). Optionally replaced by **Parakeet Redux** on ONNX Runtime (`STT_ENGINE=parakeet`),
  the same model the browsers use for on-device recognition.
- **JWT (JSON Web Tokens) + bcrypt** — authentication and password hashing.

## Folder map

The code is organised by feature: each folder under `app/features/` holds one area's routes
(`*router.py`), its logic (`service.py` and friends), its database tables (`models.py`) and its
request/response shapes (`schemas.py`). Routers only deal with HTTP; services hold the logic and
raise `DomainError`s (`app/core/errors.py`) instead of HTTP exceptions.

| Path | Contents |
|---|---|
| `app/main.py` | Builds the app (`create_app()`): middleware, error handling, lifespan, `/health` |
| `app/api_router.py` | Mounts every feature's router under `/api/v1` (`app/core/urls.py`); the order matters for overlapping paths — see [API Reference](#api-reference) below |
| `app/core/` | Cross-cutting setup: settings (`config.py`), auth dependencies (`deps.py`), cookies, domain errors, middleware, public URLs (`urls.py`), the LLM/TTS/STT provider registry (`providers.py`), rate limiting, security helpers |
| `app/db/` | Database session/engine setup; `base.py` imports every feature's models for Alembic |
| `app/storage/` | Shared upload handling: content sniffing, saving/deleting files, cached file responses |
| `app/tasks/` | Background work: the periodic data-retention purge |
| `app/features/auth/` | Register, login, logout, password reset |
| `app/features/users/` | Own profile (`/me`), account deletion, admin account management (`/admin/users`) |
| `app/features/site_settings/` | Instance-wide settings: public (`/settings/public`) and admin (`/admin/settings`) |
| `app/features/projects/` | Project CRUD, publishing, YAML export/import, cached start-prompt audio |
| `app/features/chat/` | Public chat (`/public/{slug}`) and the configurator's preview chat; `pipeline.py` combines LLM → save → TTS for both |
| `app/features/ai/` | One package each for LLM, TTS and STT, with one module per provider behind a small interface (`get_llm_client`, `get_tts_client`, `get_stt_client`) — including the local-TTS sidecar and local Whisper fallbacks |
| `app/features/api_keys/` | The user's stored provider keys (`/api-keys`), the provider registry and speech-option status routes (`/providers`), key resolution and encryption |
| `app/features/media/` | Avatar model and background image libraries |
| `app/features/analytics/` | Dashboard stats, the saved-conversation list, CSV/ZIP export |
| `alembic/` | Database migrations; `alembic/versions/` holds one file per schema change |
| `tests/` | Unit tests plus route-level tests (`test_routes_*.py`) and an OpenAPI contract snapshot (`test_openapi_contract.py`) that pins the HTTP interface |

## API Reference

Every route below is mounted under the `/api/v1` prefix (`app/core/urls.py`) — the paths in the
tables leave it out, so `GET /projects` means `GET /api/v1/projects`. The only exception is
`GET /health`, which is also reachable at the bare path. Each table names the router file that
defines its routes; request/response shapes are Pydantic models in the same feature's
`schemas.py`, and the route's `response_model=` names the one it returns.

URLs the API hands out for a browser to load directly (avatar and background files, thumbnails,
start-prompt audio, the profile picture) are absolute paths that already include `/api/v1`, so
the frontend uses them as-is.

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
`app/core/error_codes.py`. Services raise these as `DomainError`s (`app/core/errors.py`); the
frontend translates the code into user-facing text, and the backend never sends prose directly,
except for two fixed German success messages on the forgot-password and reset-password routes.

### Health

| Method & path | Auth | Description |
|---|---|---|
| `GET /health` (also `GET /api/v1/health`) | Public | Liveness check for load balancers, monitoring, and the Docker healthcheck. |

### Auth — `app/features/auth/router.py` (prefix `/auth`)

Registration, login/logout, and the password-reset flow. Login sets an httponly cookie holding a
signed JWT (JSON Web Token); there's no bearer token for the frontend to manage. The current-user
check is `GET /me` (see [Me](#me--appfeaturesusersprofile_routerpy-prefix-me)).

| Method & path | Auth | Description |
|---|---|---|
| `GET /auth/registration-status` | Public | Whether self-registration is currently enabled. |
| `POST /auth/register` | Public, rate-limited | Create an account and log in, unless registration is disabled. |
| `POST /auth/login` | Public, rate-limited | Authenticate with email + password; sets the auth cookie. |
| `POST /auth/logout` | Public | Clear the auth cookie. |
| `POST /auth/forgot-password` | Public, rate-limited | Start a password reset for an email, if an account with it exists. |
| `POST /auth/reset-password` | Public | Complete a password reset using the token from the reset email. |

### Me — `app/features/users/profile_router.py` (prefix `/me`)

The logged-in user's own account: basic fields, a profile picture, password changes, signing out
of all sessions, and account deletion.

| Method & path | Auth | Description |
|---|---|---|
| `GET /me` | Login required | The currently authenticated user (what the dashboard checks on load). |
| `PUT /me` | Login required | Update profile fields. |
| `POST /me/picture` | Login required | Upload or replace the profile picture. |
| `DELETE /me/picture` | Login required | Remove the profile picture. |
| `GET /me/picture` | Login required | Serve the current user's own profile picture. |
| `PUT /me/password` | Login required | Change password; other sessions are signed out, this one stays signed in. |
| `POST /me/logout-everywhere` | Login required | Sign out of every session while keeping this one signed in. |
| `DELETE /me` | Login required | Permanently delete the account and everything belonging to it. |

### Projects — `app/features/projects/` (prefix `/projects`)

A project is one configured AI persona — avatar, system prompt, LLM, optionally TTS/STT — see
[Public chat](#public-chat--appfeatureschatpublic_routerpy-prefix-public) for the routes its
visitors use once published. Its avatar is referenced by `avatarModelId` (one of the user's
library models) or `builtinAvatar` (a bundled default like `"julia"`), its background by
`avatarBackgroundId`; responses also carry the ready-to-load `avatarModelUrl`/`avatarBackgroundUrl`.

| Method & path | Router | Auth | Description |
|---|---|---|---|
| `POST /projects` | `router.py` | Login required | Create a new project. |
| `GET /projects` | `router.py` | Login required | List the current user's projects. |
| `GET /projects/{project_id}` | `router.py` | Login required, own resource | A single project. |
| `PUT /projects/{project_id}` | `router.py` | Login required, own resource | Update a project. |
| `DELETE /projects/{project_id}` | `router.py` | Login required, own resource | Delete a project, its saved conversations, and its access logs. |
| `POST /projects/import` | `transfer_router.py` | Login required | Create a new draft project from a previously exported YAML file (format v2; v1 files still import). |
| `GET /projects/{project_id}/export` | `transfer_router.py` | Login required, own resource | Download the project's config as a YAML file (no API keys, publish state, or chat password). |
| `PUT /projects/{project_id}/publication` | `publication_router.py` | Login required, own resource | Publish a project under a fresh public share link. |
| `DELETE /projects/{project_id}/publication` | `publication_router.py` | Login required, own resource | Unpublish a project; the old link is never reused. |
| `POST /projects/{project_id}/start-audio` | `start_audio_router.py` | Login required, own resource | Synthesize and store the start-prompt audio once (MP3 from a cloud key, WAV from the local-TTS sidecar). |
| `GET /projects/{project_id}/start-audio` | `start_audio_router.py` | Owner, or public if published | Serve the pre-generated start-prompt audio file. |
| `POST /projects/{project_id}/chat/messages` | `app/features/chat/preview_router.py` | Login required, own resource | Send a message to the project's LLM and return the reply, for the in-app preview chat. |
| `POST /projects/{project_id}/chat/transcriptions` | `app/features/chat/preview_router.py` | Login required, own resource | Transcribe a voice message for the in-app preview chat. |

### Public chat — `app/features/chat/public_router.py` (prefix `/public`)

The unauthenticated endpoints a published project's visitors actually use. See
[Latency monitoring](#latency-monitoring) below for the timing fields `/messages`,
`/messages/stream`, and `/transcriptions` ride along in their responses. `GET /public/{slug}`
also returns `browserSttModelUrl` (where the on-device speech recognition model lives) unless the
project or deployment opted out of transcribing in the visitor's browser.

| Method & path | Auth | Description |
|---|---|---|
| `GET /public/{slug}` | Visitor, rate-limited | Load a published project's public info and record the visit. |
| `POST /public/{slug}/unlock` | Visitor, rate-limited | Verify a chat password and issue an unlock token for this project + visitor. |
| `POST /public/{slug}/messages` | Visitor, rate-limited | Send a chat message and get the full reply (text + optional audio) back at once. |
| `POST /public/{slug}/messages/stream` | Visitor, rate-limited | Same, but streamed as SSE (Server-Sent Events): sentence-sized chunks, each with its own audio, as soon as ready. |
| `POST /public/{slug}/transcriptions` | Visitor, rate-limited | Transcribe a visitor's voice message. |

### Avatar library — `app/features/media/avatars_router.py` (prefix `/avatars`)

Upload, list, and delete a user's 3D avatar models (`.glb` files, the glTF binary format the
frontend's three.js renderer loads) and their thumbnails. Uploads are checked by their actual
file content (magic bytes), not just the extension.

| Method & path | Auth | Description |
|---|---|---|
| `GET /avatars` | Login required | List the current user's avatar models. |
| `POST /avatars` | Login required | Upload a new `.glb` avatar model. |
| `GET /avatars/{avatar_id}/file` | Owner, or public if used by a published project | Serve the `.glb` model file. |
| `POST /avatars/{avatar_id}/thumbnail` | Login required, own resource | Attach a thumbnail image to an avatar model. |
| `GET /avatars/{avatar_id}/thumbnail` | Login required, own resource | Serve an avatar's thumbnail image. |
| `DELETE /avatars/{avatar_id}` | Login required, own resource | Delete an avatar model and its thumbnail. |

### Background library — `app/features/media/backgrounds_router.py` (prefix `/backgrounds`)

Upload, list, and delete background images shown behind the avatar in a project's chat. Same
content-sniffing validation as the avatar library.

| Method & path | Auth | Description |
|---|---|---|
| `GET /backgrounds` | Login required | List the current user's background images. |
| `POST /backgrounds` | Login required | Upload a new background image (PNG/JPEG). |
| `GET /backgrounds/{background_id}/file` | Owner, or public if used by a published project | Serve the background image file. |
| `DELETE /backgrounds/{background_id}` | Login required, own resource | Delete a background image. |

### Voice library — `app/features/media/voices_router.py` (prefix `/voice-clips`)

Each teacher's private voice clips for local voice cloning (local TTS only — a project picks one
via `ttsVoiceClipId`). Uploads are content-sniffed, need a consent confirmation, must be 3–30 s
long, and are stored as normalized 24 kHz mono WAV whatever format came in.

| Method & path | Auth | Description |
|---|---|---|
| `GET /voice-clips` | Login required | List the current user's voice clips. |
| `POST /voice-clips` | Login required | Add a clip (multipart: `file`, `name`, `consent=true`) — an uploaded file or a browser recording. |
| `GET /voice-clips/{clip_id}/file` | Login required, own resource | Serve the clip's WAV file (never public). |
| `POST /voice-clips/{clip_id}/preview` | Login required, own resource | Speak `{text, language}` in the clip's cloned voice via the local-TTS sidecar; returns WAV. |
| `DELETE /voice-clips/{clip_id}` | Login required, own resource | Delete a clip; projects using it go back to the default voice and lose their start audio. |

### Analytics — `app/features/analytics/stats_router.py` (prefix `/analytics`)

Read-only numbers for the teacher-facing dashboards, scoped to the current user's own projects.

| Method & path | Auth | Description |
|---|---|---|
| `GET /analytics/stats` | Login required | Aggregate stats (session/message counts, ...), optionally filtered by project/period/model. |
| `GET /analytics/timeseries` | Login required | Session/message counts over time, bucketed by day/week/month, for charts. |
| `GET /analytics/overview` | Login required | Summary for the overview page: project/published counts, sessions/messages in the last 7 days. |

### Conversations — `app/features/analytics/conversations_router.py` (prefix `/conversations`)

The saved conversations behind the analytics table. One conversation (a "session" in the UI) is
one visitor's chat with a published project, not an HTTP/login session.

| Method & path | Auth | Description |
|---|---|---|
| `GET /conversations` | Login required | Paginated list of saved conversations, optionally filtered by project/period/model. |
| `GET /conversations/ids` | Login required | Every conversation id matching the current filters, ignoring pagination — backs "select all" before a bulk export. |
| `GET /conversations/{conversation_id}` | Login required, own resource | Full message-by-message transcript of one saved conversation. |
| `POST /conversations/export` | Login required | Export the given conversations as CSV (a single file) or a ZIP of CSVs (multiple). |
| `POST /conversations/batch-delete` | Login required | Permanently delete the given saved conversations. |

### API keys and providers — `app/features/api_keys/` (prefixes `/api-keys`, `/providers`)

Store, edit, test, and delete a user's own LLM/TTS/STT provider API keys — the "bring your own
key" feature — plus the provider registry so the frontend can build its key form without
duplicating that data. Keys are encrypted at rest.

| Method & path | Router | Auth | Description |
|---|---|---|---|
| `GET /providers` | `providers_router.py` | Login required | List all supported providers and their config. |
| `GET /providers/local-tts-status` | `providers_router.py` | Login required | Whether this deployment's local-TTS sidecar is enabled. |
| `GET /providers/browser-stt-status` | `providers_router.py` | Login required | Whether on-device (WebGPU) transcription is enabled for this deployment. |
| `GET /api-keys` | `router.py` | Login required | List the current user's stored keys, with how many projects use each one. |
| `POST /api-keys` | `router.py` | Login required | Store a new API key. |
| `PUT /api-keys/{key_id}` | `router.py` | Login required, own resource | Update a stored key; re-syncs any projects using it as their LLM source. |
| `DELETE /api-keys/{key_id}` | `router.py` | Login required, own resource | Delete a key; projects using it fall back to "no key configured". |
| `POST /api-keys/{key_id}/test` | `router.py` | Login required, own resource | Try the stored key against its provider and record whether it works. |

### Admin — `app/features/users/admin_users_router.py` and `app/features/site_settings/admin_router.py` (prefix `/admin`)

Account management and instance-wide settings for the admin dashboard. There's deliberately no
admin-initiated delete endpoint — disabling (`User.enabled`) is how an admin removes access; the
only way an account is actually deleted is the self-service `DELETE /me` above.

| Method & path | Auth | Description |
|---|---|---|
| `GET /admin/users` | Admin only | List every account on this instance. |
| `POST /admin/users` | Admin only | Create an account with a temporary password the new user must change on first login. |
| `PUT /admin/users/{user_id}` | Admin only | Promote/demote or enable/disable an account. |
| `POST /admin/users/{user_id}/reset-password` | Admin only | Set a user's password on their behalf; they must change it on next login. |
| `GET /admin/settings` | Admin only | The instance-wide site settings (contact email, self-registration toggle, retention). |
| `PUT /admin/settings` | Admin only | Update the instance-wide site settings. |

### Site settings — `app/features/site_settings/public_router.py` (prefix `/settings`)

| Method & path | Auth | Description |
|---|---|---|
| `GET /settings/public` | Public | The public-facing site settings (imprint details, whether self-registration is open) — see `/admin/settings` for the full, admin-only version. |

## Service-layer functions

Routers stay thin — they read the request, check auth, and delegate the actual work to a service
function, which raises a `DomainError` (rendered as `{"detail": "<CODE>"}`) instead of an HTTP
exception. These are the functions to call when extending the backend or writing a script/test
against it directly, without going through HTTP. Every function below is public (no leading
underscore); helpers named `_like_this` are file-private and left out. Paths are relative to
`app/`.

| File | Purpose | Key functions |
|---|---|---|
| `features/ai/llm/` | LLM chat completion (litellm, plus a direct integration for GWDG Arcana) | `get_llm_client(api_key_record)` → `.complete(request)`, `.stream(request)`, `.test()`.<br>`complete(api_key_record, ChatRequest(...))` — one-shot reply.<br>`stream(api_key_record, ChatRequest(...))` — text deltas, falling back to a plain call if streaming fails before the first delta. |
| `features/ai/tts/` | Text-to-speech (TTS) synthesis | `synthesize_speech(text, tts_voice, api_key_record, language)` — routes to the right provider, or the local-TTS sidecar for `api_key_record=None`, and returns `(audio_bytes, content_type)`. Raises `VoiceRequiredError` if the provider needs a voice that wasn't given.<br>`get_tts_client(api_key_record)` — the provider client itself. |
| `features/ai/stt/` | Speech-to-text (STT) transcription | `transcribe_audio(audio_bytes, language, initial_prompt, api_key_record)` — locally via faster-whisper or Parakeet (`Settings.stt_engine`), or a cloud provider if configured.<br>`get_stt_client(api_key_record)` → `.transcribe(...)`; a SAIA client also has `.test()`.<br>`capacity.transcription_slot()` — limits concurrent local transcriptions. |
| `features/chat/pipeline.py` | One chat turn for the public and preview chat | `prepare_chat(session, project)` — resolve keys and snapshot the project.<br>`reply_turn(context, turn)` — LLM → save → TTS.<br>`stream_turn(context, turn)` — `(event, data)` pairs for the SSE stream. |
| `features/api_keys/resolve.py` | Which of a project's API keys to use | `resolve_llm_key(session, project)`, `resolve_tts_key(...)`, `resolve_stt_key(...)`.<br>`get_user_api_key(...)`, `get_key_by_id(...)`, `get_owned_key_of_type(...)` — lookups.<br>`provider_from_model(llm_model)`, `browser_stt_model_url_for(project)`, `effective_api_base(key)`. |
| `features/api_keys/service.py` | Managing stored keys | `list_keys_with_usage(session, user_id)`, `create_key(...)`, `update_key(...)`, `delete_key(...)`, `run_key_test(session, key)`. |
| `features/api_keys/crypto.py` | Encrypting and masking stored API keys | `store_api_key(plaintext)` / `reveal_api_key(ciphertext)`.<br>`mask_key(plaintext)` — e.g. `"••••••••1234"`.<br>`scrub_key_from_text(text, encrypted_api_key)` — redact a key out of error text before it's shown or logged. |
| `features/auth/service.py` | Authentication helpers | `register_user(session, name, email, password)`, `authenticate_user(session, email, password)`, `user_to_out(user)`. The auth cookie itself is set by `core/cookies.py::set_auth_cookie`. |
| `features/auth/password_reset.py` | Password reset flow | `request_password_reset(session, email)` — issues a token and emails the link.<br>`reset_password(session, raw_token, new_password)`. |
| `features/projects/service.py` | Project CRUD | `create_project(session, user_id, data)`, `apply_update(session, project, data)`, `list_projects(...)`, `delete_project(...)`.<br>`sync_llm_model(session, project)` — derive `llm_model` from the linked key. |
| `features/projects/publish.py` | Publishing projects | `publish_project(session, project)` — assigns a fresh share-link slug.<br>`unpublish_project(session, project)` — the old slug is never reused. |
| `features/projects/start_audio.py` | Cached start-prompt audio | `generate_start_audio(session, project)`, `servable_start_audio(session, project_id, user)`. |
| `features/projects/export.py` | Project YAML export/import | `export_project_yaml(project)`, `parse_project_yaml(raw)`, `import_project(session, user_id, data)`. |
| `features/media/service.py` | Avatar, background and voice libraries | `create_avatar(...)`, `set_avatar_thumbnail(...)`, `delete_avatar(...)`, the background equivalents, and `is_used_by_published_project(session, column, item_id, owner_id)`.<br>`list_voice_clips(...)`, `get_owned_voice_clip(...)`, `create_voice_clip(...)`, `delete_voice_clip(session, clip)`, `voice_reference_for_project(session, project)`. |
| `features/media/voice_audio.py` | Voice clip validation | `normalize_voice_clip(content)` → (WAV bytes, duration) — sniffs, decodes and resamples an upload, enforcing 3–30 s. |
| `features/analytics/service.py` | Analytics queries behind the dashboard | `get_stats(...)`, `get_project_overview(...)`, `get_sessions_paginated(...)`, `get_session_ids(...)`, `get_timeseries_data(...)`.<br>`get_conversation_detail(...)`, `get_conversations_for_export(...)`, `delete_conversations(...)`. |
| `features/analytics/csv_export.py` | Conversation CSV/ZIP export | `build_export(rows)`, `build_conversation_csv(conversation, project)`, `conversation_export_filename(...)`. |
| `features/users/service.py` | Own profile and admin account management | `update_profile(...)`, `change_password(...)`, `set_profile_picture(...)`.<br>`create_user_as_admin(...)`, `admin_reset_password(...)`, `admin_update_user(session, admin, target, data)` — guards against self-lockout and removing the last admin. |
| `features/users/account.py` | Account deletion | `delete_user_account(session, user)` — cascades to projects, keys, conversations, and uploaded files. |
| `features/site_settings/service.py` | Instance-wide site settings | `get_or_create_site_settings(session)`, `update_site_settings(session, data)`. |
| `features/chat/streaming.py` | Splitting streamed LLM text into speakable sentence chunks | `SentenceChunker` — `feed()`/`flush()` for a live stream.<br>`chunk_text(text)` for an already-complete string; `sse_event(event, data)` for one SSE frame. |
| `features/chat/unlock.py` | Chat password verification | `verify_chat_password(project, password)`, `issue_unlock_token(project, visitor_id)`.<br>`is_unlocked(...)` / `assert_unlocked(...)` — check vs. raise variants. |
| `features/chat/visitor_name.py`, `visitor_log.py` | Visitor name and visit logging | `clean_visitor_name(...)`, `assert_visitor_name_provided(...)`, `log_access(session, project_id, visitor_id)`. |
| `features/auth/email.py` | Transactional email | `send_password_reset_email(to_email, reset_link)`. |
| `tasks/retention.py` | Data-retention cleanup | `purge_expired_data(session)` — deletes conversations/access logs past the configured retention period. |

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
| `POST /{slug}/messages` | `llmMs` | Wall-clock time inside the LLM (large language model) call. |
| | `ttsMs` | Wall-clock time inside the TTS (text-to-speech) call. `null` if TTS didn't run. |
| `POST /{slug}/messages/stream` (SSE `done` event) | `llmMs` | Time from request start to the full LLM reply being assembled. |
| | `firstChunkTextReadyMs` | Time until the first sentence chunk was handed to TTS (isolates LLM/chunking speed from TTS speed). |
| | `firstChunkMs` | Time until that first chunk's TTS synthesis *finished*. |
| | `ttsMs` | Summed synthesis time across all chunks. |
| `POST /{slug}/transcriptions` | `sttMs` | Wall-clock time inside the STT (speech-to-text) call — local Whisper or Parakeet, or the cloud provider. |

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