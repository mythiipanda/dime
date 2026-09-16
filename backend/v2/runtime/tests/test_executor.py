from __future__ import annotations

import asyncio

import pytest
from v2.contracts import Plan, PlanNode, PlanStatus, RunMode, TaskSpec
from v2.runtime import FakeCapability, PlanExecutor

@pytest.fixture
def anyio_backend():
    return "asyncio"



def node(
    node_id: str, *, parents: list[str] | None = None, attempts: int = 1
) -> PlanNode:
    return PlanNode(
        id=node_id,
        description=node_id,
        depends_on=parents or [],
        capability_hints=["fake"],
        max_attempts=attempts,
    )


@pytest.mark.anyio
async def test_executes_dag_and_preserves_lineage() -> None:
    plan = Plan(nodes=[node("a"), node("b"), node("c", parents=["a", "b"])])
    result = await PlanExecutor({"fake": FakeCapability("fake", {"ok": True})}).execute(
        TaskSpec(goal="answer", mode=RunMode.QUICK, deliverable="text"), plan
    )

    assert [item.status for item in result.plan.nodes] == [
        PlanStatus.COMPLETE,
        PlanStatus.COMPLETE,
        PlanStatus.COMPLETE,
    ]
    assert result.evidence[-1].lineage == ["evidence:a", "evidence:b"]
    assert all(count == 1 for count in result.attempts.values())


@pytest.mark.anyio
async def test_retries_without_weakening_failure() -> None:
    result = await PlanExecutor(
        {"fake": FakeCapability("fake", {}, failures_before_success=1)}
    ).execute(
        TaskSpec(goal="answer", mode=RunMode.QUICK, deliverable="text"),
        Plan(nodes=[node("a", attempts=2)]),
    )

    assert result.plan.nodes[0].status == PlanStatus.COMPLETE
    assert result.attempts == {"a": 2}
    assert result.errors["a"] == ["RuntimeError: injected capability failure"]


@pytest.mark.anyio
async def test_unknown_capability_fails_preflight() -> None:
    with pytest.raises(ValueError, match="exactly one registered capability"):
        await PlanExecutor({}).execute(
            TaskSpec(goal="answer", mode=RunMode.QUICK, deliverable="text"),
            Plan(nodes=[node("a"), node("b", parents=["a"])]),
        )


@pytest.mark.anyio
async def test_independent_nodes_run_concurrently() -> None:
    active = 0
    peak = 0

    class TrackingCapability:
        name = "fake"

        async def execute(self, node, task, evidence):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1
            return await FakeCapability("fake", {}).execute(node, task, evidence)

    plan = Plan(nodes=[node("a"), node("b")])
    await PlanExecutor({"fake": TrackingCapability()}, max_concurrency=2).execute(
        TaskSpec(goal="answer", mode=RunMode.QUICK, deliverable="text"), plan
    )
    assert peak == 2


@pytest.mark.anyio
async def test_non_task_season_capability_admits_next_vintage_contracts() -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope, SeasonRef

    class Contracts:
        name = "contracts"
        task_season_scoped = False
        async def execute(self, node, task, evidence):
            return EvidenceEnvelope(
                evidence_id="contracts:2026-27", capability=self.name,
                source="warehouse:salary", observed_at=datetime.now(UTC),
                season="2026-27", rows={"player": "Jaylen Brown",
                                         "salary": 57_100_000})

    plan = Plan(nodes=[PlanNode(
        id="salary", description="next-season salary",
        capability_hints=["contracts"])])
    task = TaskSpec(goal="trade fit", mode="deep_dive", deliverable="analysis",
                    season=SeasonRef(value="2025-26", source="user", confidence=1))
    result = await PlanExecutor({"contracts": Contracts()}).execute(task, plan)
    assert result.plan.nodes[0].status == PlanStatus.COMPLETE
    assert result.evidence[0].season == "2026-27"
    assert result.evidence[0].task_season_scoped is False


@pytest.mark.anyio
async def test_task_season_capability_still_rejects_wrong_vintage() -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope, SeasonRef

    class Standings:
        name = "standings"
        task_season_scoped = True
        async def execute(self, node, task, evidence):
            return EvidenceEnvelope(
                evidence_id="standings:wrong", capability=self.name,
                source="warehouse", observed_at=datetime.now(UTC),
                season="2024-25", rows={"wins": 61})

    plan = Plan(nodes=[PlanNode(
        id="record", description="record", capability_hints=["standings"])])
    task = TaskSpec(goal="record", mode="quick", deliverable="answer",
                    season=SeasonRef(value="2025-26", source="user", confidence=1))
    result = await PlanExecutor({"standings": Standings()}).execute(task, plan)
    assert result.plan.nodes[0].status == PlanStatus.FAILED
    assert "does not match" in result.errors["record"][0]


@pytest.mark.anyio
async def test_ambiguous_capability_hints_fail_before_any_execution() -> None:
    calls: list[str] = []

    class Tracking(FakeCapability):
        async def execute(self, node, task, evidence):
            calls.append(node.id)
            return await super().execute(node, task, evidence)

    capabilities = {"one": Tracking("one", {}), "two": Tracking("two", {})}
    plan = Plan(nodes=[
        PlanNode(id="valid", description="valid", capability_hints=["one"]),
        PlanNode(id="ambiguous", description="ambiguous",
                 capability_hints=["one", "two"]),
    ])
    with pytest.raises(ValueError, match="exactly one registered capability"):
        await PlanExecutor(capabilities).execute(
            TaskSpec(goal="answer", mode="quick", deliverable="text"), plan)
    assert calls == []


@pytest.mark.anyio
async def test_invalid_arguments_fail_before_any_execution() -> None:
    calls: list[str] = []

    class Validated(FakeCapability):
        def validate_arguments(self, node):
            if "required" not in node.arguments:
                raise ValueError("required field missing")
        async def execute(self, node, task, evidence):
            calls.append(node.id)
            return await super().execute(node, task, evidence)

    plan = Plan(nodes=[
        PlanNode(id="valid", description="valid", capability_hints=["fake"],
                 arguments={"required": True}),
        PlanNode(id="bad", description="bad", capability_hints=["fake"]),
    ])
    with pytest.raises(ValueError, match="required field missing"):
        await PlanExecutor({"fake": Validated("fake", {})}).execute(
            TaskSpec(goal="answer", mode="quick", deliverable="text"), plan)
    assert calls == []


@pytest.mark.anyio
async def test_missing_required_evidence_fails_before_execution() -> None:
    calls: list[str] = []

    class Tracking(FakeCapability):
        async def execute(self, node, task, evidence):
            calls.append(node.id)
            return await super().execute(node, task, evidence)

    task = TaskSpec(
        goal="trade", mode="deep_dive", deliverable="analysis",
        required_evidence=["fake", "contracts"],
    )
    with pytest.raises(ValueError, match="required evidence.*contracts"):
        await PlanExecutor({"fake": Tracking("fake", {})}).execute(
            task, Plan(nodes=[node("only")]))
    assert calls == []


@pytest.mark.anyio
async def test_model_plan_cannot_predeclare_node_complete() -> None:
    plan = Plan(nodes=[PlanNode(
        id="facts", description="facts", capability_hints=["fake"], status=PlanStatus.COMPLETE,
    )])
    with pytest.raises(ValueError, match="must start pending"):
        await PlanExecutor({"fake": FakeCapability("fake", {})}).execute(
            TaskSpec(goal="answer", mode="quick", deliverable="text"), plan)


def test_execution_result_rejects_unknown_state_nodes_and_duplicate_evidence() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.models import ExecutionResult

    plan = Plan(nodes=[node("known")])
    with pytest.raises(ValidationError, match="unknown nodes"):
        ExecutionResult(plan=plan, attempts={"invented": 1})
    evidence = EvidenceEnvelope(
        evidence_id="same", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={},
    )
    with pytest.raises(ValidationError, match="evidence ids must be unique"):
        ExecutionResult(plan=plan, evidence=[evidence, evidence])
