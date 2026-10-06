from __future__ import annotations

from pathlib import Path

import pytest

from v2.contracts import Plan, PlanNode, RunMode, TaskSpec
from v2.runtime import FakeCapability, PlanExecutor

@pytest.fixture
def anyio_backend():
    return "asyncio"

def _task(mode: RunMode) -> TaskSpec:
    return TaskSpec(goal="answer", mode=mode, deliverable="text")

def _node(node_id: str, capability: str, **overrides) -> PlanNode:
    fields = {
        "id": node_id,
        "description": node_id,
        "capability_hints": [capability],
    }
    fields.update(overrides)
    return PlanNode(**fields)

def _v2_dir() -> Path:
    return Path(__file__).resolve().parents[2]

@pytest.mark.anyio
async def test_lookup_mode_plan_calling_web_search_is_refused_naming_all_three() -> None:
    calls: list[str] = []

    class Probe(FakeCapability):
        async def execute(self, node, task, evidence):
            calls.append(node.id)
            return await super().execute(node, task, evidence)

    executor = PlanExecutor({"web_search": Probe("web_search", [{"title": "t"}])})
    plan = Plan(nodes=[_node(
        "discover", "web_search", arguments={"query": "current role"})])
    with pytest.raises(ValueError, match="web_search"):
        await executor.execute(_task(RunMode.QUICK), plan)
    try:
        await executor.execute(_task(RunMode.QUICK), plan)
    except ValueError as exc:
        message = str(exc)
    assert "web_search" in message
    assert "quick" in message
    assert "lookup" in message
    assert calls == []

@pytest.mark.anyio
async def test_lookup_mode_plan_calling_web_fetch_is_refused() -> None:
    executor = PlanExecutor({"web_fetch": FakeCapability("web_fetch", {})})
    plan = Plan(nodes=[_node("extract", "web_fetch", arguments={"result_rank": 1})])
    with pytest.raises(ValueError, match="web_fetch"):
        await executor.execute(_task(RunMode.QUICK), plan)
    try:
        await executor.execute(_task(RunMode.QUICK), plan)
    except ValueError as exc:
        message = str(exc)
    assert "web_fetch" in message
    assert "quick" in message
    assert "lookup" in message

@pytest.mark.anyio
async def test_comparison_in_full_mode_passes() -> None:
    executor = PlanExecutor({
        "player_comparison": FakeCapability("player_comparison", {"edge": "a"}),
    })
    result = await executor.execute(
        _task(RunMode.PROJECT), Plan(nodes=[_node("pair", "player_comparison")]))
    assert result.plan.nodes[0].status.value == "complete"
    assert result.evidence[0].capability == "player_comparison"

def test_profiles_derive_from_registry_and_new_capability_denied_by_default(
        monkeypatch) -> None:
    from v2.adapters.capabilities import CAPABILITIES
    from v2.runtime.policy import (
        allowed_capabilities_for_task_mode,
        capability_universe,
        refuse_unprofiled_capability,
    )

    universe = set(capability_universe())
    assert set(CAPABILITIES) < universe
    assert {"web_search", "web_fetch"} <= universe
    for mode in (RunMode.QUICK, RunMode.DEEP_DIVE, RunMode.PROJECT):
        assert set(allowed_capabilities_for_task_mode(mode)) <= universe
    assert set(allowed_capabilities_for_task_mode(RunMode.PROJECT)) == universe
    assert "web_search" not in allowed_capabilities_for_task_mode(RunMode.QUICK)
    assert "player_comparison" in allowed_capabilities_for_task_mode(
        RunMode.PROJECT)
    assert len(allowed_capabilities_for_task_mode(RunMode.QUICK)) < len(
        allowed_capabilities_for_task_mode(RunMode.PROJECT))
    monkeypatch.setitem(CAPABILITIES, "future_tool", CAPABILITIES["standings"])
    with pytest.raises(ValueError, match="future_tool"):
        allowed_capabilities_for_task_mode(RunMode.PROJECT)
    with pytest.raises(ValueError, match="future_tool"):
        refuse_unprofiled_capability(RunMode.QUICK, "node", "future_tool")

@pytest.mark.anyio
async def test_deny_wins_over_planner_hints_and_requirement_coverage() -> None:
    task = TaskSpec(
        goal="answer", mode=RunMode.QUICK, deliverable="text",
        requirements=[{
            "id": "external", "description": "current context",
            "capability_options": ["web_search"],
        }],
    )
    plan = Plan(nodes=[_node(
        "discover", "web_search",
        arguments={"query": "current role"},
        covers_requirement_ids=["external"],
    )])
    executor = PlanExecutor({"web_search": FakeCapability("web_search", [])})
    with pytest.raises(ValueError, match="web_search"):
        await executor.execute(task, plan)

def test_no_prompt_text_changed_to_achieve_this() -> None:
    forbidden = (
        "allowlist",
        "mode profile",
        "profile 'lookup'",
        'profile "lookup"',
        "refuse_unprofiled",
        "MODE_PROFILES",
    )
    prompts = sorted((_v2_dir() / "prompts").glob("*.md"))
    assert prompts
    for prompt in prompts:
        text = prompt.read_text()
        for token in forbidden:
            assert token not in text, f"{prompt.name} contains {token!r}"

def test_policy_derives_profiles_without_question_text() -> None:
    source = (_v2_dir() / "runtime" / "policy.py").read_text()
    for token in (
        "task.goal",
        "subquestion",
        "question",
        "casefold",
        "import re",
        "match(",
        "search(",
    ):
        assert token not in source, f"policy.py routes on {token!r}"
