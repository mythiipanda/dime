"""Single-player season-average fast-path (QA F26) and final-text
scrubber (QA F34).

F26: "how many assists per game does Jokic average" fell through to the
planner, which dead-ended in delegate_league -> text_to_sql on a null.
The season line is seeded for every rostered player, so triage answers
straight from the warehouse via get_season_averages.

F34: raw exception text (NameError, Traceback) must never reach the
user-facing narrative; presentation scrubs it to an honest admission.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _scrub_final_text, _triage_seed  # noqa: E402


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


def test_season_avg_fastpath_fires():
    st = _drain("how many assists per game does Jokic average")
    assert "get_season_averages" in _tool_names(st)
    rows = st["tool_results"][-1].get("rows") or []
    assert rows, "fast path must wrap the tool output as rows"
    line = rows[0].get("rows") or [{}]
    assert abs(float(line[0].get("APG", 0)) - 10.7) < 0.2


def test_season_avg_fastpath_allows_history():
    st = _drain("how many assists per game does Jokic average",
                history=[{"role": "user", "text": "hi"},
                         {"role": "assistant", "text": "hey"}])
    assert "get_season_averages" in _tool_names(st)


def test_career_phrasing_stays_with_planner():
    st = _drain("What are Jokic's career averages?")
    assert "get_season_averages" not in _tool_names(st)


def test_scrub_strips_exception_text():
    raw = ("No Luka Doncic data found; name '_admap_LAL' is not defined. "
           "Shai leads the cast.")
    out = _scrub_final_text(raw)
    assert "_admap_LAL" not in out
    assert "not defined" not in out
    assert "Shai leads the cast." in out


def test_scrub_keeps_clean_text():
    clean = "Curry averages 26.6 points per game on 63.7% true shooting."
    assert _scrub_final_text(clean) == clean
