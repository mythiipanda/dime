import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import routes

TOOL_NAMES = (
    "get_season_averages",
    "get_player_intel",
    "delegate_team",
    "delegate_scout",
    "run_python",
    "text_to_sql",
    "resolve_entity",
    "search_nba",
)


def _failed_event(status="fail", error="text_to_sql failed: no such column foo"):
    return {
        "node": "tools",
        "name": "text_to_sql",
        "label": "Warehouse query",
        "status": status,
        "rows": 0,
        "ms": 12,
        "agent": "league",
        "error": error,
        "sql": "SELECT foo FROM silver_bar",
        "summary": "should be dropped",
    }


@pytest.mark.parametrize(
    "event",
    [
        _failed_event(status="fail"),
        _failed_event(status="error"),
        _failed_event(status="failed"),
        _failed_event(status="ok"),
    ],
)
def test_sanitize_projects_failures_to_neutral(event):
    out = routes._sanitize_sse_event("tool_result", dict(event))
    assert out["status"] == "fail"
    assert out["error"] == "Tool failed"
    blob = json.dumps(out, default=str)
    assert "no such column" not in blob
    assert "foo" not in blob.replace("Tool failed", "")
    assert "SELECT" not in blob
    assert "silver_" not in blob
    assert "should be dropped" not in blob


def test_sanitize_keeps_success_rows():
    event = {
        "node": "tools",
        "name": "get_season_averages",
        "label": "Season averages",
        "status": "ok",
        "rows": [{"PLAYER": "LeBron James", "PPG": 25.0}],
        "ms": 12,
        "summary": "LeBron James averaged 25 points.",
        "agent": "scout",
    }
    out = routes._sanitize_sse_event("tool_result", dict(event))
    assert out["status"] == "ok"
    assert out["rows"] == event["rows"]
    assert out["summary"] == event["summary"]


def test_clean_error_strips_operational_detail():
    import app.graph as graph_mod

    raw = "text_to_sql failed: no such column foo"
    cleaned = graph_mod._clean_error_text(raw)
    assert "text_to_sql" not in cleaned
    assert "SELECT" not in cleaned
    user_facing = graph_mod._user_safe_tool_error("text_to_sql", raw)
    assert user_facing == "that data pull did not complete"
    assert "no such column" not in user_facing
    assert "foo" not in user_facing


def test_clean_error_keeps_domain_shortage_language():
    import app.graph as graph_mod

    raw = (
        "No season line on file for 2013-14; season lines cover 2014-15 "
        "through the current season, so this one is outside dataset "
        "coverage."
    )
    assert graph_mod._clean_error_text(raw) == raw.rstrip(".")
    kept = graph_mod._user_safe_tool_error("get_season_averages", raw)
    assert "2013-14" in kept
    assert "2014-15" in kept


def test_scrub_strips_remaining_name_classes():
    import app.graph as graph_mod

    raw = (
        "delegate_team failed. run_python timed out. resolve_entity error. "
        "search_nba disabled. text_to_sql broke."
    )
    cleaned = graph_mod._clean_error_text(raw)
    assert cleaned == "failed. timed out. error. disabled. broke"
    lowered = cleaned.lower()
    for name in TOOL_NAMES:
        assert name not in lowered


def test_scrub_keeps_honest_numbers():
    import app.graph as graph_mod

    raw = "This data covers the 2025-26 season. Denver averages 122.1 points."
    assert graph_mod._scrub_final_text(raw) == raw


def test_evidence_text_name_free_on_failures():
    import app.graph as graph_mod
    from shared.tools._core import InvalidSeasonError

    results = [
        {
            "tool": "get_award_race",
            "ok": False,
            "error": str(InvalidSeasonError("1998-99", nearest="2009-10")),
            "season_error": True,
        },
        {
            "tool": "get_season_averages",
            "ok": False,
            "error": (
                "No season line on file for 2013-14; season lines cover "
                "2014-15 through the current season."
            ),
        },
    ]
    blob = json.dumps(graph_mod._sanitize_evidence(results), default=str)
    assert "1998-99" in blob
    assert "2013-14" in blob
    lowered = blob.lower()
    for name in TOOL_NAMES:
        assert name not in lowered
    assert "tool_trace" not in lowered
    assert "traceback" not in lowered


def test_analyst_system_never_asks_to_name_tools():
    import app.graph as graph_mod

    assert "Never name tools, tables, or query languages." in graph_mod.ANALYST_SYSTEM


def test_empty_evidence_frames_honestly():
    import app.graph as graph_mod

    async def _go():
        state = {
            "question": "How did Jordan play?",
            "history": [],
            "calls_made": [],
            "ledger": [],
            "primary": "p",
            "model": "m",
            "tool_results": [],
        }
        async for _ in graph_mod.analytics_agent(state):
            pass
        return state.get("analysis", "")

    out = asyncio.run(_go())
    assert "No " in out
    assert "data found" in out
    lowered = out.lower()
    for token in ("failed", "error", "traceback", "silver_", "tool_trace"):
        assert token not in lowered
