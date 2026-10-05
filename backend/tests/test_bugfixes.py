"""Regression tests for the bugs found during the backend restructuring — one section per bug,
each failing before its fix."""

from conftest import PASSWORD, login_as, make_user, new_client, parse_sse

# ==================== Disabled accounts can't log in ====================


def test_disabled_account_gets_a_clear_403_instead_of_a_useless_cookie(client, engine):
    admin = make_user(engine, email="admin@example.com", is_admin=True)
    teacher = make_user(engine, email="teacher@example.com")
    login_as(client, admin)
    client.put(f"/admin/users/{teacher.id}", json={"enabled": False})

    visitor = new_client()
    response = visitor.post("/auth/login", json={"email": "teacher@example.com", "password": PASSWORD})
    assert response.status_code == 403
    assert response.json() == {"detail": "ACCOUNT_DISABLED"}
    assert "access_token" not in response.headers.get("set-cookie", "")

    # A wrong password still looks exactly like an unknown account.
    wrong = visitor.post("/auth/login", json={"email": "teacher@example.com", "password": "wrong-pass-1"})
    assert wrong.json() == {"detail": "INVALID_CREDENTIALS"}


# ==================== Emails are case-insensitive ====================


def test_emails_are_normalized_and_compared_case_insensitively(client, engine):
    registered = new_client().post("/auth/register", json={"name": "Anna", "email": "Anna@Schule.de", "password": PASSWORD})
    assert registered.json()["email"] == "anna@schule.de"

    assert new_client().post("/auth/login", json={"email": "ANNA@schule.DE", "password": PASSWORD}).status_code == 200
    duplicate = new_client().post("/auth/register", json={"name": "A", "email": "anna@SCHULE.de", "password": PASSWORD})
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "EMAIL_ALREADY_REGISTERED"}


def test_accounts_stored_in_mixed_case_before_the_fix_still_work(client, engine):
    legacy = make_user(engine, email="Legacy@Schule.de")
    assert new_client().post("/auth/login", json={"email": "legacy@schule.de", "password": PASSWORD}).status_code == 200
    assert new_client().post(
        "/auth/register", json={"name": "L", "email": "legacy@schule.de", "password": PASSWORD}
    ).json() == {"detail": "EMAIL_ALREADY_REGISTERED"}

    other = login_as(new_client(), make_user(engine, email="other@schule.de"))
    assert other.put("/me", json={"email": "LEGACY@schule.de"}).status_code == 409
    # Re-saving your own address (in another case) isn't a conflict with yourself.
    assert login_as(new_client(), legacy).put("/me", json={"email": "LEGACY@SCHULE.DE"}).json()["email"] == "legacy@schule.de"


# ==================== Rate limiter is thread-safe ====================


def test_rate_limiter_counts_exactly_under_concurrency_and_sweeps_safely(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import HTTPException

    from app.core import rate_limit

    rate_limit._hits.clear()
    monkeypatch.setattr(rate_limit, "_SWEEP_THRESHOLD", 5)  # sweep on almost every call

    def hit(i: int) -> bool:
        # Every call also inserts a fresh key, so sweeps and inserts constantly overlap.
        rate_limit._enforce(f"other-{i}", max_requests=1, window_seconds=600, message="x")
        try:
            rate_limit._enforce("shared", max_requests=25, window_seconds=600, message="x")
            return True
        except HTTPException:
            return False

    with ThreadPoolExecutor(max_workers=32) as pool:
        allowed = sum(pool.map(hit, range(400)))
    assert allowed == 25
    rate_limit._hits.clear()


# ==================== Streaming chat sets the visitor cookie ====================


def test_streamed_message_sets_visitor_cookie_so_the_conversation_stays_together(client, chat_project):
    slug = chat_project["shareSlug"]
    # A visitor whose cookie expired mid-lesson: no page load, straight to the streamed chat.
    visitor = new_client()

    first = visitor.post(f"/public/{slug}/messages/stream", json={"message": "Hi"})
    assert parse_sse(first.text)[-1][0] == "done"
    assert "ah_visitor_id" in first.headers.get("set-cookie", "")

    # The second message reuses the cookie, so both land in one conversation.
    visitor.post(f"/public/{slug}/messages/stream", json={"message": "Und weiter?"})
    sessions = client.get("/conversations").json()
    assert sessions["total"] == 1
    assert sessions["items"][0]["messageCount"] == 4
