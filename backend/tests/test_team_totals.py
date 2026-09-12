"""Team-total counting-stat route (Tony's live find, 11:54 AM).

"Which team leads in total assists this season?" dead-ended honestly
(15.6s, league desk: "team totals not explicitly reported"). The data
was one aggregation away: player game logs summed by team. The pin
routes team-total phrasings to get_team_leaders; player phrasings keep
their existing routes.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed  # noqa: E402
from app.tools import get_team_leaders  # noqa: E402


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


def test_team_totals_pin_fires():
    st = _drain("Which team leads in total assists this season?")
    assert "get_team_leaders" in _tool_names(st)
    assert "get_leaders" not in _tool_names(st)
    rows = st["tool_results"][-1].get("rows") or []
    assert rows and rows[0]["TEAM"] == "Atlanta Hawks"
    assert rows[0]["AST"] == 2462


def test_team_totals_pin_variants():
    for q in ("which team has the most rebounds",
              "team with the most points this year",
              "best team in total steals"):
        st = _drain(q)
        assert "get_team_leaders" in _tool_names(st), q


def test_player_leader_phrasings_untouched():
    st = _drain("who leads the league in assists")
    assert "get_team_leaders" not in _tool_names(st)
    st = _drain("which player has the most assists this season")
    assert "get_team_leaders" not in _tool_names(st)


def test_tool_all_stats_sane():
    for stat, leader in (("AST", "Atlanta Hawks"), ("PTS", "Denver Nuggets"),
                         ("REB", "Houston Rockets"), ("STL", "Detroit Pistons"),
                         ("BLK", "Detroit Pistons")):
        out = get_team_leaders.invoke({"stat_category": stat})
        assert out["ok"] and len(out["rows"]) == 30, stat
        assert out["rows"][0]["TEAM"] == leader, stat
        assert all(r["GP"] == 82 for r in out["rows"]), stat


def test_tool_hou_not_double_counted():
    # Warehouse seed bug: HOU's 77 games appeared twice (partial nba_api
    # rows beside full bbref rows, different Game_IDs and abbrev style).
    # True bbref-only total: 9449.
    out = get_team_leaders.invoke({"stat_category": "PTS"})
    hou = next(r for r in out["rows"] if r["TEAM"] == "Houston Rockets")
    assert hou["PTS"] == 9449
    assert hou["GP"] == 82


def test_leader_line_carries_total():
    out = get_team_leaders.invoke({"stat_category": "PTS"})
    line = out["meta"]["leader_line"]
    assert "10010" in line and "Denver Nuggets" in line and "122.1" in line


def test_league_summary_scrub_no_data_collision():
    from app.graph import _scrub_final_text
    out = _scrub_final_text(
        "Data provided by the league summary and split records.")
    assert "the data " not in out
    assert "the dataset" in out
