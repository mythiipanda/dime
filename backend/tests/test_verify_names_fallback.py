
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import presentation_agent  # noqa: E402


async def _final(state):
    async for event in presentation_agent(state):
        if event.get("type") == "final_answer":
            return event["data"]["text"]
    raise AssertionError("no final answer")


def _state(question, analysis, results):
    return {"question": question, "analysis": analysis,
            "tool_results": results, "calls_made": [], "history": [],
            "primary": "p", "model": "m"}


def test_stripped_empty_names_sourced_leader():
    state = _state(
        "Who has the highest true shooting percentage this season?",
        "Zed leads at 99.9% true shooting, ahead of 88.8%.",
        [{"tool": "get_leaders", "ok": True,
          "rows": [{"PLAYER": "Zed", "TS_PCT": 64.3, "GP": 72}],
          "meta": {"source": "warehouse", "season": "2024-25"}}])
    answer = asyncio.run(_final(state))
    assert "99.9" not in answer
    assert "88.8" not in answer
    assert "Zed" in answer
    assert "evidence panel" not in answer


def test_stripped_empty_without_rows_states_coverage():
    state = _state("rank them", "Wrong has 99.9 points.",
                   [{"tool": "x", "ok": False, "error": "boom"}])
    answer = asyncio.run(_final(state))
    assert "99.9" not in answer
    assert "evidence panel" not in answer
    assert "covers" in answer


def test_short_analysis_with_rows_names_names():
    state = _state("rank them", "ok",
                   [{"tool": "x", "ok": True,
                     "rows": [{"PLAYER": "Right", "PTS": 10}],
                     "meta": {"source": "warehouse",
                              "season": "2024-25"}}])
    answer = asyncio.run(_final(state))
    assert "Right" in answer
    assert "evidence panel" not in answer
