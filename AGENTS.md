# AGENTS.md

Guidance for AI coding agents (Claude Code, Codex, Cursor, …) working in this repository. Human
contributors are welcome to read it too. Keep it short: link to the READMEs instead of copying them.

## What this is

EduAvatars lets a teacher build a talking 3D avatar (persona = system prompt + LLM + voice + 3D
face) and publish it as a public link. Visitors — usually students, without an account — chat with
it by typing or speaking. Teachers review conversations in an analytics dashboard.

- `backend/` — FastAPI + SQLModel + Alembic (SQLite), litellm for LLM/TTS, faster-whisper/Parakeet
  for STT. Python ≥ 3.11. Details: [backend/README.md](backend/README.md)
- `frontend/` — React 18 + TypeScript + Vite, three.js via TalkingHead, react-query, i18next.
  Details: [frontend/README.md](frontend/README.md)
- `local-tts/` — optional self-hosted TTS sidecar. `docker/` — images, Compose, Caddy.

## Commands

```bash
# Backend (from backend/)
pip install -e ".[dev]"
python -m pytest                          # conftest.py sets throwaway secrets; no .env needed
python -m alembic upgrade head
python -m alembic revision --autogenerate -m "Add foo to project"   # then review by hand
uvicorn app.main:app --reload             # http://localhost:8000, needs .env (see README)

# Frontend (from frontend/)
npm ci
npm run build                             # tsc -b + vite build — this is the type check
npm run dev                               # http://localhost:5173, proxies /api to :8000
```

There is no linter/formatter config and no CI on pull requests — CI only runs on tagged releases
(`.github/workflows/docker-publish.yml`: backend `pytest` + frontend `npm run build`). So run both
yourself before you push.

## Where things live

- `backend/app/features/<area>/` — one folder per domain (`auth`, `projects`, `chat`, `media`,
  `analytics`, `api_keys`, `users`, `site_settings`, `ai`), each split into `router.py`,
  `service.py`, `schemas.py`, `models.py`. Routers stay thin; logic goes in the service.
- `backend/app/features/ai/{llm,tts,stt}/` — provider implementations behind a `base.py`
  interface. Adding a provider: [backend/README.md#adding-an-ai-provider](backend/README.md#adding-an-ai-provider)
- `backend/app/core/` — config, auth deps, rate limiting, errors. `backend/alembic/versions/` — migrations.
- `frontend/src/` — `api/` (one module per backend area), `components/`, `layouts/`, `hooks/`,
  `lib/`, `types/`, `i18n/locales/{de,en}.json`.

## Rules

**Data and security**
- Teachers only ever see their own projects, keys, voice clips and conversations. Use the existing
  ownership dependencies (e.g. `get_owned_project`) on every route that loads a teacher's resource;
  admin routes check the admin role.
- The public chat is unauthenticated: only published projects, password protection and rate limits
  must hold.
- Provider API keys are stored encrypted and are never returned to the client, logged, or exported.
- Conversations are student data: nothing personal in logs; exports and retention must keep working.

**Database**
- Every model change needs an Alembic migration in the same change. It must work on SQLite (use
  `op.batch_alter_table` for alter/drop, give new NOT NULL columns a `server_default`) and have a
  real `downgrade()`. Keep a single head.

**Frontend**
- Every user-visible string goes through `t()` and into **both** `de.json` and `en.json`
  (German is the fallback language).

**Tests**
- Backend tests use the fixtures in `backend/tests/conftest.py`, which fake providers at the
  litellm / model-loader seam. Never call a real provider or download a model in tests.
- Fixing a bug: add a regression test that fails without the fix.

**Docs**
- New env variable → `.env.example` (with a comment saying which deploy path uses it) and the
  matching README. New feature/provider/route → update the relevant README section.

**Code style**
- Code comments are always in English. When you come across a German comment, translate it.
- Comments explain *why*, not *what*. Match the naming and structure of the surrounding code.
- Don't add dependencies without a reason; pin a version cap with a comment when a newer major is
  known to break (see `av<19` in `backend/pyproject.toml`).

**Never commit** `.env`, `uv.lock`, `*.db`, `backend/uploads/`, `models/` or other generated files.

## Git and pull requests

- Develop new features and bug fixes on the branch `claude/working-branch`. Never create a new
  branch per session.
- Pull requests always target `working-branch`.
- Commit subjects: imperative, sentence case, no prefix, no trailing period — e.g.
  "Add avatar-only and chat-only layouts for the public chat". The body explains why.
- Never add the Claude session link or a `Claude-Session:` line to commit messages or PR
  descriptions.
- One topic per commit; don't mix refactors with behaviour changes.

## Subagents

Project subagents live in `.claude/agents/`:

| Agent | Use it when |
|---|---|
| `backend-test-writer` | backend code changed or a bug is being fixed |
| `migration-reviewer` | a `models.py` changed or a migration was added |
| `i18n-checker` | user-visible frontend text changed |
| `frontend-verifier` | frontend changed — build + Playwright screenshots |
| `security-privacy-auditor` | auth, public chat, API keys, uploads, analytics/export changed |
| `docs-sync` | settings, env variables, providers or features changed |

## Known pitfalls

- `av` (PyAV) is capped below 19: faster-whisper still passes an argument PyAV 19 removed.
- The 3D avatar (WebGL) and audio often don't work in headless browsers — verify the rest of the
  page instead of treating that as a bug.
- On-device STT model files come from `scripts/fetch-stt-model.sh` (writes `./models`, ~380 MB,
  git-ignored). Without them the browser falls back to server-side STT.
- The settings module validates `JWT_SECRET` / `API_KEY_ENCRYPTION_SECRET` at import time; the app
  refuses to start with placeholder values.
