"""Prediction fast-path routing tests.

DimeBench caught the supervisor calling get_preview for pre-game
prediction questions ("who wins", "win probability", "projected total")
instead of the purpose-built get_game_prediction. The triage fast-path
added in app/graph.py routes those questions straight to
get_game_prediction on clean single-turn asks.

All hermetic: _triage_seed is driven directly and the real
get_game_prediction runs against the local warehouse (neutral-site
simulation when no meeting is cached). No LLM, no network, no stubs.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph  # noqa: E402
from app.graph import (  # noqa: E402
    DEEP_TOOL_ROUNDS,
    MAX_TOOL_ROUNDS,
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


def test_who_wins_routes_to_game_prediction():
    st = _drain("who wins the Lakers vs Celtics game tonight")
    assert _tool_names(st) == ["get_game_prediction"]
    assert st["calls_made"] == [
        'get_game_prediction:{"a": "Boston Celtics", '
        '"b": "Los Angeles Lakers"}'
    ]
    # Decisive: planner rounds exhausted, supervisor loop skipped.
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)
    assert "get_preview" not in _tool_names(st)


def test_win_probability_phrasing():
    st = _drain("what is the win probability for Lakers vs Celtics")
    assert _tool_names(st) == ["get_game_prediction"]
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_projected_total_phrasing():
    st = _drain("projected total for Lakers vs Celtics tonight")
    assert _tool_names(st) == ["get_game_prediction"]
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_bench_prediction_phrasing():
    st = _drain(
        "Give me the pre-game Monte Carlo estimate for the "
        "Los Angeles Lakers vs the Boston Celtics (2025-26 season): "
        "who is favored, each team's win probability, and the projected "
        "score and total. Use default simulation settings.")
    assert _tool_names(st) == ["get_game_prediction"]
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_abbreviation_teams_resolve():
    st = _drain("LAL vs BOS: who wins tonight?")
    assert _tool_names(st) == ["get_game_prediction"]
    assert st["calls_made"] == [
        'get_game_prediction:{"a": "Boston Celtics", '
        '"b": "Los Angeles Lakers"}'
    ]


def test_fastpath_runs_real_simulation():
    st = _drain("who wins the Lakers vs Celtics game tonight")
    assert len(st["tool_results"]) == 1
    out = st["tool_results"][0]
    assert out["tool"] == "get_game_prediction"
    assert out["ok"] is True
    probs = out["estimate"]["win_prob"]
    assert set(probs) == {"BOS", "LAL"}
    assert all(0.0 < p < 1.0 for p in probs.values())
    assert out["estimate"]["projected_total"] > 0


def test_narrative_preview_not_hijacked():
    st = _drain("preview the Lakers vs Celtics matchup: form, star "
                "matchups, x-factors, why to watch")
    assert "get_game_prediction" not in _tool_names(st)
    assert st["round"] == 0  # left for the normal desk/supervisor flow


def test_live_win_prob_not_hijacked():
    st = _drain("what is the live win probability for Lakers vs Celtics "
                "right now")
    assert "get_game_prediction" not in _tool_names(st)
    assert st["round"] == 0  # desk brief still routes these to get_win_prob


def test_title_question_not_hijacked():
    st = _drain("who wins the championship: Lakers or Celtics")
    assert "get_game_prediction" not in _tool_names(st)
    assert st["round"] == 0  # league desk territory (get_playoff_sim)


def test_history_disables_fastpath():
    st = _drain("who wins the Lakers vs Celtics game tonight",
                history=[{"role": "user", "text": "hi"},
                         {"role": "assistant", "text": "hey"}])
    assert "get_game_prediction" not in _tool_names(st)
    assert st["round"] == 0


def test_single_team_prediction_falls_through():
    st = _drain("who wins the Lakers game tonight")
    assert "get_game_prediction" not in _tool_names(st)
    assert st["round"] == 0
