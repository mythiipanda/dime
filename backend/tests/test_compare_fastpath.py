"""Two-player compare fast-path routing plus force-rows desk skip.

Profiled cost: 4 planner LLM rounds (10.3s) on deterministic two-player
compare turns, plus a duplicate text_to_sql run on forced league paths
(~3s). The triage fast-path in app/graph.py answers get_compare plus one
scout desk per player straight from the warehouse; _run_desk in
app/subagents.py skips its tool-call rounds when the force tool already
returned rows.

All hermetic: _triage_seed is driven directly with stubbed delegate
desks, get_compare runs against the local warehouse, and the _run_desk
checks use fake tools with no LLM.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph as graph_mod  # noqa: E402
from app import subagents as subagents_mod  # noqa: E402
from app.graph import (  # noqa: E402
    DEEP_TOOL_ROUNDS,
    MAX_TOOL_ROUNDS,
    _triage_seed,
)

EDWARDS = "Anthony Edwards"
LUKA = "Luka Don\u010di\u0107"
DURANT = "Kevin Durant"

Q2 = f"{EDWARDS} vs {LUKA} scoring: who is better this season?"


async def _fake_delegate(name, task, primary, model, holder,
                         node="data_retrieval"):
    holder["result"] = {
        "tool": name, "ok": True, "agent": "scout",
        "summary": "canned",
        "tables": [{"tool": "get_advanced", "rows": [{"x": 1}]}],
        "tool_trace": [],
    }
    if False:
        yield {}


def _drain(question, history=None):
    async def _go():
        state = {"question": question, "history": history or [],
                 "tool_results": [], "calls_made": [], "round": 0}
        async for _e in _triage_seed(question, "primary", "model", state):
            pass
        return state

    return asyncio.run(_go())


def _tool_names(state):
    return [c.split(":")[0] for c in state["calls_made"]]


def _compare_args(state):
    for key in state["calls_made"]:
        name, _, argstr = key.partition(":")
        if name == "get_compare":
            return json.loads(argstr)
    raise AssertionError("get_compare not called")


def test_fastpath_fires_on_two_player_compare(monkeypatch):
    monkeypatch.setattr(graph_mod, "_run_delegate_live", _fake_delegate)
    st = _drain(Q2)
    assert _tool_names(st) == ["get_compare", "delegate_scout",
                               "delegate_scout"]
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_fastpath_compare_args_are_deterministic(monkeypatch):
    monkeypatch.setattr(graph_mod, "_run_delegate_live", _fake_delegate)
    st = _drain(Q2)
    args = _compare_args(st)
    assert args["season"] == "2025-26"
    assert {args["a"], args["b"]} == {EDWARDS, LUKA}


def test_fastpath_compare_output_matches_slow_path(monkeypatch):
    """Same get_compare args run directly give the same rows the fast
    path stored, so the speedup changes no numbers."""
    monkeypatch.setattr(graph_mod, "_run_delegate_live", _fake_delegate)
    st = _drain(Q2)
    args = _compare_args(st)
    from app.tools import player as pm

    try:
        direct = asyncio.run(pm.get_compare.ainvoke(dict(args)))
    except Exception as exc:
        pytest.skip(f"warehouse unavailable: {exc}")
    assert direct["ok"] is True
    assert st["tool_results"][0] == direct


def test_no_fire_on_one_player(monkeypatch):
    monkeypatch.setattr(graph_mod, "_run_delegate_live", _fake_delegate)
    st = _drain(f"How is {EDWARDS} scoring this season?")
    assert "get_compare" not in _tool_names(st)
    assert st["round"] == 0


def test_no_fire_on_three_players(monkeypatch):
    monkeypatch.setattr(graph_mod, "_run_delegate_live", _fake_delegate)
    st = _drain(f"{EDWARDS} vs {LUKA} vs {DURANT}: "
                f"compare scoring this season?")
    assert "get_compare" not in _tool_names(st)
    assert st["round"] == 0


def test_impact_compare_stays_with_planner(monkeypatch):
    monkeypatch.setattr(graph_mod, "_run_delegate_live", _fake_delegate)
    st = _drain("Compare Victor Wembanyama's and Cooper Flagg's impact "
                "this season")
    assert "get_compare" not in _tool_names(st)
    assert st["round"] == 0


def test_history_disables_compare_fastpath(monkeypatch):
    monkeypatch.setattr(graph_mod, "_run_delegate_live", _fake_delegate)
    st = _drain(Q2, history=[{"role": "user", "text": "hi"},
                             {"role": "assistant", "text": "hey"}])
    assert "get_compare" not in _tool_names(st)
    assert st["round"] == 0


class _FakeTool:
    def __init__(self, name, out):
        self.name = name
        self._out = out

    async def ainvoke(self, args):
        return dict(self._out)


def _patch_desk(monkeypatch, force_out, tooled_calls):
    monkeypatch.setattr(subagents_mod, "get_llm",
                        lambda *a, **k: object())

    async def _count_tooled(*a, **k):
        tooled_calls["n"] += 1
        return ("", [])

    async def _canned_text(*a, **k):
        return "canned summary"

    monkeypatch.setattr(subagents_mod, "_stream_tooled", _count_tooled)
    monkeypatch.setattr(subagents_mod, "_stream_text", _canned_text)
    import app.tools as tools_mod

    fake = _FakeTool("text_to_sql", force_out)
    monkeypatch.setattr(tools_mod, "v1_tools", [fake])


def test_force_rows_skip_tool_call_rounds(monkeypatch):
    """Force tool returned rows: no tool-call LLM rounds, straight to
    the summary call."""
    tooled_calls = {"n": 0}
    _patch_desk(monkeypatch,
                {"tool": "text_to_sql", "ok": True,
                 "rows": [{"PTS": 30}], "sql": "SELECT 1"},
                tooled_calls)
    out = asyncio.run(subagents_mod._run_desk(
        "league", "brief", "which players average at least 30",
        "x", "y", ["text_to_sql"],
        force_tool=("text_to_sql", {"question": "q"})))
    assert tooled_calls["n"] == 0
    assert out["ok"] is True
    assert out["summary"] == "canned summary"
    assert [t["name"] for t in out["tool_trace"]] == ["text_to_sql"]


def test_force_empty_still_uses_tool_rounds(monkeypatch):
    """Force tool with no rows: the desk still runs its tool-call
    rounds instead of skipping."""
    tooled_calls = {"n": 0}
    _patch_desk(monkeypatch,
                {"tool": "text_to_sql", "ok": True, "rows": []},
                tooled_calls)
    out = asyncio.run(subagents_mod._run_desk(
        "league", "brief", "which players average at least 30",
        "x", "y", ["text_to_sql"],
        force_tool=("text_to_sql", {"question": "q"})))
    assert tooled_calls["n"] >= 1
    assert out["ok"] is False
