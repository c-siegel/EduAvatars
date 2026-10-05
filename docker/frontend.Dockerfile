# Build context is the repo root (see .github/workflows/docker-publish.yml, "context:" — this isn't
# built via docker-compose.yml, that only pulls prebuilt images).

# --- Stage 1: build frontend/dist ---
FROM node:20-alpine AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: static files + reverse proxy in a slim Caddy image ---
# No Node runtime in the final image — only the finished dist/ output is carried over.
FROM caddy:2-alpine
# Unlike backend.Dockerfile's user, this one has nothing to adjust at container start (its only
# volume, the speech recognition model, is mounted read-only and only needs to be world-readable —
# see docker-compose.yml), so a plain build-time USER is enough. Caddy can still bind port 80 as this
# user: caddy:2-alpine's own Dockerfile already grants the `caddy` binary itself
# cap_net_bind_service via setcap, which isn't tied to running as root.
RUN adduser -D -u 1000 caddyuser
COPY --from=build --chown=caddyuser:caddyuser /app/frontend/dist /srv
COPY --chown=caddyuser:caddyuser docker/Caddyfile /etc/caddy/Caddyfile
USER caddyuser
