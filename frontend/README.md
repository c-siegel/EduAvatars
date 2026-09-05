# EduAvatars frontend

React + TypeScript single-page app (SPA) for EduAvatars: the dashboard where a user manages
projects/avatars, and the public chat page visitors use to talk to an avatar.

See the [root README](../README.md) for how this fits into the rest of the app, and
[CLAUDE.md](../CLAUDE.md) for how code in this repo is commented.

## Stack

- **React 18 + TypeScript**, built and served in dev mode by **Vite**.
- **react-router-dom** — client-side routing between pages.
- **TanStack Query** — fetching and caching data from the backend API. A global error handler
  (`src/main.tsx`) redirects to `/login` whenever any query or mutation reports an expired
  session — not just the initial auth check — so an auth cookie expiring mid-edit (e.g. in the
  Configurator) sends the user back to login instead of showing a generic error forever.
- **three.js** + **[@met4citizen/talkinghead](https://github.com/met4citizen/TalkingHead)** — 3D
  avatar rendering and lip-sync.
- **react-markdown** — renders chat messages that may contain Markdown.

## Folder map

| Path | Contents |
|---|---|
| `src/api/` | Functions that call the backend HTTP API |
| `src/components/` | Reusable UI pieces — small design-system components (`Button`, `Card`, `Table`, ...) and the avatar renderer (`TalkingHeadAvatar`, `Avatar`) |
| `src/hooks/` | Reusable React hooks |
| `src/i18n/` | Localization: English and German strings are found here in json |
| `src/layouts/` | Page layout wrappers (e.g. the dashboard shell) |
| `src/lib/` | Small standalone helper functions |
| `src/pages/` | One folder per route — see [Pages](#pages) below |
| `src/styles/` | Global styles |
| `src/types/` | Shared TypeScript types |

## Pages

| Route | Folder | What it's for |
|---|---|---|
| `/` | `Landing` | Marketing/info page for logged-out visitors |
| `/login`, `/register`, `/forgot-password`, `/reset-password` | `Login`, `Register`, `ForgotPassword`, `ResetPassword` | Account creation and recovery |
| `/dashboard` | `Dashboard/Overview` | A user's list of projects (avatars) |
| `/dashboard/projects/:id` | `Dashboard/Configurator` | The 5-step wizard for building a project: appearance, technical (AI provider/language), behavior (personality prompt), preview chat, publish. Publishing always saves the current draft first, so there's no separate "save, then publish" step. |
| `/dashboard/api` | `Dashboard/ApiDashboard` | Connect/manage a user's own LLM/TTS provider API keys ("bring your own key") |
| `/dashboard/analytics` | `Dashboard/Analytics` | Usage stats and per-conversation transcripts for a user's own projects |
| `/dashboard/profile` | `Dashboard/Profile` | Account settings: picture, password, logout-everywhere, account deletion |
| `/dashboard/change-password-required` | `Dashboard/ForcePasswordChange` | Forced password reset (e.g. after an admin-issued reset) |
| `/dashboard/admin`, `/dashboard/admin/settings` | `Dashboard/Admin` | Admin-only: manage other users, site-wide settings (e.g. registration on/off) |
| `/c/:projectSlug` | `PublicChat` | The public chat page visitors use — no login required |
| `/impressum`, `/datenschutz`, `/credits` | `Imprint`, `Privacy`, `Credits` | Legal/attribution pages (German URLs, matching German legal terminology) |

## Debugging

Open the public chat with `?latencyTest=1` appended to the URL (e.g.
`http://localhost:5173/c/<slug>?latencyTest=1`) to log latency timings to the browser console. The
query parameter only toggles these console logs — chat behavior is identical either way, and without
it the console stays silent.

- **Every message** (typed or spoken, streamed or not) logs a `[Latency-Test] Ping` — the total
  round-trip time from firing the request to the full reply text being ready. This is the quickest
  number to check for "is the server slow right now?".
- **Voice messages only** additionally log a full speech-to-audio breakdown after the avatar's
  spoken reply becomes audible — how long it took from releasing the mic button to hearing the
  reply, broken into STT (speech-to-text) round trip, LLM (large language model) time, TTS
  (text-to-speech) time, audio decode time, and speaking/animation stats. See `logLatency` in
  `src/pages/PublicChat/index.tsx` for what each field means (e.g. `sttBackendMs` is pure whisper
  time on the server, `sttRoundTripMs` also includes network time).

The backend-side timings that feed these logs (`llmMs`, `ttsMs`, `sttMs`, ...) are documented in
[backend/README.md](../backend/README.md#latency-monitoring).

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
