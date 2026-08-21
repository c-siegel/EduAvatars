"""
Deleting Student Data After a Retention Period

Removes saved conversations and page-view logs once they're older than the retention period an
admin configured (SiteSettings.conversation_retention_days). Without this, student chat content
would sit in the database indefinitely.

Why does this matter?
The public chat is used by students who never get an account and can't ask for their own data to
be deleted — they're only identified by an anonymous cookie. A time limit set by the operator is
therefore the only realistic way that data ever goes away, short of the teacher deleting their
whole account.

How to use:
    from app.services.retention_service import purge_expired_data

    purge_expired_data(session)  # no-op if retention is set to "keep forever"
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlmodel import Session

from app.models.conversation import Conversation
from app.models.project_access import ProjectAccess
from app.services.site_settings_service import get_or_create_site_settings

logger = logging.getLogger(__name__)


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
