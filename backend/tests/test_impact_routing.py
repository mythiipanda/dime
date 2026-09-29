
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import (  # noqa: E402
    DEEP_TOOL_ROUNDS,
    MAX_TOOL_ROUNDS,
    _flatten_tables,
    _triage_seed,
)
from app.subagents import _desk_spec, SCOUT_BRIEF  # noqa: E402


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


def test_estimate_impact_phrasing():
    st = _drain("Estimate Victor Wembanyama's impact per 100 possessions "
                "this season. What's the number?")
    assert _tool_names(st) == ["get_impact_estimate"]
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)
    assert "delegate_scout" not in _tool_names(st)


def test_how_good_has_rookie_been():
    st = _drain("How good has Cooper Flagg been this season?")
    assert _tool_names(st) == ["get_impact_estimate"]
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_bench_estimated_per_100_template():
    st = _drain("How good has Victor Wembanyama been this season? "
                "Give me his estimated per-100 impact.")
    assert _tool_names(st) == ["get_impact_estimate"]
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_bench_on_court_impact_template_with_team_abbrev():
    st = _drain("What is Victor Wembanyama's (SAS) estimated on-court "
                "impact this season, per 100 possessions?")
    assert _tool_names(st) == ["get_impact_estimate"]
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_fastpath_runs_real_estimator():
    st = _drain("Estimate Victor Wembanyama's impact per 100 possessions "
                "this season.")
    assert len(st["tool_results"]) == 1
    entry = st["tool_results"][0]
    inner = entry["rows"][0]
    assert inner["tool"] == "get_impact_estimate"
    assert inner["ok"] is True
    assert inner["is_estimate"] is True
    assert isinstance(inner["estimate_per_100"], (int, float))
    assert "statistical estimate" in inner["disclaimer"]


def _has_rows(rows):
    if isinstance(rows, list):
        return len(rows) > 0
    if isinstance(rows, dict):
        return any(_has_rows(v) for v in rows.values())
    return bool(rows)


def test_fastpath_result_passes_analytics_evidence_gate():
    st = _drain("Estimate Victor Wembanyama's impact per 100 possessions "
                "this season.")
    entry = st["tool_results"][0]
    rows = entry.get("rows")
    assert isinstance(rows, list) and rows
    assert rows[0]["ok"] is True
    evidenced = [
        r for r in _flatten_tables(st["tool_results"])
        if isinstance(r, dict) and _has_rows(r.get("rows"))
        and r.get("tool", "") not in ("resolve_entity", "search_nba")
    ]
    assert len(evidenced) == 1


def test_raptor_history_not_hijacked():
    st = _drain("What is LeBron James's RAPTOR history and career arc?")
    assert "get_impact_estimate" not in _tool_names(st)
    assert "get_raptor_history" in _tool_names(st)


def test_career_impact_phrasing_stays_with_raptor():
    st = _drain("Estimate LeBron James's career impact")
    assert "get_impact_estimate" not in _tool_names(st)
    assert "get_raptor_history" in _tool_names(st)


def test_greatest_season_not_hijacked():
    st = _drain("What was LeBron James's greatest season by RAPTOR?")
    assert "get_impact_estimate" not in _tool_names(st)
    assert "get_raptor_history" in _tool_names(st)


def test_compare_impact_not_hijacked():
    st = _drain("Compare Victor Wembanyama's and Cooper Flagg's impact "
                "this season")
    assert "get_impact_estimate" not in _tool_names(st)
    assert st["round"] == 0


def test_history_disables_fastpath():
    st = _drain("Estimate Victor Wembanyama's impact per 100 possessions "
                "this season",
                history=[{"role": "user", "text": "hi"},
                         {"role": "assistant", "text": "hey"}])
    assert "get_impact_estimate" not in _tool_names(st)
    assert st["round"] == 0


def test_non_impact_estimate_not_hijacked():
    st = _drain("Estimate Victor Wembanyama's points tonight")
    assert "get_impact_estimate" not in _tool_names(st)
    assert st["round"] == 0


def test_scout_desk_owns_tool_and_brief_rule():
    _desk, brief, tool_names, _force = _desk_spec(
        "delegate_scout", "How good has Cooper Flagg been?")
    assert brief == SCOUT_BRIEF
    assert "get_impact_estimate" in tool_names
    assert "get_impact_estimate" in SCOUT_BRIEF
