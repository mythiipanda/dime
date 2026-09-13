"""F66 deterministic deep-compare lane.

"Compare the top 3 scoring teams: total points, per-game average, and
how many games each won" escaped every pin, fanned out through
delegate_league, and shipped a NAMELESS table with empty cells and
invented numbers (benchmark f66-deep-compare). v67 lesson: no more
LLM-lane patching - get_team_compare joins the deduped team-totals
board with standings records in one payload, and compose ships
meta.deterministic_answer verbatim.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed, presentation_agent  # noqa: E402
from app.tools import get_team_compare  # noqa: E402


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


def test_deep_compare_pin_fires():
    st = _drain("Compare the top 3 scoring teams: total points, "
                "per-game average, and how many games each won")
    assert "get_team_compare" in _tool_names(st)
    assert "get_team_leaders" not in _tool_names(st)
    tr = st["tool_results"][-1]
    assert tr["tool"] == "get_team_compare"
    rows = tr.get("rows") or []
    assert len(rows) == 3
    assert rows[0]["TEAM"] == "Denver Nuggets"
    assert rows[0]["PTS"] == 10010
    assert rows[0]["RECORD"] == "54-28"


def test_deep_compare_pin_variants():
    for q in ("compare the top 5 rebounding teams by total rebounds "
              "and record",
              "top 3 teams in assists: totals, per game, and wins"):
        st = _drain(q)
        assert "get_team_compare" in _tool_names(st), q


def test_single_stat_totals_stay_on_team_leaders():
    st = _drain("Which team leads in total assists this season?")
    assert "get_team_leaders" in _tool_names(st)
    assert "get_team_compare" not in _tool_names(st)


def test_named_team_compares_untouched():
    st = _drain("Compare the Lakers and Celtics: total points, "
                "per-game, and records")
    assert "get_team_compare" not in _tool_names(st)


def test_tool_joins_records_and_builds_answer():
    out = get_team_compare.invoke({"stat_category": "PTS", "top": 3})
    assert out["ok"] and len(out["rows"]) == 3
    for r in out["rows"]:
        assert r["RECORD"] and r["W"] is not None and r["GP"] == 82
    answer = out["meta"]["deterministic_answer"]
    assert "10010" in answer and "Denver Nuggets" in answer
    assert "54-28" in answer and "122.1" in answer
    for bad in ("not specified", "| |", "with .", "missing"):
        assert bad not in answer


def test_tool_top_clamped_and_stat_fallback():
    out = get_team_compare.invoke({"stat_category": "bogus", "top": 99})
    assert out["ok"]
    assert len(out["rows"]) == 10
    assert out["meta"]["stat_category"] == "PTS"


_COMPARE_TR = [{"tool": "get_team_compare",
                "rows": [{"RANK": 1, "TEAM": "Denver Nuggets",
                          "ABBREV": "DEN", "PTS": 10010, "GP": 82,
                          "PER_GAME": 122.1, "W": 54, "L": 28,
                          "RECORD": "54-28"}],
                "meta": {"stat_category": "PTS", "season": "2025-26",
                         "deterministic_answer":
                         "Denver Nuggets lead with 10010 total PTS "
                         "(122.1 per game over 82 games) and a 54-28 "
                         "record."}}]


def test_deterministic_answer_ships_verbatim():
    # Feed compose a degenerate LLM narrative; the payload-built
    # sentence must ship untouched.
    out = _present(
        "Compare the top 3 scoring teams: total points, per-game "
        "average, and how many games each won",
        "Based on warehouse data, the top teams are | | with . "
        "not specified.", list(_COMPARE_TR))
    assert ("Denver Nuggets lead with 10010 total PTS "
            "(122.1 per game over 82 games) and a 54-28 record.") in out
    assert out.startswith("This data covers the 2025-26 season.")
    for bad in ("not specified", "| |", "with .", "warehouse"):
        assert bad not in out
