"""Matchup-splits fast-path routing tests.

B2: "Give me matchup splits for Lakers vs Celtics" looped 5 planner
rounds retrying a failing tool (188s turn). The triage fast-path added
in app/graph.py routes clean single-turn two-team splits asks straight
to get_team_splits (one call per team).

All hermetic: _triage_seed is driven directly and the real
get_team_splits runs against the local warehouse. No LLM, no network.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph  # noqa: E402
from app.graph import (  # noqa: E402
    DEEP_TOOL_ROUNDS,
    MAX_TOOL_ROUNDS,
    _flatten_tables,
    _triage_seed,
)


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


def _splits_teams(state):
    teams = []
    for c in state["calls_made"]:
        name, _, payload = c.partition(":")
        if name == "get_team_splits":
            teams.append(json.loads(payload)["team"])
    return teams


def test_matchup_splits_routes_to_team_splits():
    st = _drain("Give me matchup splits for Lakers vs Celtics this season.")
    assert sorted(_splits_teams(st)) == ["Boston Celtics", "Los Angeles Lakers"]
    assert len(_tool_names(st)) == 2
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_short_phrasing_routes():
    st = _drain("Lakers vs Celtics matchup splits")
    assert sorted(_splits_teams(st)) == ["Boston Celtics", "Los Angeles Lakers"]
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def _has_rows(rows):
    if isinstance(rows, list):
        return len(rows) > 0
    if isinstance(rows, dict):
        return any(_has_rows(v) for v in rows.values())
    return bool(rows)


def test_fastpath_result_passes_analytics_evidence_gate():
    st = _drain("Give me matchup splits for Lakers vs Celtics this season.")
    evidenced = [
        r for r in _flatten_tables(st["tool_results"])
        if isinstance(r, dict) and _has_rows(r.get("rows"))
        and r.get("tool", "") not in ("resolve_entity", "search_nba")
    ]
    assert len(evidenced) >= 1


def test_prediction_phrasing_not_hijacked():
    st = _drain("who wins the Lakers vs Celtics game tonight")
    assert "get_team_splits" not in _tool_names(st)


def test_narrative_preview_not_hijacked():
    st = _drain("preview the Lakers vs Celtics matchup: form, star "
                "matchups, x-factors, why to watch")
    assert "get_team_splits" not in _tool_names(st)
    assert st["round"] == 0


def test_live_splits_not_hijacked():
    st = _drain("Lakers vs Celtics live in-game splits")
    assert "get_team_splits" not in _tool_names(st)
    assert st["round"] == 0


def test_adhoc_list_still_routes_to_league_desk():
    st = _drain("which players lead the league in scoring")
    assert "get_team_splits" not in _tool_names(st)
    assert "delegate_league" in _tool_names(st)
