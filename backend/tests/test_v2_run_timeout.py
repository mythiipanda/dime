import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from v2.api.routes import _stream_queue

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
            async for _event in _stream_queue(
                    task, queue, timeout_s=0.05, drain_tick_s=0.01):
                raise AssertionError("_stream_queue yielded for a hung run")
        except TimeoutError:
            elapsed = time.monotonic() - started
            assert elapsed < 5, f"ceiling took {elapsed:.2f}s, expected ~0.05s"
            assert not task.done()
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            return
        raise AssertionError("_stream_queue returned for a hung run")

    _run(scenario())

def test_healthy_run_streams_every_event_and_stops():
    async def scenario():
        async def quick():
            return "done"

        queue: asyncio.Queue = asyncio.Queue()
        await queue.put("e1")
        await queue.put("e2")
        task = asyncio.create_task(quick())
        events = [event async for event in _stream_queue(
            task, queue, timeout_s=5.0, drain_tick_s=0.01)]
        assert events == ["e1", "e2"]
        assert task.result() == "done"

    _run(scenario())

def test_events_reach_the_client_while_the_run_is_still_working():
    async def scenario():
        release = asyncio.Event()

        async def slow():
            await release.wait()
            return "done"

        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(slow())
        await queue.put("e1")
        stream = _stream_queue(task, queue, timeout_s=5.0, drain_tick_s=0.01)

        first = await anext(stream)
        assert first == "e1"
        assert not task.done()

        await queue.put("e2")
        release.set()
        rest = [event async for event in stream]
        assert rest == ["e2"]
        assert task.result() == "done"

    _run(scenario())

def test_production_default_is_still_the_six_minute_ceiling():
    from shared.config import settings

    assert settings.dime_v2_run_timeout_s == 360.0
