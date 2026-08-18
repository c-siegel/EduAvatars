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
COPY --from=build /app/frontend/dist /srv
COPY docker/Caddyfile /etc/caddy/Caddyfile
