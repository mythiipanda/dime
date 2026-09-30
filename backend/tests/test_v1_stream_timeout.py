import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import routes
from shared.config import settings


def _final_chunks(chunks):
    return [chunk for chunk in chunks
            if chunk.startswith("event: final_answer")]


def test_hung_run_chat_terminates_with_timeout_answer(monkeypatch):
    async def events(*args, **kwargs):
        yield {"type": "thought_stream",
               "data": {"node": "x", "text": "working"}}
        await asyncio.sleep(30)

    monkeypatch.setattr(routes, "run_chat", events)
    monkeypatch.setattr(settings, "dime_v2_run_timeout_s", 0.3)

    async def collect():
        return [chunk async for chunk in routes._stream("q", None)]

    started = time.monotonic()
    chunks = asyncio.run(collect())
    elapsed = time.monotonic() - started
    finals = _final_chunks(chunks)
    assert len(finals) == 1
    assert "timed out before finishing" in finals[0]
    assert "run_timeout" in finals[0]
    assert elapsed < 10


def test_fast_run_chat_keeps_single_real_answer(monkeypatch):
    async def events(*args, **kwargs):
        yield {"type": "final_answer", "data": {"text": "Lakers went 12-4."}}
        yield {"type": "graph_end", "data": {"ok": True}}

    monkeypatch.setattr(routes, "run_chat", events)
    monkeypatch.setattr(settings, "dime_v2_run_timeout_s", 30)

    async def collect():
        return [chunk async for chunk in routes._stream("q", None)]

    chunks = asyncio.run(collect())
    finals = _final_chunks(chunks)
    assert len(finals) == 1
    assert "Lakers went 12-4." in finals[0]
    assert "timed out" not in finals[0]
