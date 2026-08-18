# EduAvatars

Eduavatars is a web app for creating and talking to a 3D avatar in the browser. A teacher (or any user) creates a "project" — a persona backed by an LLM (large language model), with a 3D avatar and a voice — and can share it as a public chat link. Visitors, who do not need an account or API key, type or speak to the avatar, which answers with generated speech and lip-synced animation.

## Architecture

The app is split into two independent apps plus a deployment folder:

| Part | What it is | Docs |
|---|---|---|
| [`backend/`](backend/) | FastAPI (Python) API: auth, projects, LLM/TTS/STT calls, analytics | [backend/README.md](backend/README.md) |
| [`frontend/`](frontend/) | React + TypeScript single-page app, 3D avatar rendering with three.js | [frontend/README.md](frontend/README.md) |
| [`docker/`](docker/) | Docker images, Compose file, and reverse-proxy config for deployment | [docker/README.md](docker/README.md) |

The frontend talks to the backend over HTTP. In production, Caddy (in `docker/`) reverse-proxies both behind a single domain.

## Deployment

There are two ways to run EduAvatars: locally for development (Deploy A), or with Docker for a
real deployment (Deploy B). Both read the same `.env` file at the repo root, so it only needs to
be set up once.

### Shared setup: the `.env` file

```bash
cp .env.example .env
```
Fill in the two required secrets (no default):

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | Signs login tokens. Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `API_KEY_ENCRYPTION_SECRET` | Encrypts stored provider API keys. Generate with `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

`.env.example` has a comment on every other variable explaining which deploy path (A, B, or both)
uses it — see that file for the full list (SMTP, `SITE_ADDRESS`, `EDUAVATARS_DATA_DIR`, ...).

### Deploy A: local development

Run the backend and frontend directly on your machine — no Docker needed.

**1. Backend** (full details: [backend/README.md](backend/README.md))
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m alembic upgrade head
uvicorn app.main:app --reload
```
The API is now available at `http://localhost:8000` (health check: `GET /health`).

**2. Frontend** (full details: [frontend/README.md](frontend/README.md))
```bash
cd frontend
npm install
npm run dev
```
The app is now available at `http://localhost:5173` and proxies `/api/*` requests to the backend.

### Deploy B: Docker (production)

Runs both apps as containers behind a Caddy reverse proxy — the setup used for real deployments
(built for TrueNAS SCALE, but works on any Docker host). Full details, including the systemd
unit: [docker/README.md](docker/README.md).

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d
```
`docker-compose.yml` pulls prebuilt images (`chsiegel/eduavatars:frontend`/`:backend`) rather than
building them — Caddy serves the frontend and reverse-proxies `/api/*` to the backend. TLS is
expected to be terminated upstream (e.g. a Cloudflare Tunnel). The `web` service listens on port
`30080` by default.

## Tech stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI |
| Database | SQLite via SQLModel/SQLAlchemy, migrations with Alembic |
| Auth | JWT (JSON Web Tokens) + bcrypt password hashing |
| LLM / TTS providers | [litellm](https://github.com/BerriAI/litellm) (provider-agnostic client) |
| Speech-to-text | [faster-whisper](https://github.com/SYSTRAN/faster-whisper), runs in the backend process |
| Frontend framework | React 18 + TypeScript, built with Vite |
| 3D avatar rendering | three.js + [@met4citizen/talkinghead](https://github.com/met4citizen/TalkingHead) |
| Frontend data fetching | TanStack Query |
| Deployment | Docker Compose + Caddy, built for TrueNAS SCALE |

## 3D avatars and lip-sync

The avatar rendering and lip-sync are built on two MIT-licensed libraries by the same author
(Mika Suominen):

- **[TalkingHead](https://github.com/met4citizen/TalkingHead)** (npm: `@met4citizen/talkinghead`)
  — renders and animates the 3D avatar (see `frontend/src/components/TalkingHeadAvatar/`). Its
  repo's README documents how to create or prepare new avatar models compatible with the
  renderer — check that if you want to add avatars beyond the ones bundled here.
- **[HeadAudio](https://github.com/met4citizen/HeadAudio)** — computes lip-sync visemes directly
  from the played audio signal in real time, instead of text-based timing estimation. No npm
  package; vendored into `frontend/public/headaudio/` (see that folder's `ATTRIBUTION.md` for
  license and details).

## Documentation conventions

Code comment and docstring conventions (how the codebase is documented, not just this README)
are written down in [docs/STYLE.md](docs/STYLE.md).

## License

MIT — see [LICENSE](LICENSE).