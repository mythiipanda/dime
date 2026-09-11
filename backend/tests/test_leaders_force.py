"""Single-stat leaders routing carve-out tests.

Live evidence caught "Who leads the league in assists?" landing in
text_to_sql via the league desk's list-question force regex (30s+ SQL
vs the purpose-built get_leaders, whose totals and per-game rows never
ran). The league brief already says one-stat-category tasks call
get_leaders, but the force regex fired before the LLM brief ever saw
the task.

The delegate_league force block now checks single-stat leaders
phrasings first and forces get_leaders with the extracted category.
Everything else keeps forcing text_to_sql exactly as today. Shot-zone
and historical guards still veto first.

All hermetic: the real _desk_spec, no LLM, no network, no mocks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.subagents import _desk_spec, _leaders_category  # noqa: E402


def _league_spec(task):
    return _desk_spec("delegate_league", task)


def test_leads_league_in_assists_forces_get_leaders():
    _desk, _brief, tool_names, force = _league_spec(
        "Who leads the league in assists?")
    assert force is not None
    assert force[0] == "get_leaders"
    assert force[1] == {"stat_category": "AST"}
    assert "get_leaders" in tool_names


def test_most_points_per_game_forces_get_leaders():
    _desk, _brief, _tools, force = _league_spec(
        "Which player averages the most points per game?")
    assert force is not None
    assert force[0] == "get_leaders"
    assert force[1] == {"stat_category": "PTS"}


def test_scoring_title_forces_get_leaders_pts():
    _desk, _brief, _tools, force = _league_spec(
        "Who wins the scoring title?")
    assert force is not None
    assert force[0] == "get_leaders"
    assert force[1] == {"stat_category": "PTS"}


def test_leaders_in_blocks_forces_get_leaders():
    _desk, _brief, _tools, force = _league_spec(
        "Who are the leaders in blocks?")
    assert force is not None
    assert force[0] == "get_leaders"
    assert force[1] == {"stat_category": "BLK"}


def test_ad_hoc_aggregation_still_forced_to_sql():
    q = "Which players averaged 25+ points in back-to-backs?"
    _desk, _brief, _tools, force = _league_spec(q)
    assert force is not None
    assert force[0] == "text_to_sql"
    assert force[1]["question"] == q


def test_top_n_list_still_forced_to_sql():
    q = "top 10 teams by net rating this season"
    _desk, _brief, _tools, force = _league_spec(q)
    assert force is not None
    assert force[0] == "text_to_sql"


def test_at_least_list_still_forced_to_sql():
    q = "Which players average at least 25 points?"
    _desk, _brief, _tools, force = _league_spec(q)
    assert force is not None
    assert force[0] == "text_to_sql"
    assert force[1]["question"] == q


def test_suffixed_leaders_task_forces_get_leaders():
    q = ("Who leads the league in assists? "
         "Answer via text_to_sql (you own that tool).")
    _desk, _brief, _tools, force = _league_spec(q)
    assert force is not None
    assert force[0] == "get_leaders"
    assert force[1] == {"stat_category": "AST"}


def test_historical_leaders_not_hijacked():
    _desk, _brief, _tools, force = _league_spec(
        "Who are the all-time leaders in assists?")
    assert force is None or force[0] != "get_leaders"


def test_extract_category_aliases():
    assert _leaders_category("Who leads the league in dimes?") == "AST"
    assert _leaders_category("Who leads the league in boards?") == "REB"
    assert _leaders_category("Who are the leaders in steals?") == "STL"
    assert _leaders_category("Who leads the league in rebounds?") == "REB"
    assert _leaders_category("Who averages the most threes per game?") == "FG3M"


def test_extract_scoring_title_always_pts():
    assert _leaders_category("Who wins the scoring title?") == "PTS"


def test_extract_returns_none_without_stat():
    assert _leaders_category("Who are the leaders in the East?") is None


def test_extract_returns_none_for_non_leaders():
    assert _leaders_category(
        "Which players averaged 25+ points in back-to-backs?") is None
    assert _leaders_category(
        "top 10 teams by net rating this season") is None
