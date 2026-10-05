
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed  # noqa: E402

HIST = [{"role": "human",
         "text": "What is Brunson averaging in the playoffs?"},
        {"role": "ai",
         "text": "Jalen Brunson averaged 32.6 points per game in "
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
    out = next(r for r in st["tool_results"]
               if r.get("tool") == "get_season_averages")
    assert out.get("ok") is False, \
        "an absent season table must fail, not answer as an empty season"
    assert "silver_player_season" in str(out.get("error", ""))
    assert not (out.get("rows") or []), \
        "season line must be evidence, not a partial log"


def test_plain_season_average_followup_pins():
    st = _drain("What's his season average?", HIST)
    assert "get_season_averages" in _tool_names(st)


def test_playoff_average_stays_off_season_pin():
    st = _drain("Compare that to his playoff average", HIST)
    assert "get_season_averages" not in _tool_names(st)


def test_answer_mention_does_not_dilute_user_subject():
    hist = HIST + [{"role": "ai",
                    "text": "Luka Dončić is at 33.5 this year."}]
    st = _drain("Compare that to his season average", hist)
    assert "get_season_averages" in _tool_names(st)
    assert any("Brunson" in c for c in st["calls_made"])


def test_two_user_named_players_no_pin():
    hist = HIST + [{"role": "human",
                    "text": "And what about Luka Dončić?"},
                   {"role": "ai",
                    "text": "Luka Dončić is at 33.5 this year."}]
    st = _drain("Compare that to his season average", hist)
    assert "get_season_averages" not in _tool_names(st)


def test_no_history_no_pin():
    st = _drain("Compare that to his season average")
    assert "get_season_averages" not in _tool_names(st)
