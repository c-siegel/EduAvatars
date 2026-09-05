"""
Analytics Queries

The actual database queries behind the analytics routes (app/api/analytics.py): aggregate
stats, a paginated session list, a timeseries for charts, and the per-conversation CSV export —
each scoped to a user's own projects and optionally filtered by project/model/time period.

How to use:
    from app.services.analytics_service import get_stats

    stats = get_stats(session, user_id, days=7)
"""

import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, func, select

from app.models.conversation import Conversation
from app.models.project import Project
from app.models.project_access import ProjectAccess
from app.models.schemas.analytics import AnalyticsStatsOut, ConversationDetailOut, SessionRowOut
from app.models.schemas.chat import ChatHistoryEntry

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


def get_conversation_detail(session: Session, user_id: str, conversation_id: str) -> ConversationDetailOut | None:
    """Full message-by-message transcript of one saved conversation — None if it doesn't exist
    or doesn't belong to one of user_id's own projects (the session-list table only ever shows a
    teacher their own projects' sessions, so this route needs the same check)."""
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        return None
    project = session.get(Project, conversation.project_id)
    if project is None or project.user_id != user_id:
        return None
    messages = json.loads(conversation.messages_json)
    return ConversationDetailOut(
        id=conversation.id,
        project_title=project.title,
        visitor_name=conversation.visitor_name,
        started_at=conversation.started_at.isoformat(),
        messages=[ChatHistoryEntry(role=m["role"], content=m["content"]) for m in messages],
    )


def get_conversations_for_export(
    session: Session, user_id: str, conversation_ids: list[str]
) -> list[tuple[Conversation, Project]]:
    """Saved conversations (with their project) from `conversation_ids` that actually belong to
    one of user_id's own projects — same ownership check as get_conversation_detail, but as a
    single bulk query for the CSV/ZIP export. Any id that doesn't exist or belongs to someone
    else is silently dropped rather than erroring out the whole download."""
    if not conversation_ids:
        return []
    rows = session.exec(
        select(Conversation, Project)
        .join(Project, Project.id == Conversation.project_id)
        .where(Conversation.id.in_(conversation_ids), Project.user_id == user_id)
    ).all()
    return list(rows)


def delete_conversations(session: Session, user_id: str, conversation_ids: list[str]) -> int:
    """Permanently delete the given saved conversations, scoped to user_id's own projects (same
    ownership check as get_conversations_for_export) — returns how many were actually deleted.
    Ids that don't exist or belong to someone else are silently skipped rather than erroring,
    same reasoning as the export: a stale selection shouldn't block the rest of it."""
    rows = get_conversations_for_export(session, user_id, conversation_ids)
    for conversation, _project in rows:
        session.delete(conversation)
    session.commit()
    return len(rows)


def _slugify(value: str) -> str:
    """ASCII-only filename fragment — German umlauts spelled out instead of stripped, everything
    else collapsed to hyphens so the result is always safe as a filename and an HTTP header."""
    for umlaut, replacement in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
        value = value.replace(umlaut, replacement).replace(umlaut.upper(), replacement.capitalize())
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return value or "gespraech"


def conversation_export_filename(conversation: Conversation, project: Project) -> str:
    """Filename for one conversation's exported CSV, used both for a standalone download and as
    a ZIP entry name when several conversations are exported at once."""
    date_part = conversation.started_at.strftime("%Y%m%d-%H%M")
    who = conversation.visitor_name or conversation.id[:8]
    return f"{_slugify(project.title)}_{date_part}_{_slugify(who)}.csv"


# Cell-leading characters a spreadsheet app (Excel, Google Sheets) reads as "this cell is a
# formula" rather than plain text — the classic CSV/formula-injection set (OWASP), plus a
# leading tab/CR which some parsers treat the same way.
_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: str) -> str:
    """Neutralize CSV/formula injection in an exported cell.

    visitor_name and message content in build_conversation_csv below come straight from an
    anonymous chat visitor with no format restriction — a name or message starting with e.g.
    '=HYPERLINK("http://evil","x")' becomes a live, clickable formula the moment a teacher opens
    the exported CSV/ZIP in Excel or Sheets. Prefixing with a single quote is the standard fix:
    spreadsheet apps then show the cell as plain text and drop the leading quote themselves.
    """
    if value and value[0] in _CSV_FORMULA_TRIGGERS:
        return "'" + value
    return value


def build_conversation_csv(conversation: Conversation, project: Project) -> str:
    """Render one saved conversation as a CSV: a short metadata header (project, LLM model,
    visitor, start time), then one row per message with a timestamp column plus one column per
    speaker (Avatar/Schüler:in) — each row fills only the column of whichever side sent that
    message, so the two columns read top-to-bottom as each side's messages in order.

    Messages saved before per-message timestamps existed (see
    app/models/schemas/chat.py::ChatHistoryEntry) leave the "Zeitpunkt" cell blank for that row.
    """
    messages = json.loads(conversation.messages_json)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Projekt", _csv_safe(project.title)])
    writer.writerow(["LLM-Modell", _csv_safe(project.llm_model or "")])
    writer.writerow(["Name/ID", _csv_safe(conversation.visitor_name or "")])
    writer.writerow(["Gestartet", conversation.started_at.isoformat()])
    writer.writerow([])
    writer.writerow(["Zeitpunkt", "Avatar", "Schüler:in"])
    for message in messages:
        timestamp = message.get("timestamp") or ""
        content = _csv_safe(message.get("content", ""))
        if message.get("role") == "assistant":
            writer.writerow([timestamp, content, ""])
        else:
            writer.writerow([timestamp, "", content])
    return buffer.getvalue()


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

    # Selects Project.title alongside Conversation directly, instead of a separate session.get()
    # per row below — the join is already here for the WHERE filters, so this is the same query,
    # not an extra one, and it scales with the page instead of a full N+1 if per_page ever grows.
    query = _apply_common_filters(
        select(Conversation, Project.title).join(Project, Project.id == Conversation.project_id),
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
    rows = session.exec(query).all()
    total = session.exec(count_query).one()

    items = []
    for conv, project_title in rows:
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
                project_title=project_title or "Unbekannt",
                started_at=conv.started_at.isoformat(),
                message_count=len(msg_list),
                duration_seconds=duration,
                last_question=last_question[:100] if last_question else None,
                visitor_name=conv.visitor_name,
            )
        )

    return {"items": items, "total": total}


def get_session_ids(
    session: Session,
    user_id: str,
    project_id: str | None = None,
    model: str | None = None,
    days: int | None = None,
) -> list[str]:
    """Every conversation id matching the given filters, ignoring pagination — powers the
    analytics table's "select all" button, which needs to select matches beyond the currently
    loaded page (see get_sessions_paginated for the same filters applied to a page)."""
    query = _apply_common_filters(
        select(Conversation.id).join(Project, Project.id == Conversation.project_id),
        user_id,
        project_id,
        model,
    )
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=min(days, MAX_STATS_DAYS))
        query = query.where(Conversation.started_at >= cutoff)
    return list(session.exec(query.order_by(Conversation.started_at.desc())))


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
