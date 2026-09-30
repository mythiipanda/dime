
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools._core import (  # noqa: E402
    COVERAGE_END,
    COVERAGE_START,
    InvalidSeasonError,
    clamp_season,
)

BANNED = ("traceback", "Traceback", "silver_", "endpoint", "cache",
          "pipeline", "snag", "failed", "exception", "select ",
          "tool_trace", "desk_retried", "first_error")


def test_clamp_season_bare_year_uses_ending_year():
    assert clamp_season("2014") == "2013-14"
    assert clamp_season("2026") == "2025-26"
    assert clamp_season("2010") == "2009-10"


def test_clamp_season_canonical_passes_through():
    assert clamp_season("2013-14") == "2013-14"
    assert clamp_season("2025-26") == "2025-26"
    assert clamp_season("2009-10") == "2009-10"


def test_clamp_season_out_of_coverage_raises_structured():
    with pytest.raises(InvalidSeasonError) as info:
        clamp_season("1998-99")
    exc = info.value
    assert exc.requested == "1998-99"
    assert exc.coverage_start == COVERAGE_START == "2009-10"
    assert exc.coverage_end == COVERAGE_END == "2025-26"
    assert exc.nearest == "2009-10"
    msg = str(exc)
    assert "1998-99" in msg
    assert "2009-10" in msg
    for token in BANNED:
        assert token not in msg


def test_clamp_season_future_raises_nearest_ceiling():
    with pytest.raises(InvalidSeasonError) as info:
        clamp_season("2027")
    assert info.value.nearest == "2025-26"
    assert "2025-26" in str(info.value)


@pytest.mark.parametrize("bad", ["garbage", "", None, "22025", "2013-15",
                                 "2014/15", "99"])
def test_clamp_season_garbage_raises_without_fallback(bad):
    with pytest.raises(InvalidSeasonError) as info:
        clamp_season(bad)
    assert info.value.nearest is None
    assert info.value.coverage_start == "2009-10"
    assert info.value.coverage_end == "2025-26"


def test_season_interpretation_in_skills_catalog():
    from app.skills import catalog, load_skill

    lines = catalog().strip().splitlines()
    match = [line for line in lines
             if line.startswith("- season_interpretation: ")]
    assert match
    desc = match[0].split(": ", 1)[1]
    assert desc.strip()
    assert len(desc) <= 150
    body = load_skill("season_interpretation")
    assert "2013-14" in body
    assert "ask the user" in body


def _node_state():
    import app.graph as graph_mod

    return graph_mod.DimeState(
        question="q", primary="mistral", model="m", round=0,
        tool_results=[], calls_made=[], history=[],
        analysis="", suggestions=[],
    )


def _run_node(calls):
    import app.graph as graph_mod

    async def _go():
        state = _node_state()
        state["_pending_calls"] = calls  # type: ignore[typeddict-unknown-key]
        events = [e async for e in graph_mod.actual_tool_node(state)]
        return state, events

    return asyncio.run(_go())


def test_tool_node_converts_out_of_coverage_to_honest_copy(monkeypatch):
    import app.graph as graph_mod
    from shared.tools.awards import get_award_race

    monkeypatch.setattr(graph_mod, "_supervisor_tools",
                        lambda state: [get_award_race])
    state, events = _run_node([{
        "name": "get_award_race",
        "args": {"award": "MVP", "season": "1998-99"},
    }])
    result = state["tool_results"][0]
    assert result.get("ok") is False
    assert result.get("season_error") is True
    text = str(result.get("error", ""))
    assert "1998-99" in text
    assert "2009-10" in text
    for token in BANNED:
        assert token not in text
    payloads = [e for e in events if e.get("type") == "tool_result"]
    assert payloads
    blob = str(payloads)
    assert "2009-10" in blob
    for token in ("traceback", "Traceback", "silver_"):
        assert token not in blob


def test_user_safe_error_keeps_season_copy_whole():
    import app.graph as graph_mod

    msg = str(InvalidSeasonError("1998-99", nearest="2009-10"))
    kept = graph_mod._user_safe_tool_error("get_award_race", msg)
    assert kept == msg.rstrip(".")
    assert "1998-99" in kept and "2009-10" in kept


def test_analytics_names_requested_season_and_floor():
    import app.graph as graph_mod

    async def _go():
        state = {"question": "How did Jordan play in the 1998-99 season?",
                 "history": [], "calls_made": [], "ledger": [],
                 "primary": "p", "model": "m",
                 "tool_results": [{
                     "tool": "get_award_race", "ok": False,
                     "error": str(InvalidSeasonError(
                         "1998-99", nearest="2009-10")),
                     "season_error": True}]}
        async for _ in graph_mod.analytics_agent(state):
            pass
        return state.get("analysis", "")

    out = asyncio.run(_go())
    assert "1998-99" in out
    assert "2009-10" in out
    low = out.lower()
    for token in ("traceback", "silver_", "endpoint", "cache", "pipeline",
                  "snag", "failed", "exception"):
        assert token not in low
