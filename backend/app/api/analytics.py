"""
Analytics Routes

Read-only endpoints for the teacher-facing analytics dashboard: aggregate stats, a paginated
list of individual chat sessions, a timeseries for charts, and a CSV export. All scoped to the
current user's own projects — the actual queries live in app/services/analytics_service.py.

What is a "session" here?
One session = one visitor's conversation with a published project (grouped by visitor_id, see
Conversation in app/models/conversation.py) — not an HTTP/login session.

How to use:
    from app.api import analytics

    app.include_router(analytics.router)
"""

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlmodel import Session

from app.core.deps import get_current_user, get_session
from app.models.schemas.analytics import AnalyticsStatsOut, SessionsPageOut, TimeseriesPointOut
from app.models.user import User
from app.services.analytics_service import get_sessions_paginated, get_stats, get_timeseries_data

router = APIRouter(prefix="/analytics", tags=["analytics"])

# The CSV export loads "all" matching sessions instead of one page — consistent with the rest of
# the filtering, and it avoids needing a separate query path just for the export.
_EXPORT_PAGE_SIZE = 10_000


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


@router.get("/export.csv")
def export_csv(
    project_id: str | None = None,
    period_days: int | None = None,
    model: str | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Export all matching sessions as a CSV file (ignores pagination — includes every match)."""
    result = get_sessions_paginated(
        session,
        current_user.id,
        project_id=project_id,
        model=model,
        days=period_days,
        page=1,
        per_page=_EXPORT_PAGE_SIZE,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Projekt", "Gestartet", "Nachrichten", "Dauer (s)", "Letzte Frage"])
    for row in result["items"]:
        writer.writerow([row.project_title, row.started_at, row.message_count, row.duration_seconds, row.last_question or ""])

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=eduavatars-sessions.csv"},
    )
