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


def test_execution_result_requires_one_evidence_per_completed_node() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.models import ExecutionResult

    completed = node("done").model_copy(update={"status": PlanStatus.COMPLETE})
    with pytest.raises(ValidationError, match="match completed plan nodes"):
        ExecutionResult(plan=Plan(nodes=[completed]))
    pending = node("pending")
    evidence = EvidenceEnvelope(
        evidence_id="ev", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={},
    )
    with pytest.raises(ValidationError, match="match completed plan nodes"):
        ExecutionResult(plan=Plan(nodes=[pending]), evidence=[evidence])
    with pytest.raises(ValidationError, match="non-negative"):
        ExecutionResult(plan=Plan(nodes=[pending]), attempts={"pending": -1})


def test_execution_result_binds_evidence_capability_and_lineage_to_plan() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.models import ExecutionResult

    parent = node("parent").model_copy(update={"status": PlanStatus.COMPLETE})
    child = node("child", parents=["parent"]).model_copy(
        update={"status": PlanStatus.COMPLETE})
    parent_evidence = EvidenceEnvelope(
        evidence_id="parent-ev", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={},
    )
    child_evidence = EvidenceEnvelope(
        evidence_id="child-ev", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={}, lineage=[],
    )
    with pytest.raises(ValidationError, match="lineage does not match"):
        ExecutionResult(
            plan=Plan(nodes=[parent, child]),
            evidence=[parent_evidence, child_evidence],
        )
    wrong_capability = parent_evidence.model_copy(update={"capability": "other"})
    with pytest.raises(ValidationError, match="capability does not match"):
        ExecutionResult(plan=Plan(nodes=[parent]), evidence=[wrong_capability])


@pytest.mark.anyio
async def test_nonseason_entity_resolution_admits_on_season_resolved_task() -> None:
    from datetime import UTC, datetime
    from v2.adapters.capabilities import CAPABILITIES
    from v2.contracts import EvidenceEnvelope, SeasonRef

    class Resolver:
        name = "entity_resolution"
        task_season_scoped = CAPABILITIES[name].task_season_scoped

        async def execute(self, node, task, evidence):
            return EvidenceEnvelope(
                evidence_id="resolve:brown", capability=self.name,
                source="static:nba", observed_at=datetime.now(UTC),
                rows={"players": [{"id": "1627759", "name": "Jaylen Brown"}]},
            )

    plan = Plan(nodes=[PlanNode(
        id="resolve", description="resolve player",
        capability_hints=["entity_resolution"],
    )])
    task = TaskSpec(
        goal="evaluate Brown", mode="quick", deliverable="answer",
        season=SeasonRef(value="2025-26", source="user", confidence=1),
    )
    result = await PlanExecutor({"entity_resolution": Resolver()}).execute(task, plan)
    assert result.plan.nodes[0].status == PlanStatus.COMPLETE
    assert result.evidence[0].task_season_scoped is False


def test_execution_result_binds_attempts_and_errors_to_node_state() -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult

    pending = node("pending")
    with pytest.raises(ValidationError, match="exceed max_attempts"):
        ExecutionResult(plan=Plan(nodes=[pending]), attempts={"pending": 2})
    failed = pending.model_copy(update={"status": PlanStatus.FAILED})
    with pytest.raises(ValidationError, match="requires errors"):
        ExecutionResult(plan=Plan(nodes=[failed]), attempts={"pending": 1})
    skipped = pending.model_copy(update={"status": PlanStatus.SKIPPED})
    with pytest.raises(ValidationError, match="cannot carry errors"):
        ExecutionResult(
            plan=Plan(nodes=[skipped]), errors={"pending": ["contradiction"]},
        )


def test_execution_result_rejects_unattempted_completed_or_failed_node() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.models import ExecutionResult

    completed = node("done").model_copy(update={"status": PlanStatus.COMPLETE})
    evidence = EvidenceEnvelope(
        evidence_id="done", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={"value": 1},
    )
    with pytest.raises(ValidationError, match="without an attempt"):
        ExecutionResult(plan=Plan(nodes=[completed]), evidence=[evidence])
    failed = node("failed").model_copy(update={"status": PlanStatus.FAILED})
    with pytest.raises(ValidationError, match="without an attempt"):
        ExecutionResult(
            plan=Plan(nodes=[failed]), errors={"failed": ["failure"]},
        )


@pytest.mark.parametrize("errors,message", [([" "], "empty errors"), (["same", "same"], "duplicate errors")])
def test_execution_result_rejects_invalid_error_messages(errors, message) -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult

    failed = node("failed").model_copy(update={"status": PlanStatus.FAILED})
    with pytest.raises(ValidationError, match=message):
        ExecutionResult(
            plan=Plan(nodes=[failed]), attempts={"failed": 1},
            errors={"failed": errors},
        )


def test_execution_result_rejects_nonterminal_node_without_attempts_remaining() -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult

    pending = node("pending", attempts=1)
    with pytest.raises(ValidationError, match="no attempts remaining"):
        ExecutionResult(plan=Plan(nodes=[pending]), attempts={"pending": 1})


@pytest.mark.anyio
async def test_cancelling_execution_cancels_every_inflight_node() -> None:
    started = {"a": asyncio.Event(), "b": asyncio.Event()}
    cancelled: set[str] = set()

    class BlockingCapability:
        name = "fake"

        async def execute(self, node, task, evidence):
            started[node.id].set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.add(node.id)
                raise

    running = asyncio.create_task(PlanExecutor(
        {"fake": BlockingCapability()}, max_concurrency=2,
    ).execute(
        TaskSpec(goal="answer", mode=RunMode.QUICK, deliverable="text"),
        Plan(nodes=[node("a"), node("b")]),
    ))
    await asyncio.gather(*(event.wait() for event in started.values()))
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running
    assert cancelled == {"a", "b"}
