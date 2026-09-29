"""Per-turn circuit breaker tests.

The supervisor never gives up on a failing tool: B2 saw text_to_sql fail
x5 across 5 planner rounds (188s turn). _circuit_broken_tools cuts a tool
from the planner's options after 2 straight fails so it moves on.

All hermetic: _supervisor_tools is driven directly with fabricated
tool_results. No LLM, no network.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import (  # noqa: E402
    SUPERVISOR_TOOL_NAMES,
    _supervisor_tools,
)
from app.subagents import _desk_spec  # noqa: E402


def _state(results):
    return {"question": "q", "primary": "primary", "model": "model",
            "round": 0, "tool_results": results, "calls_made": [],
            "history": []}


def _fail(name):
    return {"tool": name, "ok": False, "error": "boom"}


def _ok(name):
    return {"tool": name, "ok": True, "rows": [{"x": 1}]}


def _names(state):
    return [t.name for t in _supervisor_tools(state)]


def test_two_consecutive_failures_cut_tool():
    st = _state([_fail("run_python"), _fail("run_python")])
    names = _names(st)
    assert "run_python" not in names
    for name in SUPERVISOR_TOOL_NAMES:
        if name == "run_python":
            continue
        assert name in names


def test_success_resets_streak():
    st = _state([_fail("run_python"), _ok("run_python"), _fail("run_python")])
    assert "run_python" in _names(st)


def test_single_failure_keeps_tool():
    st = _state([_fail("run_python")])
    assert "run_python" in _names(st)


def test_breaker_does_not_cut_other_tools():
    st = _state([_fail("run_python"), _fail("run_python")])
    assert "delegate_league" in _names(st)


def test_streaks_are_per_tool():
    st = _state([_fail("run_python"), _fail("delegate_league"),
                 _fail("run_python")])
    names = _names(st)
    assert "run_python" not in names
    assert "delegate_league" in names


def test_adhoc_sql_route_stays_open():
    desk, brief, names, force = _desk_spec(
        "delegate_league",
        "which players average the most points "
        "Answer via text_to_sql (you own that tool).")
    assert force[0] == "text_to_sql"
    assert "text_to_sql" in names
