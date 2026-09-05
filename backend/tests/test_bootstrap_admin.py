"""Tests for bootstrap_admin's email/password validation (app/cli/bootstrap_admin.py).
register_user() is a bare service function with no validation of its own — the normal
/auth/register route only ever reaches it after RegisterRequest's Pydantic validators already
passed, but bootstrap_admin calls it directly with raw ADMIN_EMAIL/ADMIN_PASSWORD env var
strings. Without its own check, ADMIN_PASSWORD=1 would silently create a fully privileged admin
with a one-character password."""

from sqlmodel import Session, SQLModel, create_engine, select

import app.db.base  # noqa: F401  (registers every model's table on SQLModel.metadata)
from app.cli import bootstrap_admin as bootstrap_admin_module
from app.cli.bootstrap_admin import bootstrap_admin
from app.models.user import User


def _use_temp_engine(monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(bootstrap_admin_module, "engine", engine)
    return engine


def test_rejects_weak_admin_password_and_creates_no_account(monkeypatch) -> None:
    engine = _use_temp_engine(monkeypatch)
    monkeypatch.setattr(bootstrap_admin_module.settings, "admin_email", "admin@example.com")
    monkeypatch.setattr(bootstrap_admin_module.settings, "admin_password", "1")  # no digit rule, too short

    bootstrap_admin()

    with Session(engine) as session:
        assert session.exec(select(User)).all() == []


def test_rejects_malformed_admin_email_and_creates_no_account(monkeypatch) -> None:
    engine = _use_temp_engine(monkeypatch)
    monkeypatch.setattr(bootstrap_admin_module.settings, "admin_email", "not-an-email")
    monkeypatch.setattr(bootstrap_admin_module.settings, "admin_password", "a-strong-password1")

    bootstrap_admin()

    with Session(engine) as session:
        assert session.exec(select(User)).all() == []


def test_creates_admin_with_valid_credentials(monkeypatch) -> None:
    engine = _use_temp_engine(monkeypatch)
    monkeypatch.setattr(bootstrap_admin_module.settings, "admin_email", "admin@example.com")
    monkeypatch.setattr(bootstrap_admin_module.settings, "admin_password", "a-strong-password1")

    bootstrap_admin()

    with Session(engine) as session:
        user = session.exec(select(User)).first()
        assert user is not None
        assert user.email == "admin@example.com"
        assert user.is_admin is True
