"""Tests for get_or_set_visitor_id's cookie attributes (app/core/deps.py). The visitor-id cookie
previously had no `secure` flag (unlike the auth cookie's matching cookie_secure setting) and no
max_age (a bare session cookie) — unlike everything else it's supposed to persist through for the
length of one visit (rate-limit continuity, an already-unlocked password-protected chat)."""

import app.core.deps as deps_module
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.deps import VISITOR_ID_COOKIE, get_or_set_visitor_id


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    def whoami(visitor_id: str = Depends(get_or_set_visitor_id)):
        return {"visitor_id": visitor_id}

    return app


def test_sets_a_secure_cookie_with_a_max_age(monkeypatch) -> None:
    monkeypatch.setattr(deps_module.settings, "cookie_secure", True)
    client = TestClient(_make_app())

    response = client.get("/whoami")

    set_cookie = response.headers.get("set-cookie", "")
    assert VISITOR_ID_COOKIE in set_cookie
    assert "Secure" in set_cookie
    assert "Max-Age=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_reuses_an_existing_cookie_without_resetting_it() -> None:
    client = TestClient(_make_app())

    response = client.get("/whoami", cookies={VISITOR_ID_COOKIE: "existing-id"})

    assert response.json()["visitor_id"] == "existing-id"
    assert "set-cookie" not in response.headers
