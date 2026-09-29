
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed  # noqa: E402

OKC_HIST = [
    {"role": "human", "text": "Which team had the best record this season?"},
    {"role": "ai",
     "text": "The Oklahoma City Thunder had the best record at 64-18."},
]
WEMBY_HIST = [
    {"role": "human", "text": "How is Wembanyama playing?"},
    {"role": "ai",
     "text": "Victor Wembanyama is averaging 24 points this season."},
]


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


def test_playoff_carry_pins_playoff_intel():
    st = _drain("How did he do in the playoffs?", WEMBY_HIST)
    assert "get_playoff_intel" in _tool_names(st), _tool_names(st)


def test_playoff_carry_named_player_keeps_own_lane():
    st = _drain("How did Brunson do in the playoffs?", WEMBY_HIST)
    assert st["tool_results"] == [] or all(
        "pin_" not in c for c in _tool_names(st))


def test_playoff_carry_answer_mention_does_not_steal_subject():
    hist = WEMBY_HIST + [{"role": "ai", "text": "Jalen Brunson is at 32.6."}]
    st = _drain("How did he do in the playoffs?", hist)
    assert "get_playoff_intel" in _tool_names(st)
    assert any("Wembanyama" in c for c in st["calls_made"])


def test_playoff_carry_two_user_named_players_no_pin():
    hist = WEMBY_HIST + [
        {"role": "human", "text": "And how is Jalen Brunson doing?"},
        {"role": "ai", "text": "Jalen Brunson is at 32.6."},
    ]
    st = _drain("How did he do in the playoffs?", hist)
    assert "get_playoff_intel" not in _tool_names(st)


def test_playoff_carry_falls_back_to_answer_mentions():
    hist = [
        {"role": "human",
         "text": "Which team had the best record this season?"},
        {"role": "ai", "text": "The Oklahoma City Thunder at 64-18."},
        {"role": "human", "text": "Who was their best player?"},
        {"role": "ai",
         "text": "Shai Gilgeous-Alexander led the Thunder in scoring."},
    ]
    st = _drain("How did he do in the playoffs?", hist)
    assert "get_playoff_intel" in _tool_names(st)
    assert any("Gilgeous-Alexander" in c for c in st["calls_made"])


def test_playoff_carry_no_history_no_pin():
    st = _drain("How did he do in the playoffs?")
    assert "get_playoff_intel" not in _tool_names(st)


def test_best_player_carry_reads_team_scorers():
    st = _drain("Who was their best player?", OKC_HIST)
    assert "pin_team_best_player" in _tool_names(st), _tool_names(st)
    rows = st["tool_results"][-1].get("rows") or []
    assert rows, "pin must return scorer rows"
    assert "Shai Gilgeous-Alexander" in str(rows), rows
    assert all("PPG" in r for r in rows)


def test_best_player_no_team_no_pin():
    st = _drain("Who is the best player in the league?", OKC_HIST)
    assert "pin_team_best_player" not in _tool_names(st)


def test_best_player_named_player_no_pin():
    st = _drain("Is Brunson their best player?", OKC_HIST)
    assert "pin_team_best_player" not in _tool_names(st)


def test_best_player_pin_survives_carried_player():
    hist = [
        {"text": "Which team had the best record this season?"},
        {"text": "The Oklahoma City Thunder had the best record at "
                 "64-18, led by Shai Gilgeous-Alexander."},
    ]
    st = _drain("Who was their best player?", hist)
    assert "pin_team_best_player" in _tool_names(st), _tool_names(st)


def test_best_player_pin_uses_most_recent_team():
    hist = [
        {"text": "Which team had the best record this season?"},
        {"text": "The Oklahoma City Thunder had the best record at "
                 "64-18, ahead of the San Antonio Spurs at 62-20."},
    ]
    st = _drain("Who was their best player?", hist)
    names = _tool_names(st)
    assert "pin_team_best_player" in names, names
    rows = next(r for r in st["tool_results"]
                if r.get("tool") == "pin_team_best_player")["rows"]
    assert all("Wembanyama" not in r.get("PLAYER", "") for r in rows), rows


def test_best_player_pin_carries_authoritative_answer():
    st = _drain("Who was their best player?", OKC_HIST)
    result = next(r for r in st["tool_results"]
                  if r.get("tool") == "pin_team_best_player")
    answer = result["meta"].get("deterministic_answer", "")
    assert "Shai Gilgeous-Alexander" in answer
    assert "points per game" in answer


def test_playoff_carry_carries_authoritative_answer():
    hist = [
        {"role": "human", "text": "Who was their best player?"},
        {"role": "ai", "text": "Shai Gilgeous-Alexander led the Thunder."},
    ]
    st = _drain("How did he do in the playoffs?", hist)
    result = next(r for r in st["tool_results"]
                  if r.get("tool") == "get_playoff_intel")
    assert result["meta"].get("deterministic_answer")


def test_comeback_pin_carries_authoritative_answer():
    st = _drain("What was the biggest comeback win this season?")
    result = next(r for r in st["tool_results"]
                  if r.get("tool") == "get_standings_deep")
    answer = result["meta"].get("deterministic_answer", "")
    assert answer.startswith(
        "Minnesota Timberwolves led this comeback proxy with 17 wins")
    assert "trailing at halftime" in answer
    assert "not a measure of the largest" in answer
