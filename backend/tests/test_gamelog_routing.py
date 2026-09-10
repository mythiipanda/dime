"""Game-log fast-path routing tests.

Demo bug: the planner free-formed a game-log question into text_to_sql,
hit "unknown table or column" on silver_player_gamelogs, and streamed
the red error row before recovering. The triage fast-path in app/graph.py
routes clean single-turn single-player game-log asks straight to
search_game_logs instead.

All hermetic: _triage_seed is driven directly and the real
search_game_logs runs against the local warehouse. No LLM, no network.
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
    _gamelog_args,
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


def _gamelog_args_of(state):
    for c in state["calls_made"]:
        name, _, payload = c.partition(":")
        if name == "search_game_logs":
            return json.loads(payload)
    return None


def test_40_point_games_routes_to_search_game_logs():
    st = _drain("Show me Anthony Edwards' 40-point games this season")
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args["player"] == "Anthony Edwards"
    assert args["min_points"] == 40
    assert len(_tool_names(st)) == 1
    # Decisive hit: planner rounds exhausted.
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_triple_double_phrasing_sets_flag():
    st = _drain("How many triple-doubles does Luka Doncic have this season?")
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args["player"] == "Luka Dončić"
    assert args.get("triple_double") is True
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_double_double_phrasing_sets_flag():
    st = _drain("Show me Nikola Jokic's double-doubles this month")
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args.get("double_double") is True
    assert "triple_double" not in args


def test_no_clear_player_does_not_fire():
    st = _drain("who had the most 50-point games this season?")
    assert "search_game_logs" not in _tool_names(st)
    # Falls through: no triage claims, planner fallback owns it.
    assert st["round"] == 0


def test_multi_player_does_not_fire():
    st = _drain("who had more 40-point games, LeBron James or Jayson Tatum?")
    assert "search_game_logs" not in _tool_names(st)


def test_averages_phrasing_does_not_fire():
    st = _drain("what does Shai Gilgeous-Alexander average in points "
                "this season")
    assert "search_game_logs" not in _tool_names(st)


def test_opponent_arg_mapping():
    q = "Show me Jayson Tatum's 30-point games vs the Lakers this season"
    args = _gamelog_args(q, "Jayson Tatum", ["Los Angeles Lakers"])
    assert args["opponent"] == "Los Angeles Lakers"
    assert args["min_points"] == 30


def test_month_and_home_arg_mapping():
    q = "LeBron James' triple-doubles at home in March"
    args = _gamelog_args(q, "LeBron James", [])
    assert args.get("triple_double") is True
    assert args.get("home_away") == "home"
    assert args.get("month") == "march"


def _has_rows(rows):
    if isinstance(rows, list):
        return len(rows) > 0
    if isinstance(rows, dict):
        return any(_has_rows(v) for v in rows.values())
    return bool(rows)


def test_fastpath_result_passes_analytics_evidence_gate():
    st = _drain("Show me Anthony Edwards' 40-point games this season")
    evidenced = [
        r for r in _flatten_tables(st["tool_results"])
        if isinstance(r, dict) and _has_rows(r.get("rows"))
        and r.get("tool", "") not in ("resolve_entity", "search_nba")
    ]
    assert len(evidenced) >= 1
