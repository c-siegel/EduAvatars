"""
Analytics Request/Response Shapes

The response shapes for app/api/analytics.py's endpoints: aggregate stats, one row in the
paginated session list, and one point on the timeseries chart.

How to use:
    from app.models.schemas.analytics import AnalyticsStatsOut
"""

from app.core.schema import CamelModel
from app.models.schemas.chat import ChatHistoryEntry


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
    # The name/ID the visitor typed in, if the project's teacher enabled that gate (see
    # models/project.py::Project.require_visitor_name) — None for every session that didn't ask.
    visitor_name: str | None


class ConversationDetailOut(CamelModel):
    """Full message-by-message transcript of one saved conversation — what GET
    /analytics/sessions/{id} returns, as opposed to SessionRowOut's one-line summary."""

    id: str
    project_title: str
    visitor_name: str | None
    started_at: str
    messages: list[ChatHistoryEntry]


class SessionsPageOut(CamelModel):
    # {items, total} instead of a bare list — the frontend needs total for real pagination
    # ("1-4 of 1,284", see frontend/src/types/analytics.ts::SessionsPage).
    items: list[SessionRowOut]
    total: int


class TimeseriesPointOut(CamelModel):
    label: str
    value: int


class ConversationIdsIn(CamelModel):
    """Body shared by POST /analytics/export and POST /analytics/delete — which saved
    conversations (checked off in the analytics table, see
    frontend/src/pages/Dashboard/Analytics) to bundle into a CSV/ZIP download or delete."""

    conversation_ids: list[str]
