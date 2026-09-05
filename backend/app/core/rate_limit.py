"""
Rate Limiting for Endpoints That Don't Require a Login

This module protects endpoints anyone can call without logging in — the public chat, its
voice transcription, and login/register/password-reset — from being hammered by a single
visitor or bot. Not present in the source repo this project started from: none of these
routes had any protection before (cost risk on the public chat, brute-force / credential-
stuffing risk on login).

What is a sliding window?
Each call is tracked under a "key" (e.g. an IP address or email) together with a list of
timestamps. A new call is only allowed if fewer than `max_requests` timestamps for that key
fall within the last `window_seconds` — old timestamps simply age out of the window over
time. This is a simple in-memory MVP (minimum viable product) safeguard; for multi-process
deployments, swap it for something shared across processes (e.g. Redis).

Which key is trustworthy?
Only the client IP. The visitor id (ah_visitor_id) is a plain cookie the caller writes
themselves — clearing it hands out a fresh budget, so a limit keyed on it alone stops
nobody. The public chat is therefore limited on BOTH: per visitor (a tight limit that keeps
one honest browser tab in check) and per IP (the generous but actually enforceable ceiling).
The IP is only trustworthy if the app is told which proxy sits in front of it — see
FORWARDED_ALLOW_IPS in docker/docker-compose.yml, without which every request behind the
reverse proxy reports the proxy's own address and shares a single bucket.

How to use:
    from app.core.rate_limit import enforce_login_rate_limit

    @router.post("/login")
    def login(request: Request, credentials: LoginRequest):
        enforce_login_rate_limit(request, credentials.email)
        # raises HTTP 429 if this IP or email made too many attempts recently
        ...
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request

from app.core.config import settings
from app.core.error_codes import ErrorCode

# Timestamps (in seconds) of recent hits per rate-limit key, e.g. "login-ip:1.2.3.4".
_hits: dict[str, list[float]] = defaultdict(list)

# _enforce only ever trims a KEY's own timestamp list, never removes the key itself — a visitor
# or IP never seen again (very much the norm: visitor_id is a cookie that resets on every clear)
# would otherwise sit in this dict forever, growing it without bound over the process's lifetime.
# Once it grows past this size, a sweep drops every key that's stale under every window currently
# configured (see _sweep_stale_keys) — cheap to check, and keeps memory bounded without a
# separate background task.
_SWEEP_THRESHOLD = 5000


def _max_configured_window_seconds() -> int:
    """The largest rate-limit window currently in effect, across every limiter below."""
    return max(settings.chat_window_seconds, settings.transcribe_window_seconds, _UNLOCK_WINDOW_SECONDS, 600)


def _sweep_stale_keys() -> None:
    """Drop every key whose newest hit is older than the largest window in use.

    Safe by construction: such a key is necessarily also stale under its OWN (smaller-or-equal)
    window, so this can never forget a rate limit that's still actually in effect — a key that
    matters again simply gets recreated fresh on its next hit, same as any other new key.
    """
    now = time.monotonic()
    cutoff = _max_configured_window_seconds()
    stale_keys = [key for key, timestamps in _hits.items() if not timestamps or now - max(timestamps) > cutoff]
    for key in stale_keys:
        del _hits[key]

# Public chat and voice-transcription limits are Settings fields (app/core/config.py,
# CHAT_*/TRANSCRIBE_* env vars) instead of constants here, so a deployment can size them to its
# class without a rebuild — see the settings' own docstrings for the per-visitor/per-IP
# reasoning (a class typically shares one public IP behind NAT, and one spoken sentence is
# several transcription requests, not one).

# Tighter than the chat limits above: this gates a short, guessable PIN against brute-forcing,
# not just cost/abuse — a whole class sharing one IP still only needs a handful of attempts to
# get the password right once.
_UNLOCK_WINDOW_SECONDS = 600
_UNLOCK_MAX_PER_VISITOR = 5
_UNLOCK_MAX_PER_IP = 20


def _client_ip(request: Request) -> str:
    """The calling client's IP address, or "unknown" if the server didn't report one.

    Behind a reverse proxy this is only the real visitor once the proxy is trusted via
    uvicorn's --forwarded-allow-ips (see the module docstring) — otherwise every request
    reports the proxy's address, which makes every per-IP limit below a single shared bucket
    for the whole instance.
    """
    return request.client.host if request.client else "unknown"


def _enforce(key: str, *, max_requests: int, window_seconds: int, message: str) -> None:
    """Raise HTTP 429 if `key` already hit `max_requests` within the last `window_seconds`."""
    if len(_hits) > _SWEEP_THRESHOLD:
        _sweep_stale_keys()
    now = time.monotonic()
    recent = [t for t in _hits[key] if now - t < window_seconds]
    if len(recent) >= max_requests:
        raise HTTPException(status_code=429, detail=message)
    recent.append(now)
    _hits[key] = recent


def enforce_public_chat_rate_limit(request: Request, visitor_id: str) -> None:
    """Limit how often chat messages can be sent to a public chat, per visitor and per IP."""
    # The IP limit is checked FIRST and counts every attempt: a caller who rotates the
    # visitor cookie to dodge the per-visitor limit still consumes this budget, which is the
    # one they can't reset from the client side.
    message = ErrorCode.RATE_LIMIT_CHAT
    _enforce(
        f"chat-ip:{_client_ip(request)}",
        max_requests=settings.chat_max_per_ip,
        window_seconds=settings.chat_window_seconds,
        message=message,
    )
    _enforce(
        f"chat-visitor:{visitor_id}",
        max_requests=settings.chat_max_per_visitor,
        window_seconds=settings.chat_window_seconds,
        message=message,
    )


def enforce_public_transcribe_rate_limit(request: Request, visitor_id: str) -> None:
    """Limit how often voice recordings can be submitted for transcription, per visitor and per IP."""
    # Same two-dimension reasoning as the chat limit above — transcription is more expensive
    # per call (Whisper runs in-process), hence enforced on its own settings.
    message = ErrorCode.RATE_LIMIT_TRANSCRIBE
    _enforce(
        f"transcribe-ip:{_client_ip(request)}",
        max_requests=settings.transcribe_max_per_ip,
        window_seconds=settings.transcribe_window_seconds,
        message=message,
    )
    _enforce(
        f"transcribe-visitor:{visitor_id}",
        max_requests=settings.transcribe_max_per_visitor,
        window_seconds=settings.transcribe_window_seconds,
        message=message,
    )


def enforce_chat_unlock_rate_limit(request: Request, visitor_id: str) -> None:
    """Limit chat-password unlock attempts, per visitor and per IP."""
    message = ErrorCode.RATE_LIMIT_CHAT_UNLOCK
    _enforce(
        f"chat-unlock-ip:{_client_ip(request)}",
        max_requests=_UNLOCK_MAX_PER_IP,
        window_seconds=_UNLOCK_WINDOW_SECONDS,
        message=message,
    )
    _enforce(
        f"chat-unlock-visitor:{visitor_id}",
        max_requests=_UNLOCK_MAX_PER_VISITOR,
        window_seconds=_UNLOCK_WINDOW_SECONDS,
        message=message,
    )


def enforce_login_rate_limit(request: Request, email: str) -> None:
    """Limit login attempts, both per IP (10 per 10 minutes) and per email (5 per 10 minutes)."""
    # Two keys: per IP (stops one source from trying many accounts) AND per email (stops
    # distributed attempts against the same account from many IPs). Both count every attempt,
    # regardless of outcome — failed logins count too.
    message = ErrorCode.RATE_LIMIT_LOGIN
    _enforce(f"login-ip:{_client_ip(request)}", max_requests=10, window_seconds=600, message=message)
    _enforce(f"login-email:{email.lower()}", max_requests=5, window_seconds=600, message=message)


def enforce_register_rate_limit(request: Request) -> None:
    """Limit account registrations per IP (5 per 10 minutes)."""
    _enforce(
        f"register-ip:{_client_ip(request)}",
        max_requests=5,
        window_seconds=600,
        message=ErrorCode.RATE_LIMIT_REGISTER,
    )


def enforce_password_reset_rate_limit(request: Request, email: str) -> None:
    """Limit password-reset requests, both per IP (10 per 10 minutes) and per email (3 per 10 minutes)."""
    message = ErrorCode.RATE_LIMIT_GENERIC
    _enforce(f"reset-ip:{_client_ip(request)}", max_requests=10, window_seconds=600, message=message)
    _enforce(f"reset-email:{email.lower()}", max_requests=3, window_seconds=600, message=message)
