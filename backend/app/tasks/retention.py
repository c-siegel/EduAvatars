"""
Periodic Data-Retention Purge

Runs the retention purge (see services/retention_service.py) once at startup and then
periodically for as long as the process is up — started and stopped by app/main.py's lifespan.
"""

import asyncio
import logging

import anyio.to_thread
from sqlmodel import Session

from app.db.session import engine
from app.services.retention_service import purge_expired_data

logger = logging.getLogger(__name__)

# How often the data-retention purge re-runs on a live process (see services/retention_service.py).
# A restart isn't the only time it should run — a school deployment can stay up for weeks — but
# retention itself is configured in whole days, so checking a few times a day is timely enough.
RETENTION_CHECK_INTERVAL_SECONDS = 6 * 60 * 60


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
