
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed  # noqa: E402

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


def test_correction_opener_recognized_as_followup():
    hist = [{"role": "human", "text": "best defensive players?"}]
    st = _drain("no i mean best defensive players in the league", hist)
    prior = _drain("best defensive players?", [])
    assert st.get("carry_note") or _tool_names(st) == _tool_names(prior)


def test_correction_opener_league_ask_skips_player_carry():
    st = _drain("actually best defensive players in the league",
                WEMBY_HIST)
    note = st.get("carry_note") or {}
    assert not any("Wembanyama" in p for p in note.get("players", [])), note


def test_correction_opener_still_carries_player_for_fragment():
    st = _drain("actually, what about last season?", WEMBY_HIST)
    note = st.get("carry_note") or {}
    assert any("Wembanyama" in p for p in note.get("players", [])), note


def test_correction_opener_with_own_entities_no_carry():
    st = _drain("actually, how is Jalen Brunson doing?", WEMBY_HIST)
    assert not st.get("carry_note"), st.get("carry_note")


def test_correction_opener_without_history_no_carry():
    st = _drain("no i mean best defensive players in the league")
    assert not st.get("carry_note"), st.get("carry_note")
