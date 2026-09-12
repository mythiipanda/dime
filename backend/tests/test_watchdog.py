"""Watchdog (v2 step 3): stuck turns end honestly, never hang.

Per-call timeouts convert a sleeping tool into a circuit-breaker-fed
error result; the turn wall-clock budget breaks the retrieval loop and
presentation ends with coverage named (never "try a narrower ask").
Hermetic: fabricated tools, no LLM, no network.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.graph as g  # noqa: E402


def _state():
    return {"question": "q", "primary": "p", "model": "m", "round": 0,
            "tool_results": [], "calls_made": [], "history": [],
            "_pending_calls": [{"name": "run_python",
                                "args": {"code": "pass"}}]}


class _SlowTool:
    name = "run_python"

    async def ainvoke(self, args):
        await asyncio.sleep(30)
        return {"tool": "run_python", "ok": True, "rows": []}


def test_tool_call_timeout_returns_error_result(monkeypatch):
    monkeypatch.setattr(g, "TOOL_CALL_TIMEOUT_S", 0.2)
    monkeypatch.setattr(g, "_supervisor_tools", lambda s: [_SlowTool()])

    async def _go(state):
        async for _e in g.actual_tool_node(state):
            pass
        return state

    st = _state()
    t0 = time.time()
    st = asyncio.run(_go(st))
    assert time.time() - t0 < 5, "timeout did not fire"
    res = st["tool_results"][-1]
    assert res["ok"] is False
    assert "timed out" in res["error"]


def test_presentation_watchdog_honest_end():
    async def _go(state):
        out = None
        async for e in g.presentation_agent(state):
            if e.get("type") == "final_answer":
                out = e["data"]["text"]
        return out

    st = {"question": "some deep multi-stat ask", "analysis": "",
          "tool_results": [], "calls_made": [], "history": [],
          "primary": "p", "model": "m", "_watchdog_tripped": True}
    out = asyncio.run(_go(st))
    assert out == g._COMPUTE_FALLBACK
    assert "narrower" not in out and "did not run" not in out


def test_presentation_watchdog_keeps_evidence():
    async def _go(state):
        out = None
        async for e in g.presentation_agent(state):
            if e.get("type") == "final_answer":
                out = e["data"]["text"]
        return out

    st = {"question": "which team leads in total assists?",
          "analysis": "This data covers the 2025-26 season.\nThe "
                      "Atlanta Hawks lead with 2462 total AST.",
          "tool_results": [{"tool": "get_team_leaders", "ok": True,
                            "rows": [{"TEAM": "Atlanta Hawks",
                                      "AST": 2462, "GP": 82,
                                      "PER_GAME": 30.0}],
                            "meta": {"stat_category": "AST",
                                     "leader_line": "Atlanta Hawks lead "
                                     "with 2462 total AST (30.0 per game "
                                     "over 82 games)"}}],
          "calls_made": [], "history": [], "primary": "p", "model": "m",
          "_watchdog_tripped": True}
    out = asyncio.run(_go(st))
    # evidence exists: the honest fallback must NOT override it
    assert "2462" in out
