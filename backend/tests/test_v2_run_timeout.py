
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from v2.api.routes import _drain_run  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def test_hung_run_hits_timeout_ceiling():
    async def scenario():
        async def hung():
            await asyncio.sleep(60)
            return "never"

        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(hung())
        started = time.monotonic()
        try:
            await _drain_run(task, queue, timeout_s=0.05, drain_tick_s=0.01)
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - started
            assert elapsed < 5, f"ceiling took {elapsed:.2f}s, expected ~0.05s"
            assert not task.done()
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            return
        raise AssertionError("_drain_run returned for a hung run")

    _run(scenario())


def test_healthy_run_drains_events_and_returns():
    async def scenario():
        async def quick():
            return "done"

        queue: asyncio.Queue = asyncio.Queue()
        await queue.put("e1")
        await queue.put("e2")
        task = asyncio.create_task(quick())
        events = await _drain_run(task, queue, timeout_s=5.0, drain_tick_s=0.01)
        assert events == ["e1", "e2"]
        assert task.result() == "done"

    _run(scenario())


def test_production_default_is_still_the_six_minute_ceiling():
    from shared.config import settings

    assert settings.dime_v2_run_timeout_s == 360.0
