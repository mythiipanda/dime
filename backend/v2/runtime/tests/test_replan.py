from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    EvidenceEnvelope,
    Plan,
    PlanNode,
    PlanStatus,
    RunMode,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime import Runtime
from v2.runtime.models import ExecutionResult


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_task() -> TaskSpec:
    return TaskSpec(
        goal="assess scoring",
        mode=RunMode.QUICK,
        deliverable="text",
        requirements=[
            {"id": "scoring", "description": "scoring production",
             "capability_options": ["cap_a", "cap_b"]},
            {"id": "efficiency", "description": "scoring efficiency",
             "capability_options": ["cap_c", "cap_d"]},
        ],
    )


def recovery_nodes() -> list[PlanNode]:
    return [
        PlanNode(
            id="b1", description="second scoring attempt",
            capability_hints=["cap_b"], covers_requirement_ids=["scoring"],
        ),
        PlanNode(
            id="d1", description="second efficiency attempt",
            capability_hints=["cap_d"], covers_requirement_ids=["efficiency"],
        ),
    ]


def fail_all(plan: Plan) -> ExecutionResult:
    return ExecutionResult(
        plan=Plan(nodes=[
            node.model_copy(update={"status": PlanStatus.FAILED})
            for node in plan.nodes
        ]),
        attempts={node.id: 1 for node in plan.nodes},
        errors={node.id: [f"RuntimeError: {node.id} failed"]
                for node in plan.nodes},
    )


def complete_all(plan: Plan) -> ExecutionResult:
    return ExecutionResult(
        plan=Plan(nodes=[
            node.model_copy(update={"status": PlanStatus.COMPLETE})
            for node in plan.nodes
        ]),
        evidence_by_node={
            node.id: EvidenceEnvelope(
                evidence_id=f"evidence:{node.id}",
                capability=node.capability_hints[0],
                source="fake",
                observed_at=datetime.now(UTC),
                rows={"value": 1},
            )
            for node in plan.nodes
        },
        attempts={node.id: 1 for node in plan.nodes},
    )


class Intake:
    async def understand(self, request: str) -> TaskSpec:
        return make_task()


class Planner:
    def __init__(self, recovery: list[PlanNode]) -> None:
        self.calls: list = []
        self.recovery = recovery

    async def plan(self, task: TaskSpec, failure_context=None) -> Plan:
        self.calls.append(failure_context)
        if failure_context is None:
            return Plan(nodes=[
                PlanNode(
                    id="a1", description="first scoring attempt",
                    capability_hints=["cap_a"],
                    covers_requirement_ids=["scoring"],
                ),
                PlanNode(
                    id="c1", description="first efficiency attempt",
                    capability_hints=["cap_c"],
                    covers_requirement_ids=["efficiency"],
                ),
            ])
        return Plan(nodes=[
            node.model_copy() for node in self.recovery
        ])


class FailThenCompleteExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, task, plan, run_id=None, resume=True) -> ExecutionResult:
        self.calls += 1
        if self.calls == 1:
            return fail_all(plan)
        return complete_all(plan)


class AlwaysFailExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, task, plan, run_id=None, resume=True) -> ExecutionResult:
        self.calls += 1
        return fail_all(plan)


class FailsThenSucceeds:
    def __init__(self, name: str, message: str, failures: int) -> None:
        self.name = name
        self._message = message
        self._remaining = failures

    async def execute(self, node, task, evidence):
        from v2.runtime import FakeCapability

        if self._remaining:
            self._remaining -= 1
            raise RuntimeError(self._message)
        return await FakeCapability(self.name, {"value": 1}).execute(
            node, task, evidence)


def recovery_capabilities(message: str, *, cap_a_failures: int = 99) -> dict:
    return {
        "cap_a": FailsThenSucceeds("cap_a", message, cap_a_failures),
        "cap_c": FailsThenSucceeds("cap_c", message, 99),
        "cap_b": FailsThenSucceeds("cap_b", message, 0),
        "cap_d": FailsThenSucceeds("cap_d", message, 0),
    }


class PartialExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, task, plan, run_id=None, resume=True) -> ExecutionResult:
        self.calls += 1
        finished = plan.nodes[0].model_copy(
            update={"status": PlanStatus.COMPLETE})
        rest = [node.model_copy(update={"status": PlanStatus.FAILED})
                for node in plan.nodes[1:]]
        return ExecutionResult(
            plan=Plan(nodes=[finished, *rest]),
            evidence_by_node={
                finished.id: EvidenceEnvelope(
                    evidence_id=f"evidence:{finished.id}",
                    capability=finished.capability_hints[0],
                    source="fake",
                    observed_at=datetime.now(UTC),
                    rows={"value": 1},
                )
            },
            attempts={node.id: 1 for node in plan.nodes},
            errors={node.id: [f"RuntimeError: {node.id} failed"]
                    for node in rest},
        )


class Synthesizer:
    def __init__(self) -> None:
        self.seen: list = []

    async def synthesize(self, task, evidence) -> DraftReport:
        self.seen = list(evidence)
        if not evidence:
            return DraftReport(sections=["No answer"], claims=[])
        return DraftReport(
            sections=["Answer"],
            claims=[Claim(
                text="Recovered value is 1.",
                kind=ClaimKind.OBSERVED,
                evidence_ids=[evidence[0].evidence_id],
            )],
        )


class PassVerifier:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[
                {"claim_index": index, "supported": True}
                for index, _claim in enumerate(draft.claims)
            ],
        )


def build_runtime(planner, executor, synthesizer) -> Runtime:
    return Runtime(
        intake=Intake(),
        planner=planner,
        executor=executor,
        synthesizer=synthesizer,
        mechanical_verifier=PassVerifier(),
        semantic_verifier=PassVerifier(),
    )


@pytest.mark.anyio
async def test_total_failure_replans_once_and_synthesizes_recovery_evidence() -> None:
    planner = Planner(recovery_nodes())
    executor = FailThenCompleteExecutor()
    synthesizer = Synthesizer()
    result = await build_runtime(
        planner, executor, synthesizer).run("assess scoring")

    assert len(planner.calls) == 2
    assert executor.calls == 2
    assert [item.evidence_id for item in synthesizer.seen] == [
        "evidence:b1", "evidence:d1"]
    assert result.verification.status == VerificationStatus.PASS
    assert [item.claim.text for item in result.verified_claims] == [
        "Recovered value is 1."]


@pytest.mark.anyio
async def test_checkpointed_recovery_executes_the_replan_instead_of_raising(tmp_path) -> None:
    from v2.runtime import PlanExecutor
    from v2.runtime.checkpoints import FileCheckpointStore

    message = ("AdapterError: get_ratings: Team ratings for the 2024-25 "
               "season are not available. Available seasons: 2025-26.")
    planner = Planner(recovery_nodes())
    executor = PlanExecutor(
        recovery_capabilities(message),
        checkpoint_store=FileCheckpointStore(tmp_path / "checkpoints"),
    )
    synthesizer = Synthesizer()
    result = await build_runtime(
        planner, executor, synthesizer).run("assess scoring", run_id="turn-1")

    assert len(planner.calls) == 2
    assert [item.evidence_id for item in synthesizer.seen] == [
        "evidence:b1", "evidence:d1"]
    assert result.verification.status == VerificationStatus.PASS
    assert [item.claim.text for item in result.verified_claims] == [
        "Recovered value is 1."]
    failed = {
        node.id for node in result.execution.plan.nodes
        if node.status.value == "failed"
    }
    assert failed == {"a1", "c1"}
    assert result.execution.errors["a1"] == [f"RuntimeError: {message}"]
    assert not (tmp_path / "checkpoints" / "turn-1.json").exists()


@pytest.mark.anyio
async def test_checkpointed_recovery_reenters_the_same_replanned_node(tmp_path) -> None:
    from v2.runtime import PlanExecutor
    from v2.runtime.checkpoints import FileCheckpointStore

    message = "AdapterError: silver_team_ratings has no 2024-25 rows"
    planner = Planner([
        PlanNode(
            id="a1", description="same scoring node replanned",
            capability_hints=["cap_a"], covers_requirement_ids=["scoring"],
        ),
        PlanNode(
            id="d1", description="second efficiency attempt",
            capability_hints=["cap_d"], covers_requirement_ids=["efficiency"],
        ),
    ])
    executor = PlanExecutor(
        recovery_capabilities(message, cap_a_failures=1),
        checkpoint_store=FileCheckpointStore(tmp_path / "checkpoints"),
    )
    synthesizer = Synthesizer()
    result = await build_runtime(
        planner, executor, synthesizer).run("assess scoring", run_id="turn-1")

    assert len(planner.calls) == 2
    assert [item.evidence_id for item in synthesizer.seen] == [
        "evidence:a1-replan2", "evidence:d1"]
    assert result.verification.status == VerificationStatus.PASS
    assert not (tmp_path / "checkpoints" / "turn-1.json").exists()


@pytest.mark.anyio
async def test_partial_completion_skips_replan() -> None:
    planner = Planner(recovery_nodes())
    executor = PartialExecutor()
    synthesizer = Synthesizer()
    await build_runtime(planner, executor, synthesizer).run("assess scoring")

    assert len(planner.calls) == 1
    assert executor.calls == 1


@pytest.mark.anyio
async def test_failure_context_lists_failed_nodes_reasons_and_remaining_options() -> None:
    planner = Planner(recovery_nodes())
    executor = FailThenCompleteExecutor()
    synthesizer = Synthesizer()
    await build_runtime(planner, executor, synthesizer).run("assess scoring")

    assert len(planner.calls) == 2
    assert planner.calls[0] is None
    context = planner.calls[1]
    json.dumps(context)
    by_requirement = {
        entry["requirement_id"]: entry for entry in context["requirements"]
    }
    assert set(by_requirement) == {"scoring", "efficiency"}
    assert by_requirement["scoring"]["failed_nodes"] == ["a1"]
    assert by_requirement["scoring"]["failure_reasons"] == [
        "RuntimeError: a1 failed"]
    assert by_requirement["scoring"]["remaining_capability_options"] == [
        "cap_b"]
    assert by_requirement["efficiency"]["failed_nodes"] == ["c1"]
    assert by_requirement["efficiency"]["failure_reasons"] == [
        "RuntimeError: c1 failed"]
    assert by_requirement["efficiency"]["remaining_capability_options"] == [
        "cap_d"]


@pytest.mark.anyio
async def test_failed_recovery_does_not_replan_again() -> None:
    planner = Planner(recovery_nodes())
    executor = AlwaysFailExecutor()
    synthesizer = Synthesizer()
    result = await build_runtime(
        planner, executor, synthesizer).run("assess scoring")

    assert len(planner.calls) == 2
    assert executor.calls == 2
    assert result.verification.status == VerificationStatus.PARTIAL
