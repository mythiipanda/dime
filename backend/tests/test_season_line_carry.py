"""F64: cross-turn "compare that to his season average" must answer
from the full season line, not a partial game-log window (live 5:17 PM
repro: Brunson "28 PPG across 13 complete games" shipped as his season
average while the 64-game season line exists). The player arrives by
pronoun carry, so the direct-name season-avg pin never fires.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed  # noqa: E402

HIST = [{"text": "What is Brunson averaging in the playoffs?"},
        {"text": "Jalen Brunson averaged 32.6 points per game in "
                 "the Finals."}]


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


def test_compare_that_to_season_average_pins():
    st = _drain("Compare that to his season average", HIST)
    assert "get_season_averages" in _tool_names(st)
    rows = st["tool_results"][-1].get("rows") or []
    assert rows and "Jalen Brunson" in str(rows), \
        "season line must be evidence, not a partial log"
    import json as _json
    row = rows[0]["rows"][0]
    gp = row.get("GP") or row.get("G") or row.get("games")
    assert gp is None or int(gp) >= 60, \
        f"season line shows {gp} games - a partial window is not the season"


def test_plain_season_average_followup_pins():
    st = _drain("What's his season average?", HIST)
    assert "get_season_averages" in _tool_names(st)


def test_playoff_average_stays_off_season_pin():
    st = _drain("Compare that to his playoff average", HIST)
    assert "get_season_averages" not in _tool_names(st)


def test_two_carried_players_no_pin():
    hist = HIST + [{"text": "Luka Dončić is at 33.5 this year."}]
    st = _drain("Compare that to his season average", hist)
    assert "get_season_averages" not in _tool_names(st)


def test_no_history_no_pin():
    st = _drain("Compare that to his season average")
    assert "get_season_averages" not in _tool_names(st)
