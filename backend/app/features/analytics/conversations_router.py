"""
Saved Conversation Routes

The analytics table's per-conversation actions: a paginated list of individual chat sessions,
one session's full transcript, and bulk export (CSV/ZIP) or deletion of the checked-off ones.
All scoped to the current user's own projects.

What is a "session" here?
One session = one visitor's conversation with a published project (grouped by visitor_id, see
Conversation in app/features/chat/models.py) — not an HTTP/login session.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session

from app.core.deps import get_current_user, get_session
from app.core.error_codes import ErrorCode
from app.features.analytics.csv_export import build_export
from app.features.analytics.schemas import ConversationDetailOut, ConversationIdsIn, SessionsPageOut
from app.features.analytics.service import (
    delete_conversations,
    get_conversation_detail,
    get_conversations_for_export,
    get_session_ids,
    get_sessions_paginated,
)
from app.features.users.models import User

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=SessionsPageOut)
def read_sessions(
    project_id: str | None = None,
    period_days: int | None = None,
    model: str | None = None,
    page: int = 1,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Paginated list of individual chat sessions, optionally filtered by project/period/model."""
    result = get_sessions_paginated(
        session, current_user.id, project_id=project_id, model=model, days=period_days, page=page
    )
    return SessionsPageOut(items=result["items"], total=result["total"])


@router.get("/ids", response_model=list[str])
def read_session_ids(
    project_id: str | None = None,
    period_days: int | None = None,
    model: str | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Every conversation id matching the given filters, ignoring pagination — what the "select
    all" button in the analytics table calls before a bulk export, since the table itself only
    ever has the current page's ids loaded. Registered before /{conversation_id} so
    "ids" isn't swallowed as a conversation id."""
    return get_session_ids(session, current_user.id, project_id=project_id, model=model, days=period_days)


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def read_session_detail(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Full message-by-message transcript of one saved conversation — what the "view" action on
    a session row (frontend Analytics page) opens, since the table/CSV only ever show a
    truncated last question."""
    detail = get_conversation_detail(session, current_user.id, conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=ErrorCode.CONVERSATION_NOT_FOUND)
    return detail


@router.post("/export")
def export_conversations(
    data: ConversationIdsIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Export one or more saved conversations, checked off in the analytics table, as CSV — a
    single conversation as a plain .csv, several bundled into a .zip (see csv_export.py).

    Ids that don't exist or don't belong to current_user's own projects are silently skipped,
    same as read_session_detail.
    """
    rows = get_conversations_for_export(session, current_user.id, data.conversation_ids)
    if not rows:
        raise HTTPException(status_code=404, detail=ErrorCode.CONVERSATION_NOT_FOUND)
    content, media_type, filename = build_export(rows)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/batch-delete", status_code=204)
def delete_conversations_route(
    data: ConversationIdsIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Permanently delete the saved conversations checked off in the analytics table. Unlike
    export_conversations, an empty or already-gone selection is not an error (deleting something
    that's no longer there is a no-op, not a failure) — ids that don't belong to current_user's
    own projects are silently skipped, same as export."""
    delete_conversations(session, current_user.id, data.conversation_ids)
