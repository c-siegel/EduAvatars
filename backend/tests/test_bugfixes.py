"""Regression tests for the bugs found during the backend restructuring — one section per bug,
each failing before its fix."""

from conftest import PASSWORD, login_as, make_user, new_client

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
