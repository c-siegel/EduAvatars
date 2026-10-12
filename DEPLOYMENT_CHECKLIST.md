# Deployment checklist

Things still needed before EduAvatars runs publicly. Tick them off as they are done.

## Browser and brand assets
- [ ] Favicon: `favicon.svg` plus a 32×32 `favicon.ico` fallback in `frontend/public/`, linked from `frontend/index.html`.
- [ ] `apple-touch-icon.png` (180×180).
- [ ] PWA icons (192×192 and 512×512, plus a maskable variant) and a `site.webmanifest` with name, short name and theme colour.
- [ ] `<meta name="theme-color">` and `<meta name="description">` in `frontend/index.html`.
- [ ] Open Graph and Twitter card image (1200×630) with `og:title`, `og:description`, `og:url`, so shared links to public avatars get a preview.
- [ ] Logo as SVG that matches the `Wordmark` component.

## Web and SEO
- [ ] `robots.txt` (decide what must not be indexed, e.g. `/c/*` and `/dashboard`) and optionally `sitemap.xml`.
- [ ] A 404 page for unknown routes.
- [ ] Per-route `<title>`, so tabs and history are distinguishable.

## Legal and content
- [ ] Real imprint (`/impressum`) and privacy policy (`/datenschutz`) for the operator and jurisdiction.
- [ ] Review what is stored in `localStorage` and cookies, and decide whether a consent banner is required.
- [ ] Terms of use linked from the registration checkbox (currently the text only mentions them).
- [ ] Documentation site and its final URL, then set `VITE_DOCS_URL` for the frontend image build.

## Operations
- [ ] Domain and TLS (Caddy handles certificates); set `FRONTEND_BASE_URL` and the CORS/host settings in `.env`.
- [ ] Strong, unique `JWT_SECRET` and `API_KEY_ENCRYPTION_SECRET` (the app refuses placeholders).
- [ ] Email provider for password reset; decide the registration policy (open, `REGISTRATION_ENABLED=false`, invite-only).
- [ ] Backups for the SQLite database and `uploads/`, and a tested restore.
- [ ] Release process: tag, then `docker-publish.yml` builds the images. The workflow passes `APP_COMMIT`, so the footer shows the exact build.
- [ ] Error monitoring and uptime checks.
