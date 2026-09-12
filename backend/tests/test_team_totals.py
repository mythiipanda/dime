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


# --- v67: deterministic value patch + scrub widening (v66 live smoke) ---

from app.graph import _scrub_final_text, presentation_agent  # noqa: E402


def _present(question, analysis, tool_results):
    async def _go():
        state = {"question": question, "analysis": analysis,
                 "tool_results": tool_results, "calls_made": [],
                 "history": [], "primary": "p", "model": "m"}
        out = None
        async for e in presentation_agent(state):
            if e.get("type") == "final_answer":
                out = e["data"]["text"]
        return out

    return asyncio.run(_go())


_TT_TR = [{"tool": "get_team_leaders",
           "rows": [{"RANK": 1, "TEAM": "Denver Nuggets", "ABBREV": "DEN",
                     "PTS": 10010, "GP": 82, "PER_GAME": 122.1}],
           "meta": {"stat_category": "PTS", "season": "2025-26",
                    "leader_line": "Denver Nuggets lead with 10010 total "
                                   "PTS (122.1 per game over 82 games)"}}]


def test_team_totals_value_patch_with_stat_token():
    # v66 live failure shape: value dropped, stat token left behind.
    out = _present(
        "which team scored the most total points this season?",
        "This data covers the 2025-26 season.\nBased on warehouse data, "
        "the Denver Nuggets scored the most total points with PTS "
        "(122.1 per game).", list(_TT_TR))
    assert "10010" in out
    assert "with PTS (" not in out
    assert "warehouse" not in out.lower()
    # "Based on warehouse data" opened a sentence -> capitalized fix.
    assert "from the dataset" in out.lower()


def test_team_totals_value_prepend_when_missing():
    out = _present(
        "which team scored the most total points this season?",
        "This data covers the 2025-26 season.\nDenver took the scoring "
        "crown this season at 122.1 per game.", list(_TT_TR))
    assert "Denver Nuggets lead with 10010 total PTS" in out


def test_team_totals_value_untouched_when_present():
    out = _present(
        "which team scored the most total points this season?",
        "This data covers the 2025-26 season.\nThe Denver Nuggets lead "
        "with 10010 total PTS (122.1 per game over 82 games).",
        list(_TT_TR))
    assert out.count("10010") == 1


def test_scrub_nba_api_league_data_collision():
    out = _scrub_final_text("Per the NBA API league data, Denver leads.")
    assert "NBA API the dataset" not in out
    assert "the dataset" in out


def test_scrub_based_on_warehouse_data():
    out = _scrub_final_text("Based on warehouse data, Denver leads. "
                            "That holds, according to the warehouse data.")
    assert "warehouse" not in out.lower()
    assert "From the dataset, Denver leads." in out
