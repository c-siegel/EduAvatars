"""Tests for update_profile's duplicate-email handling (app/features/users/service.py). Changing your own
email to one already used by another account used to raise an unhandled IntegrityError (a
generic 500) instead of the same clean 409 that registration and admin account creation already
return for the exact same underlying conflict (see features/auth/router.py,
features/users/admin_users_router.py)."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.db.base  # noqa: F401  (registers every model's table on SQLModel.metadata)
from app.features.users.models import User
from app.core.errors import DomainError
from app.features.users.schemas import ProfileUpdate
from app.features.users.service import update_profile


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

        with pytest.raises(DomainError) as exc_info:
            update_profile(session, me, ProfileUpdate(email="taken@example.com").model_dump(exclude_unset=True))

        assert exc_info.value.status_code == 409


def test_update_profile_allows_a_non_conflicting_email() -> None:
    with _make_session() as session:
        me = User(name="Sam", email="sam@example.com", password_hash="x")
        session.add(me)
        session.commit()
        session.refresh(me)

        result = update_profile(session, me, ProfileUpdate(email="new@example.com").model_dump(exclude_unset=True))

        assert result.email == "new@example.com"
