"""Deterministic player-evaluation lane: tier + profile + value + comps."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph
from app.tools import TOOL_NAMES, get_contract_value, get_player_evaluation


def _drain(question: str):
    async def _go():
        state = {"question": question, "history": [], "tool_results": [],
                 "calls_made": [], "round": 0}
        async for _ in graph._triage_seed(question, "primary", "model", state):
            pass
        return state
    return asyncio.run(_go())


def test_registered():
    assert "get_player_evaluation" in TOOL_NAMES


def test_jaylen_brown_complete_evaluation():
    out = get_player_evaluation.invoke({"player": "Jaylen Brown"})
    assert out["ok"] is True
    rows = out["rows"]
    assert rows["player_id"].isdigit()
    assert rows["tier"] == "star"
    assert rows["profile"]["usage_rank"] == 3
    assert rows["profile"]["pie_rank"] == 25
    assert rows["profile"]["rapm_lite"] == -0.43
    assert len(rows["comps"]) == 5
    assert rows["modeled_value"]["PREDICTED"] > 10_000_000
    det = out["meta"]["deterministic_answer"]
    for text in ("star", "35.1% usage", "57.3% true shooting",
                 "RAPM-lite", "Modeled value", "Devin Booker"):
        assert text in det


def test_contract_value_can_scope_one_player():
    out = get_contract_value.invoke({"player": "Jaylen Brown"})
    assert out["ok"] is True
    assert len(out["rows"]) == 1
    assert out["rows"][0]["PLAYER"] == "Jaylen Brown"


def test_eval_wording_beats_comps_only_fastpath():
    st = _drain("Was Jaylen Brown a good player, what should his value be, "
                "who are his comparable players, and is he a star, "
                "superstar, starter, or role player?")
    names = [c.split(":", 1)[0] for c in st["calls_made"]]
    assert names == ["get_player_evaluation"]
    assert st["tool_results"][0]["rows"]["tier"] == "star"


def test_plain_comps_question_stays_on_comps_lane():
    st = _drain("Who are the closest comparable players to Jaylen Brown?")
    names = [c.split(":", 1)[0] for c in st["calls_made"]]
    assert names == ["get_comps"]
