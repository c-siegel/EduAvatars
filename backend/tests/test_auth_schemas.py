"""Tests for LoginRequest's password-length guard (app/models/schemas/auth.py) — bcrypt raises
an unhandled error above 72 bytes instead of truncating, so this is the backstop that keeps a
single oversized login attempt from 500ing the request."""

import pytest
from pydantic import ValidationError

from app.models.schemas.auth import LoginRequest


def test_rejects_oversized_password() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="a@example.com", password="a" * 73)


def test_accepts_password_within_bcrypt_limit() -> None:
    assert LoginRequest(email="a@example.com", password="a" * 72).password == "a" * 72


def test_accepts_short_password() -> None:
    # Login must keep accepting existing passwords chosen under older/weaker rules — only the
    # byte-length cap applies here, unlike _validate_password_strength for setting a new one.
    assert LoginRequest(email="a@example.com", password="ab").password == "ab"
