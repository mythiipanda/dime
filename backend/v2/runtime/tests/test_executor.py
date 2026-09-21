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


@pytest.mark.parametrize("field,value,error", [
    ("max_concurrency", 0, "between 1 and 16"),
    ("max_concurrency", 17, "between 1 and 16"),
    ("max_concurrency", True, "must be an integer"),
    ("max_concurrency", 1.5, "must be an integer"),
    ("max_failures", 0, "between 1 and 10"),
    ("max_failures", 11, "between 1 and 10"),
    ("max_failures", False, "must be an integer or None"),
    ("max_failures", 1.5, "must be an integer or None"),
])
def test_executor_rejects_invalid_operational_limits(field, value, error) -> None:
    with pytest.raises((TypeError, ValueError), match=error):
        PlanExecutor({"fake": FakeCapability("fake", {})}, **{field: value})


def test_executor_allows_explicit_unlimited_failure_budget() -> None:
    PlanExecutor({"fake": FakeCapability("fake", {})}, max_failures=None)


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
async def test_repeated_identical_failures_return_a_failed_partial_result() -> None:
    result = await PlanExecutor({
        "fake": FakeCapability("fake", {}, failures_before_success=2),
    }).execute(
        TaskSpec(goal="answer", mode=RunMode.QUICK, deliverable="text"),
        Plan(nodes=[node("a", attempts=2)]),
    )

    assert result.plan.nodes[0].status == PlanStatus.FAILED
    assert result.attempts == {"a": 2}
    assert result.errors == {
        "a": ["RuntimeError: injected capability failure"],
    }


@pytest.mark.anyio
async def test_duplicate_evidence_identity_uses_remaining_attempt_budget() -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope

    class CollidingCapability:
        name = "fake"
        task_season_scoped = True

        async def execute(self, node, task, evidence):
            return EvidenceEnvelope(
                evidence_id="same", capability=self.name, source="fixture",
                observed_at=datetime.now(UTC), rows={"node": node.id},
            )

    result = await PlanExecutor({"fake": CollidingCapability()}).execute(
        TaskSpec(goal="answer", mode=RunMode.QUICK, deliverable="text"),
        Plan(nodes=[node("a"), node("b", attempts=2)]),
    )

    assert [item.status for item in result.plan.nodes] == [
        PlanStatus.COMPLETE, PlanStatus.FAILED,
    ]
    assert result.attempts == {"a": 1, "b": 2}
    assert result.errors == {"b": ["duplicate evidence id: same"]}


@pytest.mark.anyio
async def test_capability_error_is_bounded_for_result_and_stream_contracts() -> None:
    class NoisyCapability:
        name = "fake"
        task_season_scoped = True

        async def execute(self, node, task, evidence):
            raise RuntimeError("x" * 5000)

    result = await PlanExecutor({"fake": NoisyCapability()}).execute(
        TaskSpec(goal="answer", mode=RunMode.QUICK, deliverable="text"),
        Plan(nodes=[node("a")]),
    )

    assert result.plan.nodes[0].status == PlanStatus.FAILED
    assert len(result.errors["a"][0]) == 4000
    assert result.errors["a"][0].startswith("RuntimeError: ")


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
async def test_executor_rejects_untyped_capability_season_scope() -> None:
    class Invalid(FakeCapability):
        task_season_scoped = "false"

    capability = Invalid("fake", {"wins": 61})
    capability.task_season_scoped = "false"
    result = await PlanExecutor({"fake": capability}).execute(
        TaskSpec(goal="record", mode="quick", deliverable="answer"),
        Plan(nodes=[node("record")]),
    )

    assert result.plan.nodes[0].status == PlanStatus.FAILED
    assert result.errors["record"] == [
        "TypeError: capability task_season_scoped must be boolean",
    ]


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
        ExecutionResult(plan=Plan(nodes=[node("a"), node("b")]), evidence_by_node={"a": evidence, "b": evidence})


def test_execution_result_requires_one_evidence_per_completed_node() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.models import ExecutionResult

    completed = node("done").model_copy(update={"status": PlanStatus.COMPLETE})
    ExecutionResult(plan=Plan(nodes=[completed]), attempts={"done": 1})
    pending = node("pending")
    evidence = EvidenceEnvelope(
        evidence_id="ev", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={},
    )
    with pytest.raises(ValidationError, match="owner must be complete"):
        ExecutionResult(plan=Plan(nodes=[pending]), evidence_by_node={"pending": evidence})
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
            evidence_by_node={"parent": parent_evidence, "child": child_evidence},
            attempts={"parent": 1, "child": 1},
        )
    wrong_capability = parent_evidence.model_copy(update={"capability": "other"})
    with pytest.raises(ValidationError, match="capability does not match"):
        ExecutionResult(plan=Plan(nodes=[parent]), evidence_by_node={"parent": wrong_capability}, attempts={"parent": 1})


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
        ExecutionResult(plan=Plan(nodes=[completed]), evidence_by_node={"done": evidence})
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


def test_execution_result_rejects_failed_node_with_attempts_remaining() -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult

    failed = node("failed", attempts=2).model_copy(update={"status": PlanStatus.FAILED})
    with pytest.raises(ValidationError, match="exhaust its attempt budget"):
        ExecutionResult(
            plan=Plan(nodes=[failed]), attempts={"failed": 1},
            errors={"failed": ["failure"]},
        )


def test_execution_result_rejects_skipped_node_with_attempts() -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult

    skipped = node("skipped").model_copy(update={"status": PlanStatus.SKIPPED})
    with pytest.raises(ValidationError, match="cannot carry attempts"):
        ExecutionResult(plan=Plan(nodes=[skipped]), attempts={"skipped": 1})


@pytest.mark.parametrize("count", [True, 1.5, "1"])
def test_execution_result_rejects_noninteger_attempt_counts(count) -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult
    with pytest.raises(ValidationError, match="valid integer|attempt counts must be integers"):
        ExecutionResult(plan=Plan(nodes=[node("pending")]), attempts={"pending": count})


@pytest.mark.anyio
async def test_executor_revalidates_capability_evidence_before_admission() -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope

    class InvalidEvidence:
        name = "fake"
        task_season_scoped = True
        async def execute(self, node, task, evidence):
            valid = EvidenceEnvelope(
                evidence_id="ev", capability=self.name, source="fixture",
                observed_at=datetime.now(UTC), rows={"wins": 61},
            )
            return valid.model_copy(update={"source": " "})

    result = await PlanExecutor({"fake": InvalidEvidence()}).execute(
        TaskSpec(goal="record", mode="quick", deliverable="answer"),
        Plan(nodes=[node("record")]),
    )
    assert result.plan.nodes[0].status == PlanStatus.FAILED
    assert "evidence identity" in result.errors["record"][0]


def test_execution_result_bounds_errors_per_node() -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult
    failed = node("failed", attempts=5).model_copy(update={"status": PlanStatus.FAILED})
    with pytest.raises(ValidationError, match="too many errors"):
        ExecutionResult(plan=Plan(nodes=[failed]), attempts={"failed": 5},
                        errors={"failed": [f"error-{index}" for index in range(6)]})

@pytest.mark.anyio
async def test_compound_ratings_plan_cannot_skip_requested_populations() -> None:
    from v2.contracts import Plan, PlanNode, TaskSpec

    capabilities = {
        name: FakeCapability(name, rows={"name": name})
        for name in (
            "team_ratings", "player_ratings", "playoff_team_ratings",
            "playoffs",
        )
    }
    executor = PlanExecutor(capabilities)
    task = TaskSpec(
        goal="rank offense and defense", mode="deep_dive",
        deliverable="team, player, and playoff ratings",
        required_evidence=[
            "team_ratings", "player_ratings", "playoff_team_ratings",
        ],
        requirements=[
            {"id": "teams", "description": "team ratings", "capability_options": ["team_ratings"]},
            {"id": "players", "description": "player ratings", "capability_options": ["player_ratings"]},
            {"id": "playoffs", "description": "playoff ratings", "capability_options": ["playoff_team_ratings"]},
        ],
    )
    incomplete = Plan(nodes=[PlanNode(
        id="bracket", description="playoff results",
        capability_hints=["playoffs"],
    )])
    with pytest.raises(ValueError, match=(
        "players.*playoffs.*teams"
    )):
        await executor.execute(task, incomplete)

@pytest.mark.anyio
async def test_requirement_coverage_rejects_semantically_wrong_capability() -> None:
    from v2.contracts import Plan, PlanNode, TaskSpec

    executor = PlanExecutor({
        "playoffs": FakeCapability("playoffs", rows={}),
        "playoff_team_ratings": FakeCapability("playoff_team_ratings", rows={}),
    })
    task = TaskSpec(
        goal="playoff ratings", mode="quick", deliverable="ratings",
        requirements=[{
            "id": "playoff_ratings", "description": "rate playoff teams",
            "capability_options": ["playoff_team_ratings"],
        }],
    )
    wrong = Plan(nodes=[PlanNode(
        id="bracket", description="results", capability_hints=["playoffs"],
        covers_requirement_ids=["playoff_ratings"],
    )])
    with pytest.raises(ValueError, match="cannot satisfy requirement"):
        await executor.execute(task, wrong)


@pytest.mark.anyio
async def test_matchup_plan_executes_prediction_with_covered_requirement():
    from v2.contracts import Plan, PlanNode, TaskSpec

    class Prediction(FakeCapability):
        def __init__(self):
            super().__init__("game_prediction", rows={"winner": "Boston Celtics"})
            self.calls = []
        async def execute(self, node, task, evidence):
            self.calls.append(dict(node.arguments))
            return await super().execute(node, task, evidence)

    capability = Prediction()
    task = TaskSpec(
        goal="Who wins Celtics vs Knicks?", mode="quick", deliverable="winner",
        required_evidence=["game_prediction"],
        requirements=[{"id": "winner", "description": "predict matchup winner",
                       "capability_options": ["game_prediction"]}],
    )
    plan = Plan(nodes=[PlanNode(
        id="prediction", description="simulate matchup",
        capability_hints=["game_prediction"],
        arguments={"a": "Boston Celtics", "b": "New York Knicks",
                   "season": "2025-26"},
        covers_requirement_ids=["winner"],
    )])
    result = await PlanExecutor({"game_prediction": capability}).execute(task, plan)
    assert capability.calls == [{
        "a": "Boston Celtics", "b": "New York Knicks", "season": "2025-26",
    }]
    assert result.evidence[0].capability == "game_prediction"

@pytest.mark.anyio
async def test_dependent_entity_argument_cannot_drift_from_resolution():
    from datetime import UTC, datetime
    from v2.contracts import EntityRef, EvidenceEnvelope

    class Resolver:
        name = "entity_resolution"
        task_season_scoped = False
        async def execute(self, node, task, evidence):
            return EvidenceEnvelope(
                evidence_id="resolved:tatum", capability=self.name,
                source="fixture", observed_at=datetime.now(UTC), rows={},
                entities=[EntityRef(id="1628369", type="player",
                                    display_name="Jayson Tatum")],
            )

    class TeamImpact(FakeCapability):
        dependent_entity_arguments = {"team": "team"}
        def __init__(self):
            super().__init__("injury_impact", rows={"team": "ATL"})
            self.called = False
        async def execute(self, node, task, evidence):
            self.called = True
            return await super().execute(node, task, evidence)

    impact = TeamImpact()
    plan = Plan(nodes=[
        PlanNode(id="resolve", description="resolve player",
                 capability_hints=["entity_resolution"]),
        PlanNode(id="impact", description="team injury impact",
                 depends_on=["resolve"], capability_hints=["injury_impact"],
                 arguments={"team": "ATL"}),
    ])
    result = await PlanExecutor({
        "entity_resolution": Resolver(), "injury_impact": impact,
    }).execute(TaskSpec(goal="Tatum availability", mode="quick",
                       deliverable="condition"), plan)

    assert impact.called is False
    assert result.plan.nodes[1].status == PlanStatus.FAILED
    assert result.errors["impact"] == [
        "ValueError: dependent argument 'team' requires a resolved team identity"
    ]


@pytest.mark.anyio
async def test_dependent_entity_argument_accepts_canonical_alias():
    from datetime import UTC, datetime
    from v2.contracts import EntityRef, EvidenceEnvelope

    class Resolver:
        name = "entity_resolution"
        task_season_scoped = False
        async def execute(self, node, task, evidence):
            return EvidenceEnvelope(
                evidence_id="resolved:boston", capability=self.name,
                source="fixture", observed_at=datetime.now(UTC), rows={},
                entities=[EntityRef(id="1610612738", type="team",
                                    display_name="Boston Celtics")],
            )

    class TeamImpact(FakeCapability):
        dependent_entity_arguments = {"team": "team"}

    plan = Plan(nodes=[
        PlanNode(id="resolve", description="resolve team",
                 capability_hints=["entity_resolution"]),
        PlanNode(id="impact", description="team injury impact",
                 depends_on=["resolve"], capability_hints=["injury_impact"],
                 arguments={"team": "BOS"}),
    ])
    result = await PlanExecutor({
        "entity_resolution": Resolver(),
        "injury_impact": TeamImpact("injury_impact", rows={"team": "BOS"}),
    }).execute(TaskSpec(goal="Boston availability", mode="quick",
                       deliverable="condition"), plan)

    assert result.plan.nodes[1].status == PlanStatus.COMPLETE

@pytest.mark.anyio
async def test_typed_requirements_allow_supported_execution_when_intake_evidence_is_stale():
    task = TaskSpec(goal="phase compare", mode="quick", deliverable="answer",
        required_evidence=["player_report", "shooting_efficiency"], requirements=[{
            "id":"regular", "description":"regular line",
            "capability_options":["player_report"]}])
    plan = Plan(nodes=[PlanNode(id="regular", description="regular",
        capability_hints=["player_report"], covers_requirement_ids=["regular"])])
    result = await PlanExecutor({"player_report": FakeCapability(
        "player_report", {"ppg": 33.9})}).execute(task, plan)
    assert result.evidence[0].capability == "player_report"


def _owned_execution(*, reordered=False, control=False):
    from datetime import UTC,datetime
    from v2.contracts import EvidenceEnvelope,Plan,PlanNode
    from v2.runtime.models import ExecutionResult
    ev1=EvidenceEnvelope(evidence_id="one",capability="standings",source="fixture",observed_at=datetime.now(UTC),rows={"WINS":0,"ACTIVE":False,"LOSSES":7})
    ev2=EvidenceEnvelope(evidence_id="two",capability="standings",source="fixture",observed_at=datetime.now(UTC),rows={"LOSSES":7})
    nodes=[PlanNode(id="n1",description="one",capability_hints=["standings"],covers_requirement_ids=["a"],status="complete"),PlanNode(id="n2",description="two",capability_hints=["standings"],covers_requirement_ids=["b"],status="complete")]
    if control:nodes.insert(1,PlanNode(id="resolve",description="control",capability_hints=[],status="complete"))
    owned={"n2":ev2,"n1":ev1} if reordered else {"n1":ev1,"n2":ev2}
    attempts={n.id:1 for n in nodes}
    return ExecutionResult(plan=Plan(nodes=nodes),evidence_by_node=owned,attempts=attempts)


def test_execution_ownership_is_explicit_under_reorder_and_control_node():
    execution=_owned_execution(reordered=True,control=True)
    assert execution.evidence_by_node["n1"].evidence_id=="one"
    assert "resolve" not in execution.evidence_by_node


def test_execution_rejects_orphan_wrong_node_and_duplicate_evidence():
    from pydantic import ValidationError
    good=_owned_execution()
    payload=good.model_dump();payload["evidence_by_node"]["orphan"]=payload["evidence_by_node"].pop("n1")
    with pytest.raises(ValidationError):type(good).model_validate(payload)
    payload=good.model_dump();payload["evidence_by_node"]["n2"]=payload["evidence_by_node"]["n1"]
    with pytest.raises(ValidationError):type(good).model_validate(payload)


def test_evidence_binding_preserves_zero_false_and_rejects_wrong_authority():
    from v2.contracts import TaskSpec,EvidenceRequirement,DraftReport,Claim,VerifiedClaim,EvidenceOutputBinding
    from v2.runtime.models import admit_verified_claim_bindings
    task=TaskSpec(goal="stats",mode="quick",deliverable="answer",requirements=[EvidenceRequirement(id="a",description="a",capability_options=["standings"],requested_outputs=["WINS","ACTIVE"]),EvidenceRequirement(id="b",description="b",capability_options=["standings"],requested_outputs=["LOSSES"])])
    execution=_owned_execution()
    for output,selector in [("WINS","rows.WINS"),("ACTIVE","rows.ACTIVE")]:
        binding=EvidenceOutputBinding(value=({"kind":"boolean","value":False} if output=="ACTIVE" else {"kind":"integer","value":0}), unit=({"kind":"unitless"} if output=="ACTIVE" else {"kind":"declared","value":"count"}), domain="standings", requirement_id="a",output_id=output,node_id="n1",evidence_id="one",selector=selector)
        claim=Claim(text="zero and inactive",kind="observed",evidence_ids=["one"],output_bindings=[binding]);draft=DraftReport(sections=[],claims=[claim])
        verified=VerifiedClaim(claim_index=0,claim=claim,evidence_ids=["one"],output_bindings=[binding])
        assert admit_verified_claim_bindings(task,execution,draft,verified) is verified
    bad=[dict(requirement_id="b",output_id="LOSSES",node_id="n1",evidence_id="one",selector="rows.WINS"),dict(requirement_id="a",output_id="LOSSES",node_id="n1",evidence_id="one",selector="rows.WINS"),dict(requirement_id="a",output_id="WINS",node_id="n1",evidence_id="one",selector="rows.NOPE")]
    for item in bad:
        binding=EvidenceOutputBinding(value={"kind":"integer","value":0}, unit={"kind":"unitless"}, domain="standings", **item)
        bad_claim=Claim(text="bad",kind="observed",evidence_ids=["one"],output_bindings=[binding])
        verified=VerifiedClaim(claim_index=0,claim=bad_claim,evidence_ids=["one"],output_bindings=[binding])
        with pytest.raises(ValueError):admit_verified_claim_bindings(task,execution,draft,verified)


def test_binding_rejects_existing_wrong_metric_and_wrong_capability():
    from v2.contracts import (TaskSpec, EvidenceRequirement, DraftReport, Claim,
                              VerifiedClaim, EvidenceOutputBinding)
    from v2.runtime.models import admit_verified_claim_bindings
    task = TaskSpec(goal="wins", mode="quick", deliverable="answer",
        requirements=[EvidenceRequirement(id="a", description="wins",
            capability_options=["standings"], requested_outputs=["WINS"])])
    execution = _owned_execution()
    for updates in [
        {"selector": "rows.LOSSES"},
        {"domain": "player_report"},
        {"unit": {"kind":"declared","value":"percent_0_100"}},
    ]:
        values = dict(requirement_id="a", output_id="WINS", node_id="n1",
                      evidence_id="one", selector="rows.WINS",
                      value={"kind":"integer","value":0},
                      unit={"kind":"declared","value":"count"},
                      domain="standings")
        values.update(updates)
        binding = EvidenceOutputBinding(**values)
        claim = Claim(text="wins", kind="observed", evidence_ids=["one"],
                      output_bindings=[binding])
        verified = VerifiedClaim(claim_index=0, claim=claim,
            evidence_ids=["one"], output_bindings=[binding])
        with pytest.raises(ValueError):
            admit_verified_claim_bindings(task, execution,
                DraftReport(sections=[], claims=[claim]), verified)
    wrong_task = task.model_copy(deep=True)
    wrong_task.requirements[0].capability_options = ["player_report"]
    binding = EvidenceOutputBinding(value={"kind":"integer","value":0}, unit={"kind":"declared","value":"count"}, domain="standings", requirement_id="a", output_id="WINS",
        node_id="n1", evidence_id="one", selector="rows.WINS")
    claim = Claim(text="wins", kind="observed", evidence_ids=["one"],
                  output_bindings=[binding])
    with pytest.raises(ValueError, match="capability"):
        admit_verified_claim_bindings(wrong_task, execution,
            DraftReport(sections=[], claims=[claim]),
            VerifiedClaim(claim_index=0, claim=claim,
                evidence_ids=["one"], output_bindings=[binding]))


def test_task_output_binding_and_selector_local_subject():
    from datetime import UTC, datetime
    from v2.contracts import (TaskSpec, DraftReport, Claim, VerifiedClaim,
        EvidenceOutputBinding, EntityRef, EvidenceEnvelope, Plan, PlanNode)
    from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings
    players = [EntityRef(id="23", type="player", display_name="LeBron"),
               EntityRef(id="30", type="player", display_name="Curry")]
    evidence = EvidenceEnvelope(evidence_id="pair", capability="player_report",
        source="fixture", observed_at=datetime.now(UTC), entities=players,
        rows=[{"PLAYER_ID":"23","PTS":25}, {"PLAYER_ID":"30","PTS":30}])
    execution = ExecutionResult(plan=Plan(nodes=[PlanNode(id="pair",
        description="pair", capability_hints=["player_report"], status="complete")]),
        evidence_by_node={"pair": evidence}, attempts={"pair": 1})
    task = TaskSpec(goal="LeBron points", mode="quick", deliverable="answer",
                    requested_outputs=["PTS"], entities=[players[0]])
    good = EvidenceOutputBinding(value={"kind":"integer","value":25}, unit={"kind":"unitless"}, domain="player_report", requirement_kind="task", output_id="PTS",
        node_id="pair", evidence_id="pair", selector="rows[0].PTS",
        subject_entity_type="player", subject_entity_id="23", subject_selector="rows[0].PLAYER_ID", row_selector="rows[0]")
    claim = Claim(text="LeBron scored 25", kind="observed",
                  evidence_ids=["pair"], output_bindings=[good])
    assert admit_verified_claim_bindings(task, execution,
        DraftReport(sections=[], claims=[claim]), VerifiedClaim(claim_index=0,
            claim=claim, evidence_ids=["pair"], output_bindings=[good]))
    wrong = good.model_copy(update={"selector":"rows[1].PTS"})
    wrong_claim = claim.model_copy(update={"output_bindings":[wrong]})
    with pytest.raises(ValueError, match="outside declared row"):
        admit_verified_claim_bindings(task, execution,
            DraftReport(sections=[], claims=[wrong_claim]),
            VerifiedClaim(claim_index=0, claim=wrong_claim,
                evidence_ids=["pair"], output_bindings=[wrong]))


def test_calculation_binding_requires_exact_calculation_and_requirement():
    from decimal import Decimal
    from v2.contracts import TaskSpec,CalculationRequirement,DraftReport,Claim,VerifiedClaim,CalculationOutputBinding,DeclaredCalculation,DeclaredCalculationInput
    from v2.runtime.models import admit_verified_claim_bindings
    task=TaskSpec(goal="delta",mode="quick",deliverable="answer",calculation_requirements=[CalculationRequirement(id="delta",description="delta",requested_outputs=["PTS_DELTA"])])
    execution=_owned_execution();calc=DeclaredCalculation(calculation_id="c",requirement_id="delta",operation="subtract",inputs=[DeclaredCalculationInput(evidence_id="one",path="rows.WINS"),DeclaredCalculationInput(evidence_id="two",path="rows.LOSSES")],result=Decimal("-7"))
    binding=CalculationOutputBinding(requirement_id="delta",output_id="PTS_DELTA",calculation_id="c")
    claim=Claim(text="delta is -7",kind="derived",evidence_ids=["one","two"],calculation_id="c",output_bindings=[binding]);draft=DraftReport(sections=[],claims=[claim],calculations=[calc]);verified=VerifiedClaim(claim_index=0,claim=claim,evidence_ids=["one","two"],output_bindings=[binding])
    assert admit_verified_claim_bindings(task,execution,draft,verified) is verified
    wrong=CalculationOutputBinding(requirement_id="delta",output_id="PTS_DELTA",calculation_id="wrong")
    bad_claim=claim.model_copy(update={"calculation_id":"wrong","output_bindings":[wrong]})
    bad=VerifiedClaim(claim_index=0,claim=bad_claim,evidence_ids=["one","two"],output_bindings=[wrong])
    with pytest.raises(ValueError):admit_verified_claim_bindings(task,execution,draft,bad)


def test_checkpoint_v2_roundtrip_and_rejects_legacy_shape(tmp_path):
    import json
    from v2.runtime.checkpoints import ExecutionCheckpoint,FileCheckpointStore
    execution=_owned_execution(reordered=True);checkpoint=ExecutionCheckpoint(version=2,run_id="r",task={"goal":"g","mode":"quick","deliverable":"d"},plan=execution.plan,evidence_by_node=execution.evidence_by_node,attempts=execution.attempts)
    store=FileCheckpointStore(tmp_path);store.save(checkpoint);loaded=store.load("r")
    assert loaded==checkpoint and loaded.version==2
    payload=checkpoint.model_dump();payload.pop("version");(tmp_path/"old.json").write_text(json.dumps(payload,default=str))
    with pytest.raises(Exception):store.load("old")


def test_execution_and_binding_serialization_preserves_explicit_identity():
    from v2.contracts import Claim, EvidenceOutputBinding, VerifiedClaim
    from v2.runtime.models import ExecutionResult

    execution = _owned_execution(reordered=True, control=True)
    restored = ExecutionResult.model_validate_json(execution.model_dump_json())
    assert list(restored.evidence_by_node) == ["n2", "n1"]
    assert restored.evidence_by_node["n1"].evidence_id == "one"
    binding = EvidenceOutputBinding(value={"kind":"integer","value":0}, unit={"kind":"unitless"}, domain="standings",
        requirement_id="a", output_id="WINS", node_id="n1",
        evidence_id="one", selector="rows.WINS",
    )
    claim = Claim(
        text="zero", kind="observed", evidence_ids=["one"],
        output_bindings=[binding],
    )
    verified = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=["one"],
        output_bindings=[binding],
    )
    assert VerifiedClaim.model_validate_json(
        verified.model_dump_json()) == verified


def test_verified_claim_authority_is_separate_from_untrusted_claim_proposal():
    from v2.contracts import Claim, EvidenceOutputBinding, VerifiedClaim

    binding = EvidenceOutputBinding(value={"kind":"integer","value":0}, unit={"kind":"unitless"}, domain="standings",
        requirement_id="a", output_id="WINS", node_id="n1",
        evidence_id="one", selector="rows.WINS",
    )
    claim = Claim(text="zero", kind="observed", evidence_ids=["one"],
                  output_bindings=[binding])
    verified = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=["one"], output_bindings=[])
    assert verified.claim.output_bindings == [binding]
    assert verified.output_bindings == []


def test_binding_value_exactness_numeric_types_and_boolean_zero_distinction():
    from v2.contracts import (TaskSpec, EvidenceRequirement, DraftReport, Claim,
                              VerifiedClaim, EvidenceOutputBinding)
    from v2.runtime.models import admit_verified_claim_bindings
    task = TaskSpec(goal="wins", mode="quick", deliverable="answer",
        requirements=[EvidenceRequirement(id="a", description="wins",
            capability_options=["standings"], requested_outputs=["WINS","ACTIVE"])])
    execution = _owned_execution()
    def check(output, selector, value, unit):
        binding = EvidenceOutputBinding(requirement_id="a", output_id=output,
            node_id="n1", evidence_id="one", selector=selector, value=value,
            unit=unit, domain="standings")
        claim = Claim(text="value", kind="observed", evidence_ids=["one"],
                      output_bindings=[binding])
        return admit_verified_claim_bindings(task, execution,
            DraftReport(sections=[], claims=[claim]),
            VerifiedClaim(claim_index=0, claim=claim,
                evidence_ids=["one"], output_bindings=[binding]))
    assert check("WINS", "rows.WINS", {"kind":"integer","value":0},
                 {"kind":"declared","value":"count"})
    from decimal import Decimal
    with pytest.raises(Exception):
        check("WINS", "rows.WINS", {"kind":"integer","value":"0"},
              {"kind":"declared","value":"count"})
    assert check("ACTIVE", "rows.ACTIVE", {"kind":"boolean","value":False},
                 {"kind":"unitless"})
    for value in [
        {"kind":"integer","value":99},
        {"kind":"string","value":"0"},
        {"kind":"boolean","value":False},
    ]:
        with pytest.raises(ValueError, match="value"):
            check("WINS", "rows.WINS", value,
                  {"kind":"declared","value":"count"})


def test_numeric_output_json_boundary_rejects_strings_and_roundtrips_numbers():
    import json
    from decimal import Decimal
    from v2.contracts import EvidenceOutputBinding
    base = dict(requirement_id="a", output_id="WINS", node_id="n1",
        evidence_id="one", selector="rows.WINS",
        unit={"kind":"declared","value":"count"}, domain="standings")
    for kind, raw in [("integer","0"), ("float","99"), ("integer",True)]:
        payload = dict(base, value={"kind":kind,"value":raw})
        with pytest.raises(Exception):
            EvidenceOutputBinding.model_validate_json(json.dumps(payload))
    cases = [
        {"kind":"integer","value":0},
        {"kind":"integer","value":10**200},
        {"kind":"float","value":1.5},
        {"kind":"decimal","value":"0.123456789123456789"},
        {"kind":"decimal","value":"1e+10000"},
        {"kind":"decimal","value":"1e-10000"},
        {"kind":"decimal","value":"-0"},
    ]
    for value in cases:
        binding = EvidenceOutputBinding(**dict(base, value=value))
        encoded = binding.model_dump_json()
        assert EvidenceOutputBinding.model_validate_json(encoded) == binding
        if value["kind"] == "decimal":
            assert binding.value.value == value["value"]
            assert Decimal(binding.value.value).is_finite()


def test_subject_selector_rejects_mixed_entity_id_and_allows_nested_metric():
    from datetime import UTC, datetime
    from v2.contracts import (TaskSpec, DraftReport, Claim, VerifiedClaim,
        EvidenceOutputBinding, EntityRef, EvidenceEnvelope, Plan, PlanNode)
    from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings
    lebron = EntityRef(id="23", type="player", display_name="LeBron")
    evidence = EvidenceEnvelope(evidence_id="mixed", capability="player_report",
        source="fixture", observed_at=datetime.now(UTC), entities=[lebron],
        rows=[{"PLAYER_ID":"30", "TEAM_ID":"23", "stats":{"PTS":25}}])
    execution = ExecutionResult(plan=Plan(nodes=[PlanNode(id="facts",
        description="facts", capability_hints=["player_report"], status="complete")]),
        evidence_by_node={"facts":evidence}, attempts={"facts":1})
    task = TaskSpec(goal="LeBron points", mode="quick", deliverable="answer",
                    requested_outputs=["PTS"], entities=[lebron])
    def validate(subject_selector):
        binding = EvidenceOutputBinding(requirement_kind="task", output_id="PTS",
            node_id="facts", evidence_id="mixed", selector="rows[0].stats.PTS",
            value={"kind":"integer","value":25}, unit={"kind":"unitless"},
            domain="player_report", subject_entity_type="player",
            subject_entity_id="23", subject_selector=subject_selector, row_selector="rows[0]")
        claim = Claim(text="points", kind="observed", evidence_ids=["mixed"],
                      output_bindings=[binding])
        return admit_verified_claim_bindings(task, execution,
            DraftReport(sections=[], claims=[claim]),
            VerifiedClaim(claim_index=0, claim=claim,
                evidence_ids=["mixed"], output_bindings=[binding]))
    with pytest.raises(ValueError, match="wrong entity type"):
        validate("rows[0].TEAM_ID")
    evidence.rows[0]["PLAYER_ID"] = "23"
    assert validate("rows[0].PLAYER_ID")


def test_numeric_variants_reject_cross_type_coercion_in_json_and_python():
    import json
    from v2.contracts import EvidenceOutputBinding
    base = dict(requirement_id="a", output_id="WINS", node_id="n1",
        evidence_id="one", selector="rows.WINS",
        unit={"kind":"declared","value":"count"}, domain="standings")
    bad = [
        {"kind":"float","value":1},
        {"kind":"integer","value":1.0},
        {"kind":"float","value":True},
        {"kind":"integer","value":False},
    ]
    for value in bad:
        with pytest.raises(Exception):
            EvidenceOutputBinding(**dict(base, value=value))
        with pytest.raises(Exception):
            EvidenceOutputBinding.model_validate_json(
                json.dumps(dict(base, value=value)))


def test_keyed_map_row_selector_blocks_sibling_and_prefix_tricks():
    from datetime import UTC, datetime
    from v2.contracts import (TaskSpec, DraftReport, Claim, VerifiedClaim,
        EvidenceOutputBinding, EntityRef, EvidenceEnvelope, Plan, PlanNode)
    from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings
    lebron = EntityRef(id="23", type="player", display_name="LeBron")
    curry = EntityRef(id="30", type="player", display_name="Curry")
    evidence = EvidenceEnvelope(evidence_id="pair", capability="player_report",
        source="fixture", observed_at=datetime.now(UTC), entities=[lebron,curry],
        rows={"lebron":{"PLAYER_ID":"23","stats":{"PTS":25}},
              "curry":{"PLAYER_ID":"30","stats":{"PTS":30}},
              "lebron_extra":{"PLAYER_ID":"30","stats":{"PTS":99}}})
    execution = ExecutionResult(plan=Plan(nodes=[PlanNode(id="pair",
        description="pair", capability_hints=["player_report"], status="complete")]),
        evidence_by_node={"pair":evidence}, attempts={"pair":1})
    task = TaskSpec(goal="LeBron", mode="quick", deliverable="answer",
                    requested_outputs=["PTS"], entities=[lebron])
    def validate(subject_selector, row_selector, selector="rows.lebron.stats.PTS"):
        binding = EvidenceOutputBinding(requirement_kind="task", output_id="PTS",
            node_id="pair", evidence_id="pair", selector=selector,
            row_selector=row_selector, value={"kind":"integer","value":25},
            unit={"kind":"unitless"}, domain="player_report",
            subject_entity_type="player", subject_entity_id="23",
            subject_selector=subject_selector)
        claim = Claim(text="25", kind="observed", evidence_ids=["pair"],
                      output_bindings=[binding])
        return admit_verified_claim_bindings(task, execution,
            DraftReport(sections=[], claims=[claim]), VerifiedClaim(
                claim_index=0, claim=claim, evidence_ids=["pair"],
                output_bindings=[binding]))
    assert validate("rows.lebron.PLAYER_ID", "rows.lebron")
    with pytest.raises(ValueError, match="direct row child"):
        validate("rows.curry.PLAYER_ID", "rows.lebron")
    with pytest.raises(ValueError, match="direct row child"):
        validate("rows.lebron_extra.PLAYER_ID", "rows.lebron")


def test_broad_row_selector_cannot_join_sibling_subject_and_metric():
    from datetime import UTC, datetime
    from v2.contracts import (TaskSpec, DraftReport, Claim, VerifiedClaim,
        EvidenceOutputBinding, EntityRef, EvidenceEnvelope, Plan, PlanNode)
    from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings
    lebron = EntityRef(id="23", type="player", display_name="LeBron")
    def reject(rows, selector, subject_selector, row_selector):
        evidence = EvidenceEnvelope(evidence_id="ev", capability="player_report",
            source="fixture", observed_at=datetime.now(UTC), entities=[lebron], rows=rows)
        execution = ExecutionResult(plan=Plan(nodes=[PlanNode(id="facts",
            description="facts", capability_hints=["player_report"], status="complete")]),
            evidence_by_node={"facts":evidence}, attempts={"facts":1})
        binding = EvidenceOutputBinding(requirement_kind="task", output_id="PTS",
            node_id="facts", evidence_id="ev", selector=selector,
            row_selector=row_selector, value={"kind":"integer","value":25},
            unit={"kind":"unitless"}, domain="player_report",
            subject_entity_type="player", subject_entity_id="23",
            subject_selector=subject_selector)
        claim = Claim(text="25", kind="observed", evidence_ids=["ev"],
                      output_bindings=[binding])
        with pytest.raises(ValueError, match="direct row child"):
            admit_verified_claim_bindings(TaskSpec(goal="x",mode="quick",
                deliverable="x",requested_outputs=["PTS"],entities=[lebron]),
                execution, DraftReport(sections=[],claims=[claim]), VerifiedClaim(
                    claim_index=0,claim=claim,evidence_ids=["ev"],output_bindings=[binding]))
    reject({"lebron":{"PLAYER_ID":"30","stats":{"PTS":25}},
            "curry":{"PLAYER_ID":"23","stats":{"PTS":30}}},
           "rows.lebron.stats.PTS", "rows.curry.PLAYER_ID", "rows")
    reject([{"PLAYER_ID":"30","stats":{"PTS":25}},
            {"PLAYER_ID":"23","stats":{"PTS":30}}],
           "rows[0].stats.PTS", "rows[1].PLAYER_ID", "rows")
