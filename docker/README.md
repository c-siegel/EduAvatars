# Deploying EduAvatars

Everything needed to run EduAvatars in production with Docker: images, a Compose file, the
reverse-proxy config, and a systemd unit. Works on any Docker host — the backend container's app
user adapts to whatever UID/GID owns your data directory via `PUID`/`PGID` (see
[Deploying](#deploying) below). The defaults for both happen to match **TrueNAS SCALE**'s built-in
"apps" user, so a TrueNAS deployment needs no extra configuration, but nothing here is TrueNAS-only.

See the [root README](../README.md) for what the app does and for the shared `.env` setup, and
[CLAUDE.md](../CLAUDE.md) for how code in this repo is commented.

## What's here

| File | Purpose |
|---|---|
| `backend.Dockerfile` / `frontend.Dockerfile` | Build the backend and frontend images. Both run as a non-root user; the backend's adapts its UID/GID at container start to match the bind-mounted data directory (see below), the frontend's is a fixed user since it has no data directory to adapt to |
| `backend-entrypoint.sh` | Container startup: creates upload/cache folders, runs database migrations, then starts the API |
| `Caddyfile` | Reverse-proxy config — routes `/api/*` to the backend, serves the frontend's static files otherwise (with SPA fallback so client-side routes work on page reload); also sets baseline security response headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, HSTS) on every response |
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

## Health checks

Both containers have a Docker healthcheck (`docker-compose.yml`): `backend` polls its own
`/health` endpoint directly (via Python's `urllib`, since the slim base image has no curl/wget);
`web` checks Caddy's own static file serving, not the backend — a backend outage shouldn't make an
orchestrator restart Caddy, which wouldn't fix it. `web`'s `depends_on` waits for `backend`'s
healthcheck to pass, not just for its container to have started.

The backend's `/health` is reachable two ways behind Caddy: `/api/health` (the general `/api/*`
route) and the bare `/health` path (a dedicated route in `Caddyfile`, for whatever external load
balancer or uptime monitor tries the more obvious URL first). Both hit the same endpoint.

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

To get your first admin account (dashboard access to manage other accounts and site settings),
set `ADMIN_EMAIL`/`ADMIN_PASSWORD` in the root `.env` before the first start — `backend-
entrypoint.sh` creates or promotes that account on every container start (a no-op once it's
already an admin), so the values are safe to leave in `.env` indefinitely.

**On a non-TrueNAS host**, also set `PUID`/`PGID` in `.env` to the UID/GID that should own
`EDUAVATARS_DATA_DIR` (e.g. your own user's `id -u`/`id -g`) — otherwise the backend container
defaults to UID/GID 568 (TrueNAS's built-in "apps" user) and won't have write access to a data
directory owned by anyone else. The backend's entrypoint adjusts its in-container user to match at
every start (see `backend-entrypoint.sh`), so the image itself doesn't need rebuilding for a
different host.

## Deploying behind another reverse proxy

Some hosts (e.g. a university's own infrastructure) put another reverse proxy — commonly nginx —
in front of everything, terminating TLS there instead of via a Cloudflare Tunnel. `docker/Caddyfile`
needs no changes for this: `auto_https off` already means Caddy expects TLS to be terminated by
whatever sits in front of it, and it doesn't care whether that's cloudflared or an institutional
nginx.

Point the outer proxy at the `web` container's exposed port (`30080` by default) and configure it
to:

- **Preserve the `Host` header** — Caddy's site block only matches requests whose `Host` header
  equals `SITE_ADDRESS`. Many reverse proxies default to sending their own upstream address as
  `Host` instead of forwarding the original one, which makes Caddy reject the request.
- **Forward `X-Forwarded-For` and `X-Forwarded-Proto`** — otherwise the backend can't see the real
  visitor address (see `FORWARDED_ALLOW_IPS` below) or scheme.
- **Not buffer the streamed chat reply** — `backend/app/api/public_chat.py`'s chat endpoint streams
  its reply as `text/event-stream` so a student hears the first words as soon as they're ready.
  A proxy that buffers the whole response before forwarding it defeats that.

An nginx `location` block covering all three:

```nginx
location / {
    proxy_pass http://<docker-host>:30080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_read_timeout 300s;
}
```

(No WebSocket `Upgrade`/`Connection` headers needed — the app only uses SSE for streaming, not
WebSockets.)

Also add this outer proxy's own address to `FORWARDED_ALLOW_IPS` in `.env` — see the comment next
to it in `.env.example` for why: it's now an extra hop that appends itself to `X-Forwarded-For`,
and every hop in that chain has to be trusted or the real visitor address is lost.
