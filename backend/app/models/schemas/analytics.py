"""
Analytics Request/Response Shapes

The response shapes for app/api/analytics.py's endpoints: aggregate stats, one row in the
paginated session list, and one point on the timeseries chart.

How to use:
    from app.models.schemas.analytics import AnalyticsStatsOut
"""

from app.core.schema import CamelModel


class AnalyticsStatsOut(CamelModel):
    sessions: int
    sessions_delta_pct: float
    messages: int
    messages_delta_pct: float
    avg_duration_seconds: int
    avg_duration_delta_pct: float
    token_cost_eur: float
    token_cost_delta_pct: float


class SessionRowOut(CamelModel):
    id: str
    project_title: str
    started_at: str
    message_count: int
    duration_seconds: int
    last_question: str | None


class SessionsPageOut(CamelModel):
    # {items, total} instead of a bare list — the frontend needs total for real pagination
    # ("1-4 of 1,284", see frontend/src/types/analytics.ts::SessionsPage).
    items: list[SessionRowOut]
    total: int


class TimeseriesPointOut(CamelModel):
    label: str
    value: int
