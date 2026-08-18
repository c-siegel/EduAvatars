# EduAvatars frontend

React + TypeScript single-page app (SPA) for EduAvatars: the dashboard where a user manages
projects/avatars, and the public chat page visitors use to talk to an avatar.

See the [root README](../README.md) for how this fits into the rest of the app, and
[docs/STYLE.md](../docs/STYLE.md) for how code in this repo is commented.

## Stack

- **React 18 + TypeScript**, built and served in dev mode by **Vite**.
- **react-router-dom** — client-side routing between pages.
- **TanStack Query** — fetching and caching data from the backend API.
- **three.js** + **[@met4citizen/talkinghead](https://github.com/met4citizen/TalkingHead)** — 3D
  avatar rendering and lip-sync.
- **react-markdown** — renders chat messages that may contain Markdown.

## Folder map

| Path | Contents |
|---|---|
| `src/api/` | Functions that call the backend HTTP API |
| `src/components/` | Reusable UI pieces — small design-system components (`Button`, `Card`, `Table`, ...) and the avatar renderer (`TalkingHeadAvatar`, `Avatar`) |
| `src/hooks/` | Reusable React hooks |
| `src/layouts/` | Page layout wrappers (e.g. the dashboard shell) |
| `src/lib/` | Small standalone helper functions |
| `src/pages/` | One folder per route: `Landing`, `Login`, `Register`, `ForgotPassword`, `ResetPassword`, `Dashboard`, `PublicChat` |
| `src/styles/` | Global styles |
| `src/types/` | Shared TypeScript types |

## Debugging

Open the public chat with `?latencyTest=1` appended to the URL (e.g.
`http://localhost:5173/c/<slug>?latencyTest=1`) to log a speech-to-audio latency breakdown to the
browser console after every voice message — how long it took from releasing the mic button to the
avatar's spoken reply becoming audible. Useful for measuring real-world STT (speech-to-text) / LLM
(large language model) / TTS (text-to-speech) round-trip time.

Voice messages always auto-send once transcribed (no manual "Senden" click) — the query parameter
only toggles the console log, not that behavior. Without it, the chat behaves identically but stays
silent in the console. See `logLatency` in `src/pages/PublicChat/index.tsx` for what each logged
field means (e.g. `sttBackendMs` is pure whisper time on the server, `sttRoundTripMs` also includes
network time).

## Local setup

Step-by-step setup (`npm install`, dev server) now lives in the root README — see
[Deploy A: local development](../README.md#deploy-a-local-development). Start the backend first
(it must be running at `http://localhost:8000` for the dev server's `/api/*` proxy to work — see
`vite.config.ts`).

Other scripts:
```bash
npm run build     # type-checks and builds a production bundle into dist/
npm run preview   # serves the production build locally
```
