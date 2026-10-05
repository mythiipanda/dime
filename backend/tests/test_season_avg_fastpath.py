
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


def test_season_avg_fastpath_reports_the_absent_table():
    st = _drain("how many assists per game does Jokic average")
    assert "get_season_averages" in _tool_names(st)
    out = next(r for r in st["tool_results"]
               if r.get("tool") == "get_season_averages")
    assert out.get("ok") is False
    assert "silver_player_season" in str(out.get("error", ""))
    assert not (out.get("rows") or []), (
        "a failed warehouse read must not be wrapped as empty evidence")


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


def test_named_playoff_average_does_not_use_regular_season_line():
    st = _drain("How many points per game did Luka average in the playoffs this year?")
    names = _tool_names(st)
    assert "get_playoff_intel" in names
    assert "get_season_averages" not in names
    assert "inactive for all 10" in str(st["tool_results"])
