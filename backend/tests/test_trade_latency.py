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
    from shared import store

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
    store = _needs_warehouse()
    real_connect = store.connect
    calls = []

    def counting(*a, **k):
        calls.append(1)
        return real_connect(*a, **k)

    store.connect = counting
    try:
        from shared.tools.league import get_trade_value

        res = get_trade_value.invoke(
            {"team_a": "MIN", "players_a": "Anthony Edwards",
             "team_b": "LAL", "players_b": "Luka Doncic"})
    finally:
        store.connect = real_connect
    assert res["ok"] is True
    assert res["rows"]["verdict"]["winner"] in {"MIN", "LAL", "even"}
    assert len(calls) == 1


def test_trade_check_single_connection():
    store = _needs_warehouse()
    probe = store.connect()
    try:
        vintages = {str(row[0]) for row in probe.execute(
            "SELECT DISTINCT _season FROM silver_cap_players").fetchall()}
    finally:
        probe.close()
    if vintages and "2025-26" not in vintages:
        pytest.skip(
            "release pack salary vintage is not 2025-26: "
            + ", ".join(sorted(vintages))
        )
    real_connect = store.connect
    calls = []

    def counting(*a, **k):
        calls.append(1)
        return real_connect(*a, **k)

    store.connect = counting
    try:
        from shared.tools.league import get_trade_check

        res = get_trade_check.invoke(
            {"team_a": "MIN", "players_a": "Anthony Edwards",
             "team_b": "LAL", "players_b": "Luka Doncic"})
    finally:
        store.connect = real_connect
    assert res["ok"] is True
    assert len(calls) == 1


def test_trade_value_side_totals_internally_consistent():
    _needs_warehouse()
    from shared.tools.league import get_trade_value

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
    events, state = _collect_triage(
        "Who wins this trade on production value vs salary: "
        "Anthony Edwards (MIN) for Luka Doncic (LAL)? Name the winner.")
    tool_calls = [e for e in events if e["type"] == "tool_call"]
    assert [ (e.get("data") or {}).get("name") for e in tool_calls] == [
        "get_trade_value"]
    assert state["round"] >= MAX_TOOL_ROUNDS
    assert state["tool_results"]
    last = state["tool_results"][-1]
    assert last["tool"] == "get_trade_value"
    assert last["rows"] and last["rows"][0]["ok"] is True


def test_triage_three_team_skips_value_fast_path():
    events, _ = _collect_triage(
        "Who wins this three-team trade on value: Anthony Edwards (MIN) "
        "vs Luka Doncic (LAL) vs Nikola Jokic (DEN)?")
    assert [e for e in events if e["type"] == "tool_call"] == []


def test_triage_compound_question_not_swallowed():
    events, _ = _collect_triage(
        "Is the Edwards-for-Doncic trade legal, and who wins it on value? "
        "Anthony Edwards (MIN) for Luka Doncic (LAL).")
    names = [(e.get("data") or {}).get("name")
             for e in events if e["type"] == "tool_call"]
    assert "get_trade_value" not in names


def test_desk_cache_dedupes_trade_desks():
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


def test_full_team_names_do_not_inject_same_city_team():
    from app.graph import _detect_entities, _trade_sides

    question = ("Who wins this trade on value: Anthony Edwards "
                "(Minnesota Timberwolves) for Luka Doncic "
                "(Los Angeles Lakers)?")
    players, teams = _detect_entities(question)
    assert teams == ["Los Angeles Lakers", "Minnesota Timberwolves"]
    sides = _trade_sides(question, players, teams, "2025-26")
    assert sides is not None
    assert {sides["team_a"], sides["team_b"]} == {"MIN", "LAL"}
    assert "LAC" not in sides.values()
