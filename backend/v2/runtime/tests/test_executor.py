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
        completion_test="returns evidence",
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
async def test_failed_parent_skips_descendant() -> None:
    result = await PlanExecutor({}).execute(
        TaskSpec(goal="answer", mode=RunMode.QUICK, deliverable="text"),
        Plan(nodes=[node("a"), node("b", parents=["a"])]),
    )

    assert [item.status for item in result.plan.nodes] == [
        PlanStatus.FAILED,
        PlanStatus.SKIPPED,
    ]
    assert result.errors == {"a": ["no registered capability matches capability hints"]}


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
        capability_hints=["contracts"], completion_test="salary row")])
    task = TaskSpec(goal="trade fit", mode="deep_dive", deliverable="analysis",
                    season=SeasonRef(value="2025-26", source="user", confidence=1))
    result = await PlanExecutor({"contracts": Contracts()}).execute(task, plan)
    assert result.plan.nodes[0].status == PlanStatus.COMPLETE
    assert result.evidence[0].season == "2026-27"


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
        id="record", description="record", capability_hints=["standings"],
        completion_test="record row")])
    task = TaskSpec(goal="record", mode="quick", deliverable="answer",
                    season=SeasonRef(value="2025-26", source="user", confidence=1))
    result = await PlanExecutor({"standings": Standings()}).execute(task, plan)
    assert result.plan.nodes[0].status == PlanStatus.FAILED
    assert "does not match" in result.errors["record"][0]
