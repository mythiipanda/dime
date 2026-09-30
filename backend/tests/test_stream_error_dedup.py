import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import routes


def _error_chunks(chunks):
    return [chunk for chunk in chunks if chunk.startswith("event: error")]


def test_error_then_raise_emits_single_error_frame(monkeypatch):
    async def events(*args, **kwargs):
        yield {"type": "error", "data": {"node": "x", "message": "boom"}}
        raise RuntimeError("boom")

    monkeypatch.setenv("DIME_RUNTIME_V2", "off")
    monkeypatch.setattr(routes, "run_chat", events)

    async def collect():
        return [chunk async for chunk in routes._stream("q", None)]

    chunks = asyncio.run(collect())
    assert len(_error_chunks(chunks)) == 1


def test_raise_only_emits_single_error_frame(monkeypatch):
    async def events(*args, **kwargs):
        raise RuntimeError("boom")
        yield {"type": "unreachable", "data": {}}

    monkeypatch.setenv("DIME_RUNTIME_V2", "off")
    monkeypatch.setattr(routes, "run_chat", events)

    async def collect():
        return [chunk async for chunk in routes._stream("q", None)]

    chunks = asyncio.run(collect())
    assert len(_error_chunks(chunks)) == 1
