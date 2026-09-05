"""
Visitor Name Gate

The optional per-project gate that asks a visitor to type their name or ID before the public
chat starts (see models/project.py::Project.require_visitor_name) — the sibling of the chat
password gate in services/chat_password_service.py, but with no secret to verify: the entered
value just becomes a label on the visitor's saved Conversation, so a teacher can tell sessions
apart when downloading the chat protocol (app/api/analytics.py).

How to use:
    from app.services.visitor_name_service import assert_visitor_name_provided, clean_visitor_name

    visitor_name = clean_visitor_name(x_visitor_name)
    assert_visitor_name_provided(project, visitor_name)
"""

from urllib.parse import unquote

from fastapi import HTTPException

from app.core.error_codes import ErrorCode
from app.models.project import Project

# Generous enough for a real name or a classroom ID, short enough that nothing absurd ends up in
# the exported CSV/protocol.
MAX_VISITOR_NAME_LENGTH = 100


def clean_visitor_name(x_visitor_name: str | None) -> str | None:
    """Decode and trim the raw X-Visitor-Name header into a value safe to store, or None if
    empty/missing.

    URL-encoded on the way in (see frontend lib/visitorNameStorage.ts) because raw HTTP header
    values can't carry arbitrary Unicode — many real names (e.g. with ş, ü, 山) fall outside the
    Latin-1 range a header is restricted to.
    """
    if not x_visitor_name:
        return None
    decoded = unquote(x_visitor_name).strip()
    return decoded[:MAX_VISITOR_NAME_LENGTH] or None


def assert_visitor_name_provided(project: Project, visitor_name: str | None) -> None:
    """Reject the request if this project requires a visitor name and none was sent."""
    if project.require_visitor_name and not visitor_name:
        raise HTTPException(status_code=400, detail=ErrorCode.VISITOR_NAME_REQUIRED)
