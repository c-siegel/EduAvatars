# EduAvatars

**Create a talking 3D avatar, give it a personality, and share it as a link — no coding
required to use it, once someone has set it up for you.**

EduAvatars is a web app for building custom AI characters that students, visitors, or
colleagues can talk to in a browser, by typing or by speaking out loud. A teacher (or anyone
with an account) creates a "project": a persona described in plain language, backed by an AI
language model, with a 3D face and a voice. Publishing a project turns it into a public link —
visitors need no account and no technical knowledge to use it.

<p align="center">
  <img src="docs/screenshots/public-chat.svg" alt="Screenshot placeholder: a visitor talking to a published avatar" width="720">
</p>

## Who is this for?

- **Teachers and instructors** — build a subject-matter tutor, an exam-prep quiz partner, a
  historical figure students can interview, or an always-available FAQ desk for your course.
  See [Using EduAvatars as a teacher](#using-eduavatars-as-a-teacher) below — no installation
  needed if your institution already runs an instance.
- **Researchers and institutions** — self-host to keep full control over student data, export
  anonymized conversation logs for study, and compare answer quality/latency/cost across
  several AI providers side by side. See [Using EduAvatars as a researcher](#using-eduavatars-as-a-researcher).
- **Developers and IT admins** — a small, self-contained FastAPI + React stack you can run
  locally in minutes or deploy with Docker. See [Deployment](#deployment).

## What you can do

- **Give an avatar a personality.** Describe how it should behave in plain language (a system
  prompt) — e.g. "You are a patient calculus tutor who never gives away the final answer
  directly."
- **Pick a 3D face and a voice.** Every project starts with two bundled 3D faces to choose from
  (Julia and David), or upload your own; add a background image if you like; pick a synthesized
  voice from any connected provider.
- **Talk by typing or by speaking.** Visitors can type a message or hold a button to speak —
  their speech is transcribed automatically, and the avatar answers out loud with matching lip
  movement.
- **Share one link, nothing to install.** A published project gets a public chat URL. Visitors
  need no account, no API key, and no software.
- **Protect access if needed.** Optionally require a password before the chat starts, or ask
  visitors to type a name/ID first so their sessions are easy to tell apart afterwards.
- **Bring your own AI provider key.** Connect Anthropic, OpenAI, Google Gemini, Mistral,
  Cartesia, Google Cloud TTS (text-to-speech), a self-hosted/Ollama model, an OpenAI-compatible
  endpoint, or GWDG Arcana. See [Supported AI providers](#supported-ai-providers).
- **Ground answers in your own material.** Upload scripts, worksheets or notes (PDF, Word, text,
  Markdown) to a knowledge base and attach it to a project: before each reply, the best-matching
  passages are handed to the AI, whichever provider it is (RAG — retrieval-augmented
  generation). Optional module, see [Knowledge bases](#knowledge-bases-optional).
- **Review usage afterwards.** A built-in analytics dashboard shows session counts, message
  volume, and per-conversation transcripts, exportable as CSV/ZIP.
- **Use it in English or German.** The dashboard and public chat UI (user interface) are fully
  translated into both.

<p align="center">
  <img src="docs/screenshots/configurator.svg" alt="Screenshot placeholder: the project configurator wizard" width="720">
</p>

## Using EduAvatars as a teacher

If someone else (your IT department, your institution) already runs an EduAvatars instance for
you, none of the setup below applies — just:

1. **Log in** (or register, if open registration is enabled) at your instance's web address.
2. **Create a project** from the dashboard: give it a name, pick an avatar and a background
   image.
3. **Connect an AI provider**, or ask your admin whether one is already available for everyone
   to use. This is the "brain" that generates the avatar's replies.
4. **Describe the avatar's personality** — a short instruction in plain language for how it
   should behave and what it should know or avoid.
5. **Preview it** — chat with your own avatar right in the wizard before anyone else sees it.
6. **Publish** — you get a shareable link. Optionally add a password, or require visitors to
   enter their name first. Publishing always saves your latest changes first, so there's no
   separate "save, then publish" step to remember.
7. **Check back later** under Analytics to see how many people talked to it and read through
   individual conversations.

## Using EduAvatars as a researcher

- **Self-host for data control.** Running your own instance (see [Deployment](#deployment))
  means conversation data never leaves infrastructure you control — relevant if you're working
  with student data under institutional data-protection rules.
- **Export conversation data.** The Analytics dashboard exports individual sessions or a bulk
  ZIP of everything for offline analysis.
  <p align="center">
    <img src="docs/screenshots/analytics.svg" alt="Screenshot placeholder: the analytics dashboard" width="600">
  </p>
- **Compare AI providers.** Because API keys are bring-your-own and swappable per project, you
  can run the same persona against different LLMs (large language models) or voices and compare
  cost, latency, or answer quality.
- **Ground answers in your own material.** Knowledge bases (RAG, retrieval-augmented generation)
  work with every provider; transcripts and CSV exports record which document and page each reply
  was given, and the latency test times the lookup. The GWDG Arcana provider offers its own,
  separately hosted knowledge base too.
- **Measure latency.** Every response is timed server-side (LLM, TTS, STT stage-by-stage) and
  the frontend can log matching client-side timings — see
  [backend/README.md](backend/README.md#latency-monitoring) — useful if you're studying
  response-time perception or comparing infrastructure choices. The dashboard's **Latency test**
  page runs scripted student conversations on any device and compares configurations (speech
  recognition on the device or the server, LLM, streaming, speech output, avatar on/off) — see
  [docs/latency-test.md](docs/latency-test.md).

## Project status

EduAvatars is under active development. The core flow — create a project, publish it, chat by
text or voice, view analytics — works end to end and is what this repo's default configuration
is built around. Automated test coverage is still thin (see
[backend/README.md](backend/README.md#tests)), and some rougher edges (error messages, mobile
layout, provider coverage) are still being smoothed out. Expect it to keep evolving.

Backend tests run in CI on every tagged release, and Docker images are only published if they
(and the frontend build) pass — see [`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml).
There's no CI gate on regular pull requests yet, only on the tag/publish step.

## Architecture

The app is split into two independent apps plus a deployment folder:

| Part | What it is | Docs |
|---|---|---|
| [`backend/`](backend/) | FastAPI (Python) API: auth, projects, LLM/TTS/STT calls, analytics | [backend/README.md](backend/README.md) |
| [`frontend/`](frontend/) | React + TypeScript single-page app, 3D avatar rendering with three.js enabled by [TalkingHead](https://github.com/met4citizen/TalkingHead) by Mika Suominen | [frontend/README.md](frontend/README.md) |
| [`local-tts/`](local-tts/) | Optional self-hosted text-to-speech sidecar, so no cloud key is needed for speech output | [local-tts/README.md](local-tts/README.md) |
| [`rag/`](rag/) | Optional knowledge service: parses teachers' documents, indexes them and finds matching passages | [rag/README.md](rag/README.md) |
| [`docker/`](docker/) | Docker images, Compose file, and reverse-proxy config for deployment | [docker/README.md](docker/README.md) |

The frontend talks to the backend over HTTP; the backend optionally calls the local-TTS sidecar
over HTTP too, when a project has no cloud TTS key configured, and the knowledge service when a
project has knowledge bases attached. In production, Caddy (in
`docker/`) reverse-proxies the frontend and backend behind a single domain.

<p align="center">
  <img src="docs/architecture.svg" alt="Diagram: browsers talk to Caddy, which routes /api/* to the FastAPI backend and serves the frontend elsewhere; the backend reads/writes SQLite + uploaded files and calls out to external AI providers" width="820">
</p>

## Deployment

There are two ways to run EduAvatars: locally for development (Deploy A), or with Docker for a
real deployment (Deploy B). Both read the same `.env` file at the repo root, so it only needs to
be set up once.

### Create the `.env` file

```bash
cp .env.example .env
```
Fill in the two required secrets (no default):

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | Signs login tokens (JWT = JSON Web Token). Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `API_KEY_ENCRYPTION_SECRET` | Encrypts stored provider API keys. Generate with `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

Both are validated at startup, not just required to be present: the app refuses to boot if either
is left at a placeholder value (e.g. `change-me`), too short, or — for `API_KEY_ENCRYPTION_SECRET`
— not actually a valid Fernet key, with an error telling you which one and how to generate a good
one. This catches a copy-pasted `.env.example` before it ever reaches production, not after.

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

<details>
<summary>On Windows (PowerShell)</summary>

```powershell
# From the repo root: create .env, then fill in the two secrets as described above
# (use `py` instead of `python3` in the generate commands)
Copy-Item .env.example .env

cd backend
py -3.11 -m venv .venv            # any Python >= 3.11; `py --list` shows what's installed
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```
- `uvicorn : Die Benennung "uvicorn" wurde nicht … erkannt` / `uvicorn is not recognized`: the
  virtual environment isn't active in this window. Activate it again (needed in every new
  PowerShell window; the prompt then starts with `(.venv)`), or call it without activating:
  `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload`.
- `Activate.ps1 cannot be loaded because running scripts is disabled`: allow local scripts for
  your user once with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
</details>

To get your first admin account (dashboard access to manage other accounts, site settings, ...),
either set `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `.env` and run
`python -m app.cli.bootstrap_admin` from `backend/` (same idempotent step Deploy B runs
automatically on every container start), or promote an existing account by hand in the database.

**2. Frontend** (full details: [frontend/README.md](frontend/README.md))
```bash
cd frontend
npm install
npm run dev
```
The app is now available at `http://localhost:5173` and proxies `/api/*` requests to the backend.

**3. Speech recognition model** (optional, ~380 MB on disk): voice input is transcribed on the
visitor's own device by default, from model files the app hosts itself. Download them once with
```bash
scripts/fetch-stt-model.sh   # writes ./models, which the Vite dev server serves at /models/
```
Without them, voice input still works — the browser fails to load the model and falls back to
transcribing on the server.

### Local text-to-speech (optional)

By default, projects that leave the TTS key unset simply get no speech output (unlike voice
*input*, which always falls back to a bundled offline model — see
[Supported AI providers](#supported-ai-providers)). [`local-tts/`](local-tts/) adds that same kind
of no-key-needed fallback for speech *output*: a small self-hosted TTS engine running as its own
process, so nobody needs a cloud API key just to hear an avatar speak.

It's opt-in. Each teacher can also clone voices from their own short recordings (Dashboard →
Voices) and pick one per project. In Docker it's an optional service — see
[docker/README.md](docker/README.md#local-text-to-speech-optional). To try it locally:

```bash
cd local-tts
python3 -m venv .venv
./.venv/bin/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
./.venv/bin/pip install -e .
TTS_MODEL_CACHE_DIR="$PWD/.cache" TTS_VOICES_DIR="$PWD/voices" \
  ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 --app-dir .
```

Then tell the backend to use it — set these two variables before starting it (e.g. add them to
`.env`):

```bash
LOCAL_TTS_ENABLED=true
LOCAL_TTS_URL=http://127.0.0.1:8080
```

Projects speak either with a teacher's own voice clip (Dashboard → Voices) or with a default
clip per language — see [`local-tts/voices/README.md`](local-tts/voices/README.md); the repo ships
none by default.
Full details, including the model's resource footprint and API: [local-tts/README.md](local-tts/README.md).

### Knowledge bases (optional)

Teachers upload their own documents (Dashboard → Knowledge) and attach them to projects
(Configurator, step 3); before each reply, the passages that best match the student's message are
added to the system prompt. This works with every LLM provider. The work happens in a separate
service, [`rag/`](rag/), which is off unless you switch it on: it parses uploads in a sandbox,
embeds them with a local model by default (teachers can pick an API embedding model instead), and
keeps the index in its own SQLite file. Design and safety measures:
[docs/rag-plan.md](docs/rag-plan.md). In Docker it's an optional service, see
[docker/README.md](docker/README.md#knowledge-bases-optional). To try it locally:

```bash
cd rag
python3 -m venv .venv && ./.venv/bin/pip install -e .
export RAG_SERVICE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
RAG_DATA_DIR="$PWD/.data" ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8090
```

and start the backend with the same token:

```bash
RAG_ENABLED=true
RAG_SERVICE_URL=http://127.0.0.1:8090
RAG_SERVICE_TOKEN=<the same value>
```

The first upload downloads the local embedding model (about 600 MB) from Hugging Face. Upload
limits (file size, pages, quotas) are set by an admin under Admin → Settings.

### Deploy B: Docker (production)

Runs both apps as containers behind a Caddy reverse proxy — the setup used for real deployments
(built for TrueNAS SCALE, but works on any Docker host). Full details, including the systemd
unit: [docker/README.md](docker/README.md).

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d
```
The example `docker-compose.yml` pulls prebuilt images (`chsiegel/eduavatars:frontend`/`:backend`) rather than building them — Caddy serves the frontend and reverse-proxies `/api/*` to the backend. TLS is expected to be terminated upstream (e.g. a Cloudflare Tunnel). The `web` service listens on port `30080` by default.

## Supported AI providers

Every project picks its own LLM (large language model, for generating replies) and, optionally,
its own TTS (text-to-speech) voice — each user connects these with their own API key under
"API Keys" in the dashboard. STT (speech-to-text, for voice input) needs no key from anyone: it
runs on the visitor's own device (Parakeet Redux via WebGPU, with live text while speaking), and
on a device that can't run it, falls back to a bundled offline model on the server; TTS can optionally work the same way if
the deployment runs the [local-TTS sidecar](#local-text-to-speech-optional) — leave a project's
TTS key unset and it falls back to that instead of producing no audio.

| Provider | Used for | Notes |
|---|---|---|
| Anthropic | LLM | Claude models |
| OpenAI | LLM + TTS | GPT models for chat, `tts-1` for voices |
| Google Gemini | LLM + TTS | |
| Mistral | LLM | |
| Ollama | LLM | Self-hosted, e.g. on your own GPU server |
| OpenAI-compatible endpoint | LLM | Any self-hosted or third-party API that mimics OpenAI's (Together.ai, Groq, ...) |
| Cartesia | TTS | |
| Google Cloud TTS | TTS | The classic per-character Cloud TTS product, not Gemini's built-in voice |
| GWDG Arcana | LLM | German academic cloud provider; adds RAG (retrieval-augmented generation) against a knowledge base you configure there |

Adding a new provider is a matter of one entry in
[`backend/app/core/providers.py`](backend/app/core/providers.py) — the frontend's provider list
and validation are generated from that single source, so nothing else needs to change.

For Ollama and OpenAI-compatible keys, the endpoint address you enter can be anything on your own
network (e.g. a school's LAN GPU box) — the backend only rejects addresses that could never be a
real LLM/TTS server, like a cloud metadata endpoint, to close off that one otherwise-easy misuse of
a "bring your own endpoint" field.

### Requirements for on-device speech recognition

Voice input is transcribed in the visitor's browser only when **all** of the following hold.
Otherwise the chat shows a short notice and voice input goes through the server instead, so it
keeps working, just without live text while speaking and with a bit more delay.

**On the server**
- The model files are in place: `scripts/fetch-stt-model.sh` (Deploy A) or the `stt-model`
  service (Deploy B, automatic). Check: `/models/parakeet-redux/v1/manifest.json` loads.
- `BROWSER_STT_ENABLED` is not set to `false`, and the project has voice input enabled.
- The site is served over **HTTPS** (or opened as `localhost`). Browsers turn off WebGPU and the
  microphone on plain HTTP.

**On the visitor's device**
- **A browser with WebGPU that finds a usable GPU.** The API being there isn't enough: the app asks
  for a GPU adapter, and the device falls back to the server if it doesn't get one.
  - iPad / iPhone: **iPadOS / iOS 26 or newer** (Safari 26 is the first Safari with WebGPU on by
    default). Older iPads that can't update to 26 (or are held back by device management) always
    use the server. This is the most likely reason some iPads in the pilot didn't support it.
    Lockdown Mode also turns WebGPU off.
  - Windows, macOS, ChromeOS: current Chrome or Edge. Safari 26 on macOS.
  - Android: current Chrome on Android 12 or newer; some GPUs are still left out.
  - Firefox: only on Windows so far.
- **Enough memory.** The model takes ~350 MB of GPU memory next to the 3D avatar. iPadOS reloads
  tabs that use too much, which hits older iPads with little RAM first.
- **~400 MB of free storage** for the browser's cache. Private browsing keeps nothing, so the
  model downloads again on every visit.
- **Microphone permission** for the site.

**Network.** A device's first visit downloads ~175 MB. A class of 25 iPads opening the chat at
the same time therefore pulls ~4.4 GB through the school's network, so let the devices open the
chat link once before the lesson (the model then comes from the browser cache, and the chat is
ready in a few seconds). Safari can delete a site's stored data after 7 days without a visit, so
on iPads used only weekly, expect the download again now and then. On Deploy B behind Cloudflare, also see
[docker/README.md](docker/README.md#deploying) for letting Cloudflare cache the model.

To check a specific device, open `/stt-test` on it and follow
[docs/stt-device-test.md](docs/stt-device-test.md).

## Tech stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI |
| Database | SQLite via SQLModel/SQLAlchemy, migrations with Alembic |
| Auth | JWT (JSON Web Tokens) + bcrypt password hashing |
| LLM / TTS providers | [litellm](https://github.com/BerriAI/litellm) (provider-agnostic client) |
| Speech-to-text | [Parakeet Redux](https://huggingface.co/moondream/parakeet-redux) on the visitor's device via [onnxruntime-web](https://onnxruntime.ai/) + WebGPU (default, live text while speaking); [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (or optionally Parakeet, `STT_ENGINE=parakeet`) in the backend process as the fallback |
| Local text-to-speech (optional) | [sopro](https://github.com/samuel-vitorino/sopro), runs in its own sidecar process (see `local-tts/`) |
| Frontend framework | React 18 + TypeScript, built with Vite |
| 3D avatar rendering | three.js + [@met4citizen/talkinghead](https://github.com/met4citizen/TalkingHead) |
| Frontend data fetching | TanStack Query |
| Deployment | Docker Compose + Caddy, built by default for TrueNAS SCALE, but PUID/GID can be changed in `.env` file |

## 3D avatars and lip-sync

The avatar rendering and lip-sync are built on two MIT-licensed libraries by the same author
(Mika Suominen):

- **[TalkingHead](https://github.com/met4citizen/TalkingHead)** (npm: `@met4citizen/talkinghead`)
  — renders and animates the 3D avatar (see `frontend/src/components/TalkingHeadAvatar/`). Two
  models, Julia and David, ship under `frontend/public/avatars/` and are offered as defaults in
  every project's configurator — see that folder's `ATTRIBUTION.md` for license and details. Its
  repo's README documents how to create or prepare new avatar models compatible with the
  renderer — check that if you want to add avatars beyond the ones bundled here.
- **[HeadAudio](https://github.com/met4citizen/HeadAudio)** — computes lip-sync visemes directly
  from the played audio signal in real time, instead of text-based timing estimation. No npm
  package; vendored into `frontend/public/headaudio/` (see that folder's `ATTRIBUTION.md` for
  license and details).

## Data privacy note

EduAvatars itself does not phone home or share data with its developers. User accounts,
project settings, and conversation records stay on whichever server you (or your institution)
deploy the app to — see [Deploy B](#deploy-b-docker-production) for running your own instance.

This does **not** mean conversations stay fully private: every chat message is sent to whichever
third-party AI provider that project is configured to use (voice input is transcribed on the
visitor's device by default, so the audio itself only leaves it on the server fallback, or with
a project-configured cloud STT key) — see [Supported AI providers](#supported-ai-providers) — since that's what generates the
avatar's replies. That provider's own data-handling terms apply to that traffic, independent of
where you host EduAvatars itself. Password-reset emails (only if you configure SMTP) are the
only other outbound traffic the backend generates on its own.

Knowledge bases (if enabled) stay on your server with the default local embedding model. A
teacher who picks an API embedding model instead sends the full text of their documents to that
provider when they're indexed. Original files are deleted as soon as they're parsed; deleting a
document, knowledge base or account deletes its indexed text too. Material attached to a
published project can be quoted by anyone who can open its link — teachers confirm they may make
it available when they upload.

Whether a given deployment and provider choice satisfies your institution's data-protection
requirements (e.g. GDPR — General Data Protection Regulation) is something you need to assess
yourself; this project does not provide a data-processing agreement or legal review on your
behalf.

If an admin sets a conversation retention period (Admin → Settings), it's enforced continuously
for as long as the backend process runs — re-checked every few hours, not just once when the
container happens to restart — so data past that limit doesn't linger indefinitely on a
long-uptime deployment.

## Contributing

Issues and pull requests are welcome. There's no formal contribution process yet — open an issue
to discuss a change before investing time in a large one.

## License

MIT — see [LICENSE](LICENSE).
