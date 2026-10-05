"""Regression tests for the bugs found during the backend restructuring — one section per bug,
each failing before its fix."""

from sqlmodel import Session

from app.features.projects.models import Project
from conftest import PASSWORD, browser_url, create_key, create_project, login_as, make_user, new_client, parse_sse, publish

GLB = b"glTF" + b"\x00" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

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


# ==================== Projects can only use their owner's avatars/backgrounds ====================


def test_project_cannot_reference_another_users_avatar_or_background(client, engine, teacher):
    avatar = client.post("/avatars", files={"file": ("Julia.glb", GLB, "model/gltf-binary")}).json()
    background = client.post("/backgrounds", files={"file": ("Klasse.png", PNG, "image/png")}).json()
    other = login_as(new_client(), make_user(engine, email="other@example.com"))

    created = other.post("/projects", json={"title": "X", "avatarModelId": avatar["id"]})
    assert created.status_code == 400
    assert created.json() == {"detail": "AVATAR_NOT_FOUND"}
    project = create_project(other)
    updated = other.put(f"/projects/{project['id']}", json={"avatarBackgroundId": background["id"]})
    assert updated.status_code == 400
    assert updated.json() == {"detail": "BACKGROUND_NOT_FOUND"}
    # Clearing stays possible.
    assert other.put(f"/projects/{project['id']}", json={"avatarModelId": None}).status_code == 200


def test_foreign_published_project_does_not_expose_a_users_avatar_or_background(client, engine, teacher):
    avatar = client.post("/avatars", files={"file": ("Julia.glb", GLB, "model/gltf-binary")}).json()
    background = client.post("/backgrounds", files={"file": ("Klasse.png", PNG, "image/png")}).json()
    other = login_as(new_client(), make_user(engine, email="other@example.com"))
    project = create_project(other)
    publish(other, project["id"])
    # A reference stored before the ownership check existed.
    with Session(engine) as session:
        row = session.get(Project, project["id"])
        row.avatar_model_id = avatar["id"]
        row.avatar_background_id = background["id"]
        session.add(row)
        session.commit()

    assert new_client().get(browser_url(avatar["fileUrl"])).status_code == 404
    assert new_client().get(browser_url(background["fileUrl"])).status_code == 404


# ==================== STT key references are checked ====================


def test_project_only_accepts_the_users_own_stt_key(client, engine, teacher):
    stt_key = create_key(client, key_type="stt", provider="gwdg_saia")
    llm_key = create_key(client)
    other = login_as(new_client(), make_user(engine, email="other@example.com"))
    foreign_stt_key = create_key(other, key_type="stt", provider="gwdg_saia")

    for wrong_id in (foreign_stt_key["id"], llm_key["id"], "does-not-exist"):
        response = client.post("/projects", json={"title": "X", "sttApiKeyId": wrong_id})
        assert response.status_code == 400
        assert response.json() == {"detail": "UNKNOWN_API_KEY"}
    project = create_project(client)
    assert client.put(f"/projects/{project['id']}", json={"sttApiKeyId": llm_key["id"]}).status_code == 400
    assert client.put(f"/projects/{project['id']}", json={"sttApiKeyId": stt_key["id"]}).json()["sttApiKeyId"] == stt_key["id"]


# ==================== An empty LLM reply is a clean chat failure ====================


def test_llm_reply_without_content_is_reported_as_unavailable_not_a_crash(client, chat_project, fake_ai):
    # E.g. a content filter or a tool call: the provider answers, but with content=None.
    fake_ai.llm_reply = None

    public = new_client().post(f"/public/{chat_project['shareSlug']}/messages", json={"message": "Hi"})
    assert public.status_code == 503
    assert public.json() == {"detail": "CHAT_UNAVAILABLE"}

    preview = client.post(f"/projects/{chat_project['id']}/chat/messages", json={"message": "Hi"})
    assert preview.status_code == 502
    assert preview.json()["detail"]["code"] == "LLM_REQUEST_FAILED"
    assert client.get("/conversations").json()["total"] == 0


# ==================== Preview transcription errors don't echo the API key ====================


def test_preview_transcription_error_scrubs_the_stt_key(client, chat_project, monkeypatch):
    from app.features.ai.stt.saia import SaiaClient

    def failing_transcribe(self, *args, **kwargs):
        raise RuntimeError("401 for https://saia.example/v1/audio?key=sk-test-secret-1234")

    monkeypatch.setattr(SaiaClient, "transcribe", failing_transcribe)
    stt_key = create_key(client, key_type="stt", provider="gwdg_saia")
    client.put(f"/projects/{chat_project['id']}", json={"sttEnabled": True, "sttApiKeyId": stt_key["id"]})

    files = {"audio": ("rec.webm", b"fake-audio", "audio/webm")}
    response = client.post(f"/projects/{chat_project['id']}/chat/transcriptions", files=files)
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["code"] == "STT_REQUEST_FAILED"
    assert "401 for" in detail["message"]
    assert "sk-test-secret-1234" not in detail["message"]


# ==================== Account deletion removes start-audio files ====================


def test_account_deletion_removes_the_projects_start_audio_files(client, engine, teacher, fake_ai):
    from pathlib import Path

    tts_key = create_key(client, key_type="tts")
    project = create_project(client, startPrompt="Willkommen", ttsEnabled=True, ttsApiKeyId=tts_key["id"])
    assert client.post(f"/projects/{project['id']}/start-audio").status_code == 200
    with Session(engine) as session:
        audio_path = Path(session.get(Project, project["id"]).start_audio_path)
    assert audio_path.is_file()

    assert client.delete("/me").status_code == 200
    assert not audio_path.exists()


# ==================== Analytics paging/period parameters are validated ====================


def test_analytics_rejects_zero_or_negative_page_and_period(client, teacher):
    for path in (
        "/conversations?page=0",
        "/conversations?page=-1",
        "/conversations?period_days=0",
        "/conversations/ids?period_days=-5",
        "/analytics/stats?period_days=0",
        "/analytics/timeseries?period_days=-1",
    ):
        assert client.get(path).status_code == 422, path
    assert client.get("/conversations?page=1&period_days=7").status_code == 200
    assert client.get("/analytics/stats?period_days=1").status_code == 200
