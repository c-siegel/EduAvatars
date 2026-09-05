"""Tests for update_profile's duplicate-email handling (app/api/profile.py). Changing your own
email to one already used by another account used to raise an unhandled IntegrityError (a
generic 500) instead of the same clean 409 that registration and admin account creation already
return for the exact same underlying conflict (see api/auth.py, api/admin.py)."""

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

import app.db.base  # noqa: F401  (registers every model's table on SQLModel.metadata)
from app.api.profile import update_profile
from app.models.schemas.profile import ProfileUpdate
from app.models.user import User


def _make_session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_update_profile_rejects_duplicate_email_with_a_clean_409() -> None:
    with _make_session() as session:
        session.add(User(name="Alex", email="taken@example.com", password_hash="x"))
        me = User(name="Sam", email="sam@example.com", password_hash="x")
        session.add(me)
        session.commit()
        session.refresh(me)

        with pytest.raises(HTTPException) as exc_info:
            update_profile(ProfileUpdate(email="taken@example.com"), current_user=me, session=session)

        assert exc_info.value.status_code == 409


def test_update_profile_allows_a_non_conflicting_email() -> None:
    with _make_session() as session:
        me = User(name="Sam", email="sam@example.com", password_hash="x")
        session.add(me)
        session.commit()
        session.refresh(me)

        result = update_profile(ProfileUpdate(email="new@example.com"), current_user=me, session=session)

        assert result.email == "new@example.com"
