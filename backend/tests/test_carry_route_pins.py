"""F63/F67 carry-route pins.

F63 (6:22 PM QA, 0/3): "How did he do in the playoffs?" names nobody,
so player-level lanes never fired and the planner settled for TEAM
tables (injuries, team game logs) and dead-ended honestly. One carried
player + a playoff/Finals ask pins that player's playoff game log.

F67 (6:22 PM QA): "Who was their best player?" resolved "their" to
team-scoring totals and gave up, though the named-team control works.
One resolved team + a best-player ask reads the team's top scorers
from the leaders table.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed  # noqa: E402

# Roles match the production chat_history shape ('human'/'ai').
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
    # Player named in the question: the carry pin must NOT fire.
    st = _drain("How did Brunson do in the playoffs?", WEMBY_HIST)
    assert st["tool_results"] == [] or all(
        "pin_" not in c for c in _tool_names(st))


def test_playoff_carry_answer_mention_does_not_steal_subject():
    # F64: an ANSWER that happens to name a second player must not
    # break the one-carried-player gate - the user-turn subject
    # (Wembanyama) wins and the pin fires for him.
    hist = WEMBY_HIST + [{"role": "ai", "text": "Jalen Brunson is at 32.6."}]
    st = _drain("How did he do in the playoffs?", hist)
    assert "get_playoff_intel" in _tool_names(st)
    assert any("Wembanyama" in c for c in st["calls_made"])


def test_playoff_carry_two_user_named_players_no_pin():
    # Genuine ambiguity: the USER's own turns name two players, so
    # "he" has no single referent and the pin must not fire.
    hist = WEMBY_HIST + [
        {"role": "human", "text": "And how is Jalen Brunson doing?"},
        {"role": "ai", "text": "Jalen Brunson is at 32.6."},
    ]
    st = _drain("How did he do in the playoffs?", hist)
    assert "get_playoff_intel" not in _tool_names(st)


def test_playoff_carry_falls_back_to_answer_mentions():
    # F67 chain (battery run8/run12 flake): asks named nobody ("best
    # record?" / "their best player?"), so "he" must resolve from the
    # answer that named the player.
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
    # Battery run 2 flake (local, 8:53 PM): T1's standings answer named
    # Shai, the carry seed pulled him into found_p, and the pin's
    # "not found_p" clause silently handed the turn to the planner.
    # The question still names nobody, so the carried player is context,
    # not the ask - the pin must fire.
    hist = [
        {"text": "Which team had the best record this season?"},
        {"text": "The Oklahoma City Thunder had the best record at "
                 "64-18, led by Shai Gilgeous-Alexander."},
    ]
    st = _drain("Who was their best player?", hist)
    assert "pin_team_best_player" in _tool_names(st), _tool_names(st)


def test_best_player_pin_uses_most_recent_team():
    # Battery run 2 flake (local, 9:00 PM): T1's answer named the
    # runner-up Spurs too, so the "exactly one carried team" gate
    # failed and the planner compared SGA vs Wembanyama instead of
    # answering about OKC. "Their" is the most recent turn's subject.
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
