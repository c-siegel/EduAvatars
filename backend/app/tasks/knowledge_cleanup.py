"""
Finishing Deletes in the Knowledge Service

When a teacher deletes a document, a knowledge base or their account while the knowledge service
(rag/) is unreachable, the backend rows go immediately but the indexed text in that service can't
— the delete is queued as a RagPendingDeletion instead (see features/knowledge/service.py). This
loop sends the queued deletes until the service confirms them, so derived text never outlives
its document. Only runs when Settings.rag_enabled.

How to use:
    task = asyncio.create_task(knowledge_cleanup_loop())   # started by app/main.py's lifespan
"""

import asyncio
import logging

import anyio.to_thread
from sqlmodel import Session

from app.db.session import engine
from app.features.evaluation.service import mark_interrupted
from app.features.knowledge.service import retry_pending_deletions

logger = logging.getLogger(__name__)

# Short: a queued delete means a teacher expects something to be gone, and a retry is cheap.
KNOWLEDGE_CLEANUP_INTERVAL_SECONDS = 5 * 60


def run_knowledge_cleanup() -> None:
    """One round of queued deletes; never lets a cleanup problem take down the caller."""
    try:
        with Session(engine) as session:
            done = retry_pending_deletions(session)
        if done:
            logger.info("Knowledge cleanup: sent %d queued deletions.", done)
    except Exception:
        logger.exception("Knowledge cleanup failed.")


async def knowledge_cleanup_loop() -> None:
    while True:
        await anyio.to_thread.run_sync(run_knowledge_cleanup)
        await asyncio.sleep(KNOWLEDGE_CLEANUP_INTERVAL_SECONDS)


def mark_interrupted_evaluation_runs() -> None:
    """At startup: evaluation runs that were in progress when the backend stopped end as
    "interrupted" — their worker thread is gone. Never lets a problem here block startup."""
    try:
        with Session(engine) as session:
            count = mark_interrupted(session)
        if count:
            logger.info("Marked %d evaluation run(s) as interrupted.", count)
    except Exception:
        logger.exception("Marking interrupted evaluation runs failed.")
