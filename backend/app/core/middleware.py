"""
HTTP Middleware

App-wide middleware registered in app/main.py::create_app.
"""

from fastapi import Request


async def add_security_headers(request: Request, call_next):
    """Adds baseline security headers to every response.

    Defense-in-depth alongside the same headers set at the Caddy layer in production (see
    docker/Caddyfile) — this also covers Deploy A (uvicorn run directly, no Caddy in front) and
    any future non-Caddy topology. No Content-Security-Policy here, same reason as the
    Caddyfile: getting it right needs real browser testing against the three.js avatar, blob:
    audio playback, and the Tally survey iframe, not a guess that risks silently breaking them.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Harmless if this response is ever actually served over plain HTTP: browsers only honor
    # this header on a response they received over HTTPS (RFC 6797).
    response.headers["Strict-Transport-Security"] = "max-age=15552000"
    return response
