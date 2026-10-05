"""
Analytics Stats Routes

Read-only numbers for the teacher-facing dashboards: aggregate stats and a timeseries for charts
(analytics page), plus the overview page's summary (/projects/stats). All scoped to the current
user's own projects — the queries live in service.py.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.deps import get_current_user, get_session
from app.features.analytics.schemas import AnalyticsStatsOut, TimeseriesPointOut
from app.features.analytics.service import get_project_overview, get_stats, get_timeseries_data
from app.features.projects.schemas import ProjectStats
from app.features.users.models import User

router = APIRouter(prefix="/analytics", tags=["analytics"])

# The overview's summary keeps its historical /projects/stats path. Registered before the project
# CRUD router (see app/api_router.py) so "stats" is never swallowed as a project id.
projects_router = APIRouter(prefix="/projects", tags=["projects"])


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


@projects_router.get("/stats", response_model=ProjectStats)
def get_stats_route(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Summary stats (project count, published count, sessions/messages this week) for the current user."""
    return get_project_overview(session, current_user.id)
