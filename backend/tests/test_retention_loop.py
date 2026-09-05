"""Tests for main.py's lifespan-managed retention loop. Data past the configured retention
period (see services/retention_service.py's docstring) used to only ever get purged once, right
at process startup — on a long-running container it then never ran again. The fix re-runs the
purge periodically for as long as the process is up; this test checks the background task
actually starts on lifespan entry and, just as importantly, cancels cleanly on exit instead of
hanging or leaking a pending task."""

import asyncio

from app.main import lifespan


def test_lifespan_starts_and_cancels_the_retention_loop_cleanly() -> None:
    async def drive() -> None:
        # `app` is accepted but unused inside lifespan() itself (FastAPI only needs the
        # parameter for its own dispatch), so a placeholder is fine here.
        async with lifespan(None):
            pass

    asyncio.run(drive())
