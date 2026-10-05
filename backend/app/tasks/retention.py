"""
Deleting Student Data After a Retention Period

Removes saved conversations and page-view logs once they're older than the retention period an
admin configured (SiteSettings.conversation_retention_days). Without this, student chat content
would sit in the database indefinitely. Runs once at startup and then periodically for as long
as the process is up — started and stopped by app/main.py's lifespan.

Why does this matter?
The public chat is used by students who never get an account and can't ask for their own data to
be deleted — they're only identified by an anonymous cookie. A time limit set by the operator is
therefore the only realistic way that data ever goes away, short of the teacher deleting their
whole account.

How to use:
    from app.tasks.retention import purge_expired_data

    purge_expired_data(session)  # no-op if retention is set to "keep forever"
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import anyio.to_thread
from sqlalchemy import delete
from sqlmodel import Session

from app.db.session import engine
from app.features.chat.models import Conversation, ProjectAccess
from app.features.site_settings.service import get_or_create_site_settings

logger = logging.getLogger(__name__)

# How often the data-retention purge re-runs on a live process.
# A restart isn't the only time it should run — a school deployment can stay up for weeks — but
# retention itself is configured in whole days, so checking a few times a day is timely enough.
RETENTION_CHECK_INTERVAL_SECONDS = 6 * 60 * 60


def purge_expired_data(session: Session) -> int:
    """Delete conversations and access logs past the configured retention period; returns rows removed."""
    retention_days = get_or_create_site_settings(session).conversation_retention_days
    # 0 (the default) means "keep forever" — nothing to do, and importantly not "delete everything".
    if retention_days <= 0:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    # updated_at, not started_at: a conversation that's still being added to shouldn't be cut in
    # half mid-lesson just because it began before the cutoff.
    conversations = session.execute(delete(Conversation).where(Conversation.updated_at < cutoff)).rowcount
    accesses = session.execute(delete(ProjectAccess).where(ProjectAccess.accessed_at < cutoff)).rowcount
    session.commit()

    removed = (conversations or 0) + (accesses or 0)
    if removed:
        logger.info("Retention: removed %d rows older than %d days.", removed, retention_days)
    return removed


def run_retention_purge() -> None:
    """Runs one retention purge; never lets a cleanup problem take down the caller."""
    try:
        with Session(engine) as session:
            purge_expired_data(session)
    except Exception:
        logger.exception("Data-retention cleanup failed.")


async def retention_loop() -> None:
    """Re-runs the retention purge periodically for as long as the process stays up.

    Without this, data past the configured retention period only ever got deleted right after
    a restart (see the lifespan startup call in app/main.py) and then never again — for a
    long-running container, that defeats the whole point of a retention period.
    """
    while True:
        await asyncio.sleep(RETENTION_CHECK_INTERVAL_SECONDS)
        # The purge itself is blocking DB work — run it off the event loop, same reasoning as
        # every sync route (see request_thread_pool_size in core/config.py).
        await anyio.to_thread.run_sync(run_retention_purge)
