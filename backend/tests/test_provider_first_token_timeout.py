"""First-token timeout on provider streaming (P0: chat hangs in prod).

Hermetic: fake clients, no network. A provider whose astream never yields
(e.g. the hung NIM endpoint seen in prod) must fail fast at the asyncio
level, get recorded as a provider failure, and let the fallback chain move
on -- instead of holding the whole turn hostage.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shared.providers as prov  # noqa: E402


class _Chunk:
    def __init__(self, text):
        self.content = text


class _HangClient:
    """Accepts the request, never produces a token."""

    def __init__(self, hang_s=3600):
        self.hang_s = hang_s

    async def astream(self, messages, **kwargs):
        await asyncio.sleep(self.hang_s)
        yield _Chunk("never")  # pragma: no cover


class _OKClient:
    def __init__(self, text="hello", chunks=1):
        self.text = text
        self.chunks = chunks

    async def astream(self, messages, **kwargs):
        for _ in range(self.chunks):
            yield _Chunk(self.text)


class _EmptyFirstClient:
    """Yields an empty first chunk, then streams text (connection healthy)."""

    async def astream(self, messages, **kwargs):
        yield _Chunk("")
        yield _Chunk("fine")


class _BoomClient:
    async def astream(self, messages, **kwargs):
        raise RuntimeError("quota exhausted")
        yield _Chunk("never")  # pragma: no cover


def _setup(monkeypatch, clients, timeout_s=0.3):
    prov._probe_state.clear()
    monkeypatch.setattr(prov, "fallback_order",
                        lambda primary: list(clients.keys()))
    monkeypatch.setattr(prov, "probe_verdict", lambda name: None)
    monkeypatch.setattr(prov, "get_llm",
                        lambda name, model=None: clients[name]())
    monkeypatch.setattr(prov.settings, "dime_first_token_timeout_s", timeout_s)
    monkeypatch.setattr(prov, "note_provider_failure",
                        lambda name: prov._probe_state.setdefault(
                            name, (False, time.time())))


def test_hanging_provider_fails_fast(monkeypatch):
    _setup(monkeypatch, {"p1": _HangClient}, timeout_s=0.3)
    t0 = time.monotonic()
    try:
        asyncio.run(_drain_text("p1"))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        elapsed = time.monotonic() - t0
        assert elapsed < 5.0, f"took {elapsed:.1f}s -- watchdog did not fire"
        assert "all providers failed" in str(exc)
        assert "no first token" in str(exc)
        assert "p1" in str(exc)
    assert prov.probe_verdict("p1") is False


def test_hanging_provider_falls_back_to_next(monkeypatch):
    _setup(monkeypatch, {"p1": _HangClient, "p2": _OKClient}, timeout_s=0.3)
    chunks = asyncio.run(_drain_text("p1"))
    assert chunks == [{"provider": "p2", "text": "hello"}]


def test_chunks_variant_also_fails_fast(monkeypatch):
    _setup(monkeypatch, {"p1": _HangClient}, timeout_s=0.3)
    t0 = time.monotonic()
    try:
        asyncio.run(_drain_chunks("p1"))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert time.monotonic() - t0 < 5.0
        assert "no first token" in str(exc)


def test_empty_first_chunk_counts_as_progress(monkeypatch):
    """A connection that yields an (empty) chunk is not hung: no timeout."""
    _setup(monkeypatch, {"p1": _EmptyFirstClient}, timeout_s=0.3)
    chunks = asyncio.run(_drain_text("p1"))
    assert chunks == [{"provider": "p1", "text": "fine"}]


def test_healthy_client_streams_normally(monkeypatch):
    _setup(monkeypatch, {"p1": lambda: _OKClient("hi", chunks=3)},
           timeout_s=0.3)
    chunks = asyncio.run(_drain_text("p1"))
    assert [c["text"] for c in chunks] == ["hi"] * 3


def test_immediate_error_still_falls_back(monkeypatch):
    _setup(monkeypatch, {"p1": _BoomClient, "p2": _OKClient}, timeout_s=0.3)
    chunks = asyncio.run(_drain_text("p1"))
    assert chunks == [{"provider": "p2", "text": "hello"}]


async def _drain_text(primary):
    return [x async for x in prov.astream_with_fallback(primary, "m", [])]


async def _drain_chunks(primary):
    return [x async for x in prov.astream_chunks_with_fallback(primary, "m", [])]
