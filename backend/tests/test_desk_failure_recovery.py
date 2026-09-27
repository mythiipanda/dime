"""Desk-failure recovery: a failed team desk must not surface the canned
"I could not find that in the dataset" fallback.

Regression for the "boston celtics stats" prod incident (2026-09-26):
the team desk timed out and the turn collapsed into the generic dataset
fallback, which reads as hardcoded. Expected behavior now:
1. a delegate_* desk that fails is retried once with a simpler task,
2. if it still fails, presentation names the desk and the error instead
   of the canned fallback.

Hermetic: fabricated desk, no LLM, no network.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.graph as g  # noqa: E402

CANNED = "I could not find that in the dataset"


def _final_text(state):
    out = None

    async def _go():
        nonlocal out
        async for e in g.presentation_agent(state):
            if e.get("type") == "final_answer":
                out = e["data"]["text"]

    asyncio.run(_go())
    return out


def test_team_desk_timeout_no_canned_fallback():
    state = {
        "question": "boston celtics stats",
        "analysis": "",
        "tool_results": [
            {"tool": "delegate_team", "ok": False,
             "error": "timed out after 120s",
             "desk_retried": True,
             "first_error": "timed out after 120s"},
        ],
        "calls_made": [], "history": [],
        "primary": "p", "model": "m",
    }
    text = _final_text(state)
    assert CANNED not in text, f"canned fallback leaked: {text!r}"
    assert "team desk" in text
    assert "timed out" in text


def test_team_desk_error_no_canned_fallback():
    state = {
        "question": "boston celtics stats",
        "analysis": "",
        "tool_results": [
            {"tool": "delegate_team", "ok": False,
             "error": "provider 500 from NIM"},
        ],
        "calls_made": [], "history": [],
        "primary": "p", "model": "m",
    }
    text = _final_text(state)
    assert CANNED not in text, f"canned fallback leaked: {text!r}"
    assert "team desk" in text


class _DelegateStub:
    name = "delegate_team"

    async def ainvoke(self, args):
        raise AssertionError("delegate desks run via run_desk_streaming")


def test_desk_retries_once_with_simpler_task(monkeypatch):
    calls = []

    async def _fake_desk(name, task, primary, model, on_token=None):
        calls.append((name, task))
        return {"tool": name, "ok": False, "error": "boom"}

    monkeypatch.setattr(g, "run_desk_streaming", _fake_desk)
    monkeypatch.setattr(g, "_supervisor_tools", lambda s: [_DelegateStub()])
    monkeypatch.setattr(g, "DESK_CALL_TIMEOUT_S", 5.0)

    async def _go(state):
        async for _e in g.actual_tool_node(state):
            pass
        return state

    state = {"question": "boston celtics stats", "primary": "p", "model": "m",
             "round": 0, "tool_results": [], "calls_made": [], "history": [],
             "_pending_calls": [{"name": "delegate_team",
                                "args": {"task": "get celtics team stats"}}]}
    state = asyncio.run(_go(state))
    assert len(calls) == 2, f"expected 1 retry, got {len(calls)} attempts"
    assert "simplest" in calls[1][1] or "Retry" in calls[1][1]
    res = state["tool_results"][-1]
    assert res["ok"] is False
    assert res.get("desk_retried") is True
    assert res.get("first_error") == "boom"


def test_desk_retry_success_uses_second_result(monkeypatch):
    attempts = []

    async def _fake_desk(name, task, primary, model, on_token=None):
        attempts.append(task)
        if len(attempts) == 1:
            return {"tool": name, "ok": False, "error": "boom"}
        return {"tool": name, "ok": True, "rows": [{"TEAM": "Celtics"}]}

    monkeypatch.setattr(g, "run_desk_streaming", _fake_desk)
    monkeypatch.setattr(g, "_supervisor_tools", lambda s: [_DelegateStub()])
    monkeypatch.setattr(g, "DESK_CALL_TIMEOUT_S", 5.0)

    async def _go(state):
        async for _e in g.actual_tool_node(state):
            pass
        return state

    state = {"question": "boston celtics stats", "primary": "p", "model": "m",
             "round": 0, "tool_results": [], "calls_made": [], "history": [],
             "_pending_calls": [{"name": "delegate_team",
                                "args": {"task": "get celtics team stats"}}]}
    state = asyncio.run(_go(state))
    assert len(attempts) == 2
    res = state["tool_results"][-1]
    assert res.get("ok") is True
    assert res["rows"] == [{"TEAM": "Celtics"}]
