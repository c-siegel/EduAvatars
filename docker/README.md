# Deploying EduAvatars

Everything needed to run EduAvatars in production with Docker: images, a Compose file, the
reverse-proxy config, and a systemd unit. Works on any Docker host — the backend container's app
user adapts to whatever UID/GID owns your data directory via `PUID`/`PGID` (see
[Deploying](#deploying) below). The defaults for both happen to match **TrueNAS SCALE**'s built-in
"apps" user, so a TrueNAS deployment needs no extra configuration, but nothing here is TrueNAS-only.

See the [root README](../README.md) for what the app does and for the shared `.env` setup, and
[docs/STYLE.md](../docs/STYLE.md) for how code in this repo is commented.

## What's here

| File | Purpose |
|---|---|
| `backend.Dockerfile` / `frontend.Dockerfile` | Build the backend and frontend images |
| `backend-entrypoint.sh` | Container startup: creates upload/cache folders, runs database migrations, then starts the API |
| `Caddyfile` | Reverse-proxy config — routes `/api/*` to the backend, serves the frontend's static files otherwise (with SPA fallback so client-side routes work on page reload) |
| `docker-compose.yml` | The two-container stack (`web` = frontend+Caddy, `backend` = the API) |
| `eduavatars.service` | systemd unit to start/stop the stack on boot |

The `.env` file itself lives one level up, at the repo root — see [Deploying](#deploying) below.

## How it fits together

`docker-compose.yml` **pulls** prebuilt images (`chsiegel/eduavatars:frontend` /
`chsiegel/eduavatars:backend`) rather than building them itself — the two Dockerfiles are used in
a separate build/publish step. The `web` container runs Caddy, which serves the built frontend
and reverse-proxies API calls to the `backend` container. Caddy itself only speaks plain HTTP
(`auto_https off`); TLS is expected to be terminated in front of it (e.g. a Cloudflare Tunnel).

Both services read their configuration from `../.env` (relative to this folder) via
`env_file: ../.env` — the same file used by [Deploy A](../README.md#deploy-a-local-development).
This assumes the repo is checked out on the host and Compose is run from within it (e.g. via
`eduavatars.service`), not e.g. pasted into a UI that only takes the YAML without the surrounding
repo.

## Deploying

This assumes the repo is checked out on the host (e.g. at `/opt/eduavatars`) — see the root
[README](../README.md#deployment) for the shared `.env` setup (`cp .env.example .env` at the repo
root, then fill in the required secrets).

1. Start the stack from the repo root:
   ```bash
   docker compose -f docker/docker-compose.yml --env-file .env up -d
   ```
   The `web` service listens on port `30080` by default (see `docker-compose.yml`).

   **`--env-file .env` is required, not optional.** Without it, Compose falls back to looking for a
   `.env` file next to the compose file itself (`docker/.env`) for `${VAR}` substitution — which
   doesn't exist, since the real one lives at the repo root. `EDUAVATARS_DATA_DIR` would silently
   resolve to an empty string, turning the volume mount into `- :/data` and breaking the container
   at startup. (`eduavatars.service` already passes the equivalent absolute-path flag.)
2. Optional — run it as a systemd service so it survives reboots: install `eduavatars.service`
   (it expects the repo checked out at `/opt/eduavatars` — adjust `WorkingDirectory` and the
   paths in `ExecStart`/`ExecStop` if you use a different location) and enable it with
   `systemctl enable --now eduavatars`.

For a real (non-`localhost`) deployment, also set `SITE_ADDRESS`, `CORS_ORIGINS`,
`FRONTEND_BASE_URL`, and `EDUAVATARS_DATA_DIR` in the root `.env` — see `.env.example` for what
each one does.

**On a non-TrueNAS host**, also set `PUID`/`PGID` in `.env` to the UID/GID that should own
`EDUAVATARS_DATA_DIR` (e.g. your own user's `id -u`/`id -g`) — otherwise the backend container
defaults to UID/GID 568 (TrueNAS's built-in "apps" user) and won't have write access to a data
directory owned by anyone else. The backend's entrypoint adjusts its in-container user to match at
every start (see `backend-entrypoint.sh`), so the image itself doesn't need rebuilding for a
different host.

## Known gaps

**The project was just renamed from AvatarHub to EduAvatars in this repo.** The following still
need to be done outside this repo before a production deploy will work:
- Build and push new images to Docker Hub as `chsiegel/eduavatars:frontend` /
  `chsiegel/eduavatars:backend` (the old `chsiegel/avatarhub:*` images still exist but are no
  longer referenced by `docker-compose.yml`).
- Rename/move the data directory on the host to match `EDUAVATARS_DATA_DIR`.
- Re-install `eduavatars.service` and disable the old `avatarhub.service` unit.
