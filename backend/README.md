# EduAvatars backend

EduAvatars' backend uses FastAPI as framework for building APIs with Python: user auth, avatar/project management, and calls out to LLM, text-to-speech (TTS), and speech-to-text (STT) providers.


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

## Known gap

`pyproject.toml` configures `testpaths = ["tests"]`, but no `tests/` directory exists yet in this
repo — there is currently no automated test suite to run.