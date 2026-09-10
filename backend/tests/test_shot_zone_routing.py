"""Shot-zone routing carve-out tests.

SSE verification caught "Which team(s) shoot the most at the rim?"
landing in text_to_sql via the league desk's list-question force regex
(33.6s SQL vs the fast purpose-built tool, whose zone_leaders never
ran). The league brief already says shot-zone/shot-diet/rim-rate tasks
call get_team_shot_zones, but the force regex fired before the LLM
brief ever saw the task. A second hijack lived in graph.py's _LIST_RX
fast-path, which appended "Answer via text_to_sql (you own that tool)."
to the delegate task.

Both force sites now check _SHOT_ZONE_RX first. Shot-zone questions
fall through to the brief (force=None, desk owns the routing);
genuine ad-hoc aggregations still force to text_to_sql.

All hermetic: the real _desk_spec, no LLM, no network, no mocks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _LIST_RX  # noqa: E402
from app.subagents import _SHOT_ZONE_RX, _desk_spec  # noqa: E402


def _league_spec(task):
    return _desk_spec("delegate_league", task)


def test_rim_question_not_forced_to_sql():
    desk, brief, tool_names, force = _league_spec(
        "Which teams shoot the most at the rim?")
    assert desk == "league"
    assert force is None
    assert "get_team_shot_zones" in tool_names
    assert "get_team_shot_zones" in brief


def test_corner_three_rate_not_forced_to_sql():
    _desk, _brief, tool_names, force = _league_spec(
        "which teams lead in corner three rate")
    assert force is None
    assert "get_team_shot_zones" in tool_names


def test_shot_diet_not_forced_to_sql():
    _desk, _brief, tool_names, force = _league_spec(
        "Which teams have the most midrange-heavy shot diet?")
    assert force is None
    assert "get_team_shot_zones" in tool_names


def test_efg_by_zone_not_forced_to_sql():
    _desk, _brief, _tools, force = _league_spec(
        "Which teams have the best eFG by zone this season?")
    assert force is None


def test_where_teams_shoot_from_not_forced_to_sql():
    _desk, _brief, _tools, force = _league_spec(
        "Where do teams shoot from most often?")
    assert force is None


def test_ad_hoc_aggregation_still_forced_to_sql():
    # Back-to-back splits have no purpose-built tool: text_to_sql stays.
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


def test_suffixed_task_strips_suffix_when_forced():
    # The graph.py fast-path suffix must not leak into the SQL question.
    q = ("Which players averaged 25+ points in back-to-backs? "
         "Answer via text_to_sql (you own that tool).")
    _desk, _brief, _tools, force = _league_spec(q)
    assert force[0] == "text_to_sql"
    assert force[1]["question"] == \
        "Which players averaged 25+ points in back-to-backs?"


def test_list_fastpath_regex_pair_skips_shot_zone():
    # Mirrors the _triage_seed guard: _LIST_RX fires on the phrasing but
    # _SHOT_ZONE_RX vetoes the "Answer via text_to_sql" fast-path, so
    # the plain question reaches the desk and the brief routes it.
    q = "Which teams shoot the most at the rim?"
    assert _LIST_RX.search(q)
    assert _SHOT_ZONE_RX.search(q)


def test_list_fastpath_regex_pair_keeps_ad_hoc():
    q = "Which players averaged 25+ points in back-to-backs?"
    assert _LIST_RX.search(q)
    assert not _SHOT_ZONE_RX.search(q)
