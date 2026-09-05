"""
Chat Password Verification

Checks a public chat's optional teacher-set password (see Project.chat_password_hash) and the
short-lived unlock token a visitor gets after entering it correctly.

How to use:
    from app.services.chat_password_service import assert_unlocked

    assert_unlocked(project, visitor_id, unlock_token)
    # raises HTTP 401 if the project is password-protected and the token doesn't check out
"""

import jwt
from fastapi import HTTPException

from app.core.error_codes import ErrorCode
from app.core.security import create_chat_unlock_token, decode_chat_unlock_token, verify_password
from app.models.project import Project


def verify_chat_password(project: Project, password: str) -> bool:
    """Check `password` against the project's chat password. False if the project isn't protected."""
    if project.chat_password_hash is None:
        return False
    return verify_password(password, project.chat_password_hash)


def is_unlocked(project: Project, visitor_id: str, token: str | None) -> bool:
    """Whether `token` proves `visitor_id` already unlocked `project`'s chat. Never raises."""
    if not project.password_protected:
        return True
    if not token:
        return False
    try:
        project_id, unlocked_visitor_id = decode_chat_unlock_token(token)
    except jwt.InvalidTokenError:
        return False
    return project_id == project.id and unlocked_visitor_id == visitor_id


def assert_unlocked(project: Project, visitor_id: str, token: str | None) -> None:
    """Raise HTTP 401 unless `token` proves `visitor_id` already unlocked `project`'s chat."""
    if not is_unlocked(project, visitor_id, token):
        raise HTTPException(status_code=401, detail=ErrorCode.CHAT_UNLOCK_REQUIRED)


def issue_unlock_token(project: Project, visitor_id: str) -> str:
    """Issue a new unlock token for `visitor_id` after a correct password check."""
    return create_chat_unlock_token(project.id, visitor_id)
