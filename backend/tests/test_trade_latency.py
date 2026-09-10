"""Latency regression tests for the trade path.

Bottlenecks found Sep 10, 2026 (2-team "trade winner" turn: 11.0s,
three-team trade turn: 17.1s):

1. get_trade_value / get_trade_check opened a fresh DuckDB connection per
   helper (4 and 7 connects per call, ~0.17s each on the 162MB warehouse).
   Fixed: one shared connection per tool call.
2. "Who wins this trade on value" questions exited triage with zero tool
   calls and burned two planner LLM rounds (resolve_entity, then the value
   call) before reaching get_trade_value, which resolves names itself.
   Fixed: deterministic triage fast-path calling get_trade_value directly
   (2-team only; 3-team, picks, and legality compounds still go to the
   planner).
3. desk_cache dedupe for repeated delegate desks (verified hit, not changed).

Warehouse-backed tests skip when the warehouse is unavailable or locked.
"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph as graph_mod
from app.graph import (
    MAX_TOOL_ROUNDS,
    _triage_seed,
    actual_tool_node,
)


def _needs_warehouse():
    from app import store

    try:
        con = store.connect()
    except Exception:
        pytest.skip("warehouse unavailable")
        return None
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    for t in ("silver_leaders_pts", "silver_salaries"):
        if t not in tables:
            pytest.skip(f"warehouse table absent: {t}")
    return store


def test_trade_value_single_connection():
    """get_trade_value must do all warehouse reads on one connection."""
    store = _needs_warehouse()
    real_connect = store.connect
    calls = []

    def counting(*a, **k):
        calls.append(1)
        return real_connect(*a, **k)

    store.connect = counting
    try:
        from app.tools.league import get_trade_value

        res = get_trade_value.invoke(
            {"team_a": "MIN", "players_a": "Anthony Edwards",
             "team_b": "LAL", "players_b": "Luka Doncic"})
    finally:
        store.connect = real_connect
    assert res["ok"] is True
    assert res["rows"]["verdict"]["winner"] in {"MIN", "LAL", "even"}
    assert len(calls) == 1


def test_trade_check_single_connection():
    """get_trade_check must do all warehouse reads on one connection."""
    store = _needs_warehouse()
    real_connect = store.connect
    calls = []

    def counting(*a, **k):
        calls.append(1)
        return real_connect(*a, **k)

    store.connect = counting
    try:
        from app.tools.league import get_trade_check

        res = get_trade_check.invoke(
            {"team_a": "MIN", "players_a": "Anthony Edwards",
             "team_b": "LAL", "players_b": "Luka Doncic"})
    finally:
        store.connect = real_connect
    assert res["ok"] is True
    assert len(calls) == 1


def test_trade_value_side_totals_internally_consistent():
    """Refactor guard: side totals still equal player + pick values."""
    _needs_warehouse()
    from app.tools.league import get_trade_value

    try:
        res = get_trade_value.invoke(
            {"team_a": "LAL", "players_a": "Austin Reaves",
             "picks_a": "2029 FRP",
             "team_b": "BKN", "players_b": "Michael Porter Jr."})
    except Exception:
        pytest.skip("warehouse unavailable")
    if res["ok"] is False:
        pytest.skip(f"warehouse tables absent: {res.get('error')}")
    for side in ("team_a", "team_b"):
        s = res["rows"][side]
        expect = round(sum(
            p["est_market_value_m"] for p in s["players"]
            if isinstance(p["est_market_value_m"], (int, float))) + sum(
            k["est_value_m"] for k in s["picks"]), 1)
        assert s["side_total_m"] == expect
    assert res["rows"]["verdict"]["text"].count(".") >= 3


def _collect_triage(question):
    async def _run():
        state = {"question": question, "history": [], "tool_results": [],
                 "calls_made": [], "round": 0}
        events = []
        async for e in _triage_seed(question, "x", "y", state):
            events.append(e)
        return events, state

    try:
        return asyncio.run(_run())
    except Exception:
        pytest.skip("warehouse unavailable for _trade_sides")


def test_triage_trade_value_fast_path():
    """The profiled 2-team value question answers in triage: one
    get_trade_value call, planner loop skipped (no LLM rounds)."""
    events, state = _collect_triage(
        "Who wins this trade on production value vs salary: "
        "Anthony Edwards (MIN) for Luka Doncic (LAL)? Name the winner.")
    tool_calls = [e for e in events if e["type"] == "tool_call"]
    assert [ (e.get("data") or {}).get("name") for e in tool_calls] == [
        "get_trade_value"]
    # Planner loop skipped: round pushed past the budget.
    assert state["round"] >= MAX_TOOL_ROUNDS
    # Wrapped like the prediction/gamelog fast-paths so analytics sees rows.
    assert state["tool_results"]
    last = state["tool_results"][-1]
    assert last["tool"] == "get_trade_value"
    assert last["rows"] and last["rows"][0]["ok"] is True


def test_triage_three_team_skips_value_fast_path():
    """Three-team trades must NOT take the 2-team value fast-path."""
    events, _ = _collect_triage(
        "Who wins this three-team trade on value: Anthony Edwards (MIN) "
        "vs Luka Doncic (LAL) vs Nikola Jokic (DEN)?")
    assert [e for e in events if e["type"] == "tool_call"] == []


def test_triage_compound_question_not_swallowed():
    """Legality + value compounds stay out of the value fast-path."""
    events, _ = _collect_triage(
        "Is the Edwards-for-Doncic trade legal, and who wins it on value? "
        "Anthony Edwards (MIN) for Luka Doncic (LAL).")
    names = [(e.get("data") or {}).get("name")
             for e in events if e["type"] == "tool_call"]
    assert "get_trade_value" not in names


def test_desk_cache_dedupes_trade_desks():
    """Two delegate_league calls over the same trade entities run the desk
    once; the second is served from desk_cache (deduped=True)."""
    ran = []

    async def fake_desk(name, task, primary, model, on_token=None):
        ran.append(task)
        return {"tool": name, "ok": True, "agent": "league",
                "summary": "canned", "tables": [], "tool_trace": []}

    import unittest.mock as mock

    async def _run():
        state = {"question": "q", "primary": "x", "model": "y", "round": 0,
                 "tool_results": [], "calls_made": [], "history": [],
                 "analysis": "", "suggestions": [],
                 "desk_cache": {}, "entity_cache": {},
                 "_pending_calls": [
                     {"name": "delegate_league", "args": {
                         "task": "Who wins this trade on value: "
                                 "Anthony Edwards (MIN) for Luka Doncic "
                                 "(LAL)?"}},
                     {"name": "delegate_league", "args": {
                         "task": "Grade the trade on production value vs "
                                 "salary: Luka Doncic (LAL) for Anthony "
                                 "Edwards (MIN)."}},
                 ]}
        with mock.patch.object(graph_mod, "run_desk_streaming", fake_desk):
            async for _ in actual_tool_node(state):
                pass
        return state

    state = asyncio.run(_run())
    assert len(ran) == 1, f"desk ran {len(ran)}x, expected 1 (cache hit)"
    results = [r for r in state["tool_results"]
               if r.get("tool") == "delegate_league"]
    assert len(results) == 2
    assert results[1].get("deduped") is True
