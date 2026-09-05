"""
Analytics Routes

Read-only endpoints for the teacher-facing analytics dashboard: aggregate stats, a paginated
list of individual chat sessions, a timeseries for charts, and a per-conversation CSV/ZIP export.
All scoped to the current user's own projects — the actual queries live in
app/services/analytics_service.py.

What is a "session" here?
One session = one visitor's conversation with a published project (grouped by visitor_id, see
Conversation in app/models/conversation.py) — not an HTTP/login session.

How to use:
    from app.api import analytics

    app.include_router(analytics.router)
"""

import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session

from app.core.deps import get_current_user, get_session
from app.core.error_codes import ErrorCode
from app.models.schemas.analytics import (
    AnalyticsStatsOut,
    ConversationDetailOut,
    ConversationIdsIn,
    SessionsPageOut,
    TimeseriesPointOut,
)
from app.models.user import User
from app.services.analytics_service import (
    build_conversation_csv,
    conversation_export_filename,
    delete_conversations,
    get_conversation_detail,
    get_conversations_for_export,
    get_session_ids,
    get_sessions_paginated,
    get_stats,
    get_timeseries_data,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/stats", response_model=AnalyticsStatsOut)
def read_stats(
    project_id: str | None = None,
    period_days: int = 7,
    model: str | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Aggregate stats (session/message counts, ...) for the current user's projects."""
    return get_stats(session, current_user.id, project_id=project_id, days=period_days, model=model)


@router.get("/sessions", response_model=SessionsPageOut)
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


@router.get("/sessions/ids", response_model=list[str])
def read_session_ids(
    project_id: str | None = None,
    period_days: int | None = None,
    model: str | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Every conversation id matching the given filters, ignoring pagination — what the "select
    all" button in the analytics table calls before a bulk export, since the table itself only
    ever has the current page's ids loaded. Registered before /sessions/{conversation_id} so
    "ids" isn't swallowed as a conversation id."""
    return get_session_ids(session, current_user.id, project_id=project_id, model=model, days=period_days)


@router.get("/sessions/{conversation_id}", response_model=ConversationDetailOut)
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


@router.get("/timeseries", response_model=list[TimeseriesPointOut])
def read_timeseries(
    project_id: str | None = None,
    period_days: int = 30,
    model: str | None = None,
    granularity: str = "day",
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Session/message counts over time, bucketed by day/week/month, for charting."""
    granularity = granularity if granularity in ("day", "week", "month") else "day"
    return get_timeseries_data(
        session, current_user.id, project_id=project_id, model=model, days=period_days, granularity=granularity
    )


@router.post("/export")
def export_conversations(
    data: ConversationIdsIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Export one or more saved conversations, checked off in the analytics table, as CSV.

    A single conversation comes back as a plain .csv; more than one is bundled into a .zip (one
    .csv per conversation) — browsers don't let a page trigger several file downloads at once
    without extra prompts, so a bulk export has to be one file. Ids that don't exist or don't
    belong to current_user's own projects are silently skipped, same as read_session_detail.
    """
    rows = get_conversations_for_export(session, current_user.id, data.conversation_ids)
    if not rows:
        raise HTTPException(status_code=404, detail=ErrorCode.CONVERSATION_NOT_FOUND)

    if len(rows) == 1:
        conversation, project = rows[0]
        return Response(
            content=build_conversation_csv(conversation, project),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{conversation_export_filename(conversation, project)}"'},
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        # Two different conversations can otherwise land on the same "<project>_<time>_<name>.csv"
        # name (e.g. two anonymous visitors starting in the same minute) — de-duplicated with a
        # numeric suffix so neither entry silently overwrites the other inside the archive.
        used_names: dict[str, int] = {}
        for conversation, project in rows:
            name = conversation_export_filename(conversation, project)
            if name in used_names:
                used_names[name] += 1
                stem, _, ext = name.rpartition(".")
                name = f"{stem}-{used_names[name]}.{ext}"
            else:
                used_names[name] = 0
            archive.writestr(name, build_conversation_csv(conversation, project))

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="eduavatars-gespraeche.zip"'},
    )


@router.post("/delete", status_code=204)
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
