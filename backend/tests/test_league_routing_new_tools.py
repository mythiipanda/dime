"""League routing for the new warehouse tools.

SSE evidence showed "Who led the league in scoring each season from 2020
to 2025?" calling get_leaders once per season: the league desk tool list
lacked get_historical_leaders, get_zone_deltas, get_wpa_leaders, and
get_rapm_prior, the brief had no IF/THEN lines for them, and the
list-question force paths pushed "who leads" phrasing into text_to_sql
(~30s) before the brief ran. Historical phrasing now guards both force
sites so the task falls through to the brief, exactly like _SHOT_ZONE_RX.

All hermetic: the real _desk_spec, no LLM, no network, no mocks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _LIST_RX  # noqa: E402
from app.subagents import _HISTORICAL_RX, _SHOT_ZONE_RX, _desk_spec  # noqa: E402

NEW_TOOLS = [
    "get_historical_leaders",
    "get_zone_deltas",
    "get_wpa_leaders",
    "get_rapm_prior",
]


def _league_spec(task):
    return _desk_spec("delegate_league", task)


def test_league_spec_includes_new_tools():
    _desk, brief, tool_names, _force = _league_spec(
        "who leads the league in scoring")
    for name in NEW_TOOLS:
        assert name in tool_names
        assert name in brief


def test_each_season_from_to_not_forced():
    q = "Who leads the league in scoring each season from 2020 to 2025?"
    _desk, _brief, _tools, force = _league_spec(q)
    assert force is None
    assert _LIST_RX.search(q)
    assert _HISTORICAL_RX.search(q)
    assert not _SHOT_ZONE_RX.search(q)


def test_every_season_since_not_forced():
    q = "Who leads the league in scoring every season since 2020?"
    _desk, _brief, _tools, force = _league_spec(q)
    assert force is None
    assert _LIST_RX.search(q)
    assert _HISTORICAL_RX.search(q)


def test_top_n_year_by_year_not_forced():
    q = "Top 10 scoring seasons since 2020 year by year"
    _desk, _brief, _tools, force = _league_spec(q)
    assert force is None
    assert _LIST_RX.search(q)
    assert _HISTORICAL_RX.search(q)


def test_all_time_single_season_campaigns_not_forced():
    q = "All-time single-season scoring campaigns year-by-year"
    _desk, brief, _tools, force = _league_spec(q)
    assert force is None
    assert _HISTORICAL_RX.search(q)
    assert "get_historical_leaders" in brief


def test_live_evidence_past_tense_not_forced():
    q = "Who led the league in scoring each season from 2020 to 2025?"
    _desk, _brief, _tools, force = _league_spec(q)
    assert force is None
    assert _HISTORICAL_RX.search(q)


def test_plain_who_leads_forces_fast_leaders_tool():
    q = "who leads the league in scoring"
    _desk, _brief, _tools, force = _league_spec(q)
    assert force is not None
    assert force[0] == "get_leaders"
    assert _LIST_RX.search(q)
    assert not _HISTORICAL_RX.search(q)


def test_list_fastpath_regex_pair_skips_historical():
    q = "Who leads the league in scoring each season from 2020 to 2025?"
    assert _LIST_RX.search(q)
    assert _HISTORICAL_RX.search(q)


def test_list_fastpath_regex_pair_keeps_plain():
    q = "who leads the league in scoring"
    assert _LIST_RX.search(q)
    assert not _HISTORICAL_RX.search(q)
