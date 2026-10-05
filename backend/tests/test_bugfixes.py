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
