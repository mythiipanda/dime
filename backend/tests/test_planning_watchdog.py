"""Planning-call watchdog (P1: NVIDIA planning hang, 2026-09-28).

Prod evidence: with model=nvidia forced, the graph hung 120s at
"planning warehouse lookups" with zero tokens and zero errors -- the
45s first-token watchdog only covered the final answer stream, not the
planning LLM calls. Every planning-path LLM call must fail fast with
an honest error instead of hanging silently.

Hermetic: fake clients, no network. Proves the watchdog fires on:
1. invoke_with_fallback (non-streaming planning/tool LLM calls),
   including fallback to the next provider.
2. _stream_planner (supervisor planning stream): hung primary fails
   fast and the next provider's plan is used; all-hung raises an
   honest error fast.
3. _select_skills_intent (runs before the planner stream): a hung
   skills call returns ([], None) fast instead of holding the turn.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shared.providers as prov  # noqa: E402
from app import graph as graph_module  # noqa: E402


class _Chunk:
    def __init__(self, text="", tool_calls=None):
        self.content = text
        self.tool_call_chunks = tool_calls or []


class _HangStreamClient:
    """Accepts the request, never produces a token."""

    def __init__(self, hang_s=3600):
        self.hang_s = hang_s

    def bind_tools(self, tools):
        return self

    async def astream(self, messages, **kwargs):
        await asyncio.sleep(self.hang_s)
        yield _Chunk("never")  # pragma: no cover

    async def ainvoke(self, messages, **kwargs):
        await asyncio.sleep(self.hang_s)
        raise AssertionError("unreachable")  # pragma: no cover


class _OKStreamClient:
    def __init__(self, tool_calls=None):
        self._tool_calls = tool_calls or []

    def bind_tools(self, tools):
        return self

    async def astream(self, messages, **kwargs):
        yield _Chunk("", tool_calls=self._tool_calls)

    async def ainvoke(self, messages, **kwargs):
        class _R:
            content = ""
            tool_calls = self._tool_calls
        return _R()


class _HangAinvokeClient:
    async def ainvoke(self, messages, **kwargs):
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")  # pragma: no cover


class _OKAinvokeClient:
    def __init__(self, text="select 1"):
        self._text = text

    async def ainvoke(self, messages, **kwargs):
        class _R:
            pass
        r = _R()
        r.content = self._text
        return r


class _HangSkillsLLM:
    async def ainvoke(self, msgs):
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")  # pragma: no cover


def _setup_providers(monkeypatch, clients, timeout_s=0.3):
    prov._probe_state.clear()
    monkeypatch.setattr(prov, "fallback_order",
                        lambda primary: list(clients.keys()))
    monkeypatch.setattr(prov, "probe_verdict", lambda name: None)
    monkeypatch.setattr(prov, "get_llm",
                        lambda name, model=None: clients[name]())
    monkeypatch.setattr(prov.settings, "dime_first_token_timeout_s",
                        timeout_s)
    monkeypatch.setattr(graph_module.settings, "dime_first_token_timeout_s",
                        timeout_s)


def _setup_graph(monkeypatch, clients, timeout_s=0.3):
    _setup_providers(monkeypatch, clients, timeout_s)
    monkeypatch.setattr(graph_module, "fallback_order",
                        lambda primary: list(clients.keys()))
    monkeypatch.setattr(graph_module, "get_llm",
                        lambda name, model=None: clients[name]())


def test_invoke_watchdog_fails_fast_and_falls_back(monkeypatch):
    """A hung non-streaming LLM call fails fast and uses the next provider."""
    _setup_providers(monkeypatch,
                     {"p1": _HangAinvokeClient, "p2": _OKAinvokeClient},
                     timeout_s=0.3)
    t0 = time.monotonic()
    out = asyncio.run(prov.invoke_with_fallback("p1", "m", []))
    elapsed = time.monotonic() - t0
    assert elapsed < 5.0, f"took {elapsed:.1f}s -- watchdog did not fire"
    assert out.provider == "p2"
    assert out.content == "select 1"


def test_invoke_watchdog_all_hung_raises_fast(monkeypatch):
    _setup_providers(monkeypatch, {"p1": _HangAinvokeClient},
                     timeout_s=0.3)
    t0 = time.monotonic()
    try:
        asyncio.run(prov.invoke_with_fallback("p1", "m", []))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert time.monotonic() - t0 < 5.0
        assert "all providers failed" in str(exc)


def test_planner_stream_falls_back_on_hang(monkeypatch):
    """Hung planning primary fails fast; the next provider's plan is used."""
    plan_chunks = [{
        "name": "delegate_league",
        "args": '{"task": "standings"}',
        "id": "call_1",
    }]
    expected_calls = [{
        "name": "delegate_league",
        "args": {"task": "standings"},
        "id": "call_1",
    }]
    _setup_graph(monkeypatch,
                 {"p1": _HangStreamClient,
                  "p2": lambda: _OKStreamClient(tool_calls=plan_chunks)},
                 timeout_s=0.3)
    holder: dict = {}

    async def _drain():
        async for _ in graph_module._stream_planner("p1", "m", [], [],
                                                   holder):
            pass

    t0 = time.monotonic()
    asyncio.run(_drain())
    elapsed = time.monotonic() - t0
    assert elapsed < 5.0, f"took {elapsed:.1f}s -- watchdog did not fire"
    assert holder.get("calls") == expected_calls


def test_planner_stream_all_hung_raises_honest_error_fast(monkeypatch):
    _setup_graph(monkeypatch, {"p1": _HangStreamClient}, timeout_s=0.3)
    holder: dict = {}

    async def _drain():
        async for _ in graph_module._stream_planner("p1", "m", [], [],
                                                   holder):
            pass

    t0 = time.monotonic()
    try:
        asyncio.run(_drain())
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert time.monotonic() - t0 < 5.0
        assert "all providers failed" in str(exc)


def test_skills_intent_hang_returns_empty_fast(monkeypatch):
    monkeypatch.setattr(graph_module.settings, "dime_first_token_timeout_s",
                        0.3)
    t0 = time.monotonic()
    out = asyncio.run(graph_module._select_skills_intent(
        "Who leads the league in scoring?", _HangSkillsLLM()))
    assert time.monotonic() - t0 < 5.0
    assert out == ([], None)
