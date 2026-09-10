"""Regression: actual_tool_node must never pass a Future to create_task.

asyncio.gather() returns a Future, not a coroutine. Feeding it to
asyncio.create_task() raised "TypeError: a coroutine was expected, got
<_GatheringFuture pending>" and failed every DimeBench task whose planner
called concrete tools directly (compare/brief/chain/trade families).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.graph as graph_mod
from app.graph import DimeState, actual_tool_node


class _StubTool:
    name = "get_compare"

    async def ainvoke(self, args):
        return {"tool": self.name, "ok": True, "rows": {"echo": args}}


def _make_state():
    return DimeState(
        question="q", primary="mistral", model="m", round=0,
        tool_results=[], calls_made=[], history=[],
        analysis="", suggestions=[],
    )


def _drain_node_twice():
    async def _go():
        # Twice in a row on one loop, mirroring the benchmark's sequential
        # run_task loop, to catch loop-reuse regressions too.
        for _ in range(2):
            state = _make_state()
            state["_pending_calls"] = [  # type: ignore[typeddict-unknown-key]
                {"name": "get_compare", "args": {"a": "x", "b": "y"}},
            ]
            events = [e async for e in actual_tool_node(state)]
            assert state["tool_results"], "tool results were not recorded"
            assert state["tool_results"][0].get("ok") is True
            assert "tool_result" in {e.get("type") for e in events}
    asyncio.run(_go())


def test_tool_node_spawns_gather_without_future_leak(monkeypatch):
    monkeypatch.setattr(graph_mod, "_supervisor_tools",
                        lambda state: [_StubTool()])
    _drain_node_twice()
