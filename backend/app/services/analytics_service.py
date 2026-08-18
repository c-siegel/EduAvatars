"""
Analytics Queries

The actual database queries behind the analytics routes (app/api/analytics.py): aggregate
stats, a paginated session list, and a timeseries for charts — each scoped to a user's own
projects and optionally filtered by project/model/time period.

How to use:
    from app.services.analytics_service import get_stats

    stats = get_stats(session, user_id, days=7)
"""

import json
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, func, select

from app.models.conversation import Conversation
from app.models.project import Project
from app.models.project_access import ProjectAccess
from app.models.schemas.analytics import AnalyticsStatsOut, SessionRowOut

MAX_STATS_DAYS = 90
MAX_TIMESERIES_DAYS = 365


def weekly_active_students(session: Session, user_id: str) -> int:
    """Count distinct visitors across a user's projects in the last 7 days."""
    since = datetime.now(timezone.utc) - timedelta(days=7)
    return session.exec(
        select(func.count(func.distinct(ProjectAccess.visitor_id)))
        .join(Project, Project.id == ProjectAccess.project_id)
        .where(Project.user_id == user_id, ProjectAccess.accessed_at >= since)
    ).one()


def conversations_for_project(session: Session, project_id: str) -> list[Conversation]:
    """List all saved conversations for one project."""
    # Only meaningful if Project.save_conversations was enabled.
    return list(session.exec(select(Conversation).where(Conversation.project_id == project_id)))


def _apply_common_filters(query, user_id: str, project_id: str | None, model: str | None):
    """Apply the shared user/project/model filters used by every analytics query below."""
    query = query.where(Project.user_id == user_id)
    if project_id:
        query = query.where(Project.id == project_id)
    if model:
        query = query.where(Project.llm_model == model)
    return query


def get_stats(
    session: Session,
    user_id: str,
    project_id: str | None = None,
    days: int = 7,
    model: str | None = None,
) -> AnalyticsStatsOut:
    """Calculate aggregate analytics stats for a user (optionally filtered by project/model)."""
    days = min(days, MAX_STATS_DAYS)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Sessions = page loads of the published chat page (ProjectAccess), as a plain COUNT instead
    # of loading the rows — previously every access row re-summed all of the project's
    # conversations, which would multiply messages/avg-duration for repeat visits to one project.
    access_count_query = _apply_common_filters(
        select(func.count(ProjectAccess.id)).join(Project, Project.id == ProjectAccess.project_id),
        user_id,
        project_id,
        model,
    ).where(ProjectAccess.accessed_at >= cutoff)
    sessions_count = session.exec(access_count_query).one()

    # Messages/duration come from the conversations updated within the period — once per
    # conversation, not once per page load.
    conversations_query = _apply_common_filters(
        select(Conversation).join(Project, Project.id == Conversation.project_id),
        user_id,
        project_id,
        model,
    ).where(Conversation.updated_at >= cutoff)
    conversations = session.exec(conversations_query).all()

    messages_count = 0
    total_duration_seconds = 0.0
    for conv in conversations:
        msg_list = json.loads(conv.messages_json)
        messages_count += len(msg_list)
        total_duration_seconds += (conv.updated_at - conv.started_at).total_seconds()
    avg_duration = int(total_duration_seconds / len(conversations)) if conversations else 0

    # Deltas (comparison to the previous period) and token cost are deliberately not part of this
    # phase — that would need real per-litellm-call token/cost tracking, which isn't persisted
    # anywhere yet. Returned as 0 instead of faking a number.
    return AnalyticsStatsOut(
        sessions=sessions_count,
        sessions_delta_pct=0,
        messages=messages_count,
        messages_delta_pct=0,
        avg_duration_seconds=avg_duration,
        avg_duration_delta_pct=0,
        token_cost_eur=0,
        token_cost_delta_pct=0,
    )


def get_sessions_paginated(
    session: Session,
    user_id: str,
    project_id: str | None = None,
    model: str | None = None,
    days: int | None = None,
    page: int = 1,
    per_page: int = 10,
) -> dict:
    """Return a paginated page of conversations (one row per session in the analytics table)."""
    offset = (page - 1) * per_page

    query = _apply_common_filters(
        select(Conversation).join(Project, Project.id == Conversation.project_id),
        user_id,
        project_id,
        model,
    )
    count_query = _apply_common_filters(
        select(func.count(Conversation.id)).join(Project, Project.id == Conversation.project_id),
        user_id,
        project_id,
        model,
    )

    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=min(days, MAX_STATS_DAYS))
        query = query.where(Conversation.started_at >= cutoff)
        count_query = count_query.where(Conversation.started_at >= cutoff)

    query = query.order_by(Conversation.started_at.desc()).offset(offset).limit(per_page)
    conversations = session.exec(query).all()
    total = session.exec(count_query).one()

    items = []
    for conv in conversations:
        project = session.get(Project, conv.project_id)
        msg_list = json.loads(conv.messages_json)
        duration = int((conv.updated_at - conv.started_at).total_seconds())

        last_question = None
        for msg in reversed(msg_list):
            if msg.get("role") == "user":
                last_question = msg.get("content", "")
                break

        items.append(
            SessionRowOut(
                id=conv.id,
                project_title=project.title if project else "Unbekannt",
                started_at=conv.started_at.isoformat(),
                message_count=len(msg_list),
                duration_seconds=duration,
                last_question=last_question[:100] if last_question else None,
            )
        )

    return {"items": items, "total": total}


def get_timeseries_data(
    session: Session,
    user_id: str,
    project_id: str | None = None,
    model: str | None = None,
    days: int = 30,
    granularity: str = "day",
) -> list[dict]:
    """Return timeseries data (sessions per day/week/month) for the analytics chart."""
    days = min(days, MAX_TIMESERIES_DAYS)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = _apply_common_filters(
        select(ProjectAccess.accessed_at).join(Project, Project.id == ProjectAccess.project_id),
        user_id,
        project_id,
        model,
    ).where(ProjectAccess.accessed_at >= cutoff)
    accesses = session.exec(query).all()

    timeseries: dict[str, int] = {}
    for accessed_at in accesses:
        if granularity == "week":
            key = accessed_at.strftime("%Y-%W")
        elif granularity == "month":
            key = accessed_at.strftime("%Y-%m")
        else:
            key = accessed_at.strftime("%Y-%m-%d")
        timeseries[key] = timeseries.get(key, 0) + 1

    return [{"label": k, "value": v} for k, v in sorted(timeseries.items())]
