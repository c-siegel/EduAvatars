// The URL path prefix the site is served under: "" at the root, e.g. "/lola" under a sub-path.
// Read from index.html's <base href>, which Caddy fills in from BASE_PATH per request (see
// vite.config.ts and docker/Caddyfile), so one build works under any prefix. Root-relative paths
// like "/avatars/julia.glb" ignore <base>, so every one the app builds itself goes through
// sitePath(); URLs the backend hands out already carry the prefix (backend/app/core/urls.py).
export const BASE_PATH = (document.querySelector("base")?.getAttribute("href") ?? "/").replace(/\/+$/, "");

export function sitePath(path: string): string {
  return `${BASE_PATH}${path}`;
}
