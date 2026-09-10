"""Turn-scoped dedupe + non-blocking suggestions regressions."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.graph as graph_mod
from app.graph import DimeState, actual_tool_node, presentation_agent


def _make_state(question="q"):
    return DimeState(
        question=question, primary="mistral", model="m", round=0,
        tool_results=[], calls_made=[], history=[],
        analysis="", suggestions=[],
    )


def _replay_names(events):
    out = []
    for e in events:
        if e.get("type") in ("tool_call", "tool_result"):
            name = (e.get("data", {}) or {}).get("name", "")
            if name == "get_advanced":
                out.append(e.get("type"))
    return out


class _DelegateStub:
    name = "delegate_scout"

    async def ainvoke(self, args):
        raise AssertionError("delegate path must use run_desk_streaming")


def test_same_entity_redelegation_reuses_first_result(monkeypatch):
    calls = {"n": 0}

    async def _fake_desk(name, task, primary, model, on_token=None):
        calls["n"] += 1
        return {"tool": name, "ok": True, "rows": [{"p": "x"}],
                "tool_trace": [{"name": "get_advanced", "label": "x",
                                "status": "ok"}]}

    monkeypatch.setattr(graph_mod, "run_desk_streaming", _fake_desk)
    monkeypatch.setattr(graph_mod, "_supervisor_tools",
                        lambda state: [_DelegateStub()])

    async def _go():
        state = _make_state("Anthony Edwards vs Shai Gilgeous-Alexander")
        state["_pending_calls"] = [  # type: ignore[typeddict-unknown-key]
            {"name": "delegate_scout",
             "args": {"task": "Research Anthony Edwards scoring, part one"}},
        ]
        events1 = [e async for e in actual_tool_node(state)]
        state["_pending_calls"] = [  # type: ignore[typeddict-unknown-key]
            {"name": "delegate_scout",
             "args": {"task": "Research more on Anthony Edwards defense"}},
        ]
        events2 = [e async for e in actual_tool_node(state)]
        return state, events1, events2

    state, events1, events2 = asyncio.run(_go())
    assert calls["n"] == 1
    assert len(state["tool_results"]) == 2
    assert state["tool_results"][0].get("ok") is True
    assert state["tool_results"][1].get("ok") is True
    assert "deduped" not in state["tool_results"][0]
    assert state["tool_results"][1].get("deduped") is True
    assert len(_replay_names(events1)) == 2
    assert _replay_names(events2) == []


def test_multi_entity_fanout_still_runs(monkeypatch):
    calls = {"n": 0}

    async def _fake_desk(name, task, primary, model, on_token=None):
        calls["n"] += 1
        return {"tool": name, "ok": True, "rows": [{"t": task}],
                "tool_trace": [{"name": "get_advanced", "label": "x",
                                "status": "ok"}]}

    monkeypatch.setattr(graph_mod, "run_desk_streaming", _fake_desk)
    monkeypatch.setattr(graph_mod, "_supervisor_tools",
                        lambda state: [_DelegateStub()])

    async def _go():
        state = _make_state("Anthony Edwards vs Shai Gilgeous-Alexander")
        state["_pending_calls"] = [  # type: ignore[typeddict-unknown-key]
            {"name": "delegate_scout",
             "args": {"task": "Research Anthony Edwards scoring"}},
            {"name": "delegate_scout",
             "args": {"task": "Research Shai Gilgeous-Alexander scoring"}},
        ]
        events = [e async for e in actual_tool_node(state)]
        return state, events

    state, _ = asyncio.run(_go())
    assert calls["n"] == 2
    assert len(state["tool_results"]) == 2
    assert all("deduped" not in r for r in state["tool_results"])


def test_resolve_entity_cache(monkeypatch):
    stub_holder: dict = {}

    class _ResolveStub:
        name = "resolve_entity"

        async def ainvoke(self, args):
            stub_holder["n"] = stub_holder.get("n", 0) + 1
            return {"tool": "resolve_entity", "ok": True,
                    "rows": [{"q": args.get("query")}]}

    monkeypatch.setattr(graph_mod, "_supervisor_tools",
                        lambda state: [_ResolveStub()])

    async def _go():
        state = _make_state("q")
        state["_pending_calls"] = [  # type: ignore[typeddict-unknown-key]
            {"name": "resolve_entity", "args": {"query": "Anthony Edwards"}},
            {"name": "resolve_entity", "args": {"query": "anthony edwards"}},
            {"name": "resolve_entity", "args": {"query": "Lakers"}},
        ]
        [e async for e in actual_tool_node(state)]
        return state

    state = asyncio.run(_go())
    assert stub_holder.get("n") == 2
    assert len(state["tool_results"]) == 3
    assert "deduped" not in state["tool_results"][0]
    assert state["tool_results"][1].get("deduped") is True
    assert "deduped" not in state["tool_results"][2]


def test_suggestions_non_blocking(monkeypatch):
    class _Resp:
        content = '["Follow up one", "Follow up two", "Follow up three"]'

    class _FakeLLM:
        async def ainvoke(self, messages):
            await asyncio.sleep(2)
            return _Resp()

    monkeypatch.setattr(graph_mod, "get_llm", lambda *a, **k: _FakeLLM())

    async def _go():
        state = _make_state("How good is Anthony Edwards?")
        state["analysis"] = "Some analysis text."
        t0 = time.monotonic()
        events = [e async for e in presentation_agent(state)]
        elapsed = time.monotonic() - t0
        kinds = {e.get("type") for e in events}
        assert "final_answer" in kinds
        assert "suggestions" not in kinds
        items = await graph_mod._finish_suggestions(state)
        return elapsed, items

    elapsed, items = asyncio.run(_go())
    assert elapsed < 1.5, f"presentation_agent blocked: {elapsed:.2f}s"
    assert items == ["Follow up one", "Follow up two", "Follow up three"]


def test_suggestions_fallback_without_llm(monkeypatch):
    monkeypatch.setattr(graph_mod, "get_llm", lambda *a, **k: None)

    async def _go():
        state = _make_state("How good is Anthony Edwards?")
        state["tool_results"] = []
        state["calls_made"] = []
        state["analysis"] = "Some analysis text."
        events = [e async for e in presentation_agent(state)]
        assert "suggestions" not in {e.get("type") for e in events}
        return state, await graph_mod._finish_suggestions(state)

    state, items = asyncio.run(_go())
    assert items == graph_mod._suggest(state["question"], [], [])
