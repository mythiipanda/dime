from __future__ import annotations

import pytest
from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    Plan,
    PlanNode,
    PlanStatus,
    RunMode,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime import FakeCapability, PlanExecutor, Runtime

@pytest.fixture
def anyio_backend():
    return "asyncio"

def make_task() -> TaskSpec:
    return TaskSpec(
        goal="assists",
        mode=RunMode.QUICK,
        deliverable="text",
        required_evidence=["fake"],
        requirements=[
            {"id": "r1", "description": "assists",
             "capability_options": ["fake"]},
        ],
    )

class Intake:
    async def understand(self, request: str) -> TaskSpec:
        return make_task()

class UnderCoveringPlanner:
    def __init__(self) -> None:
        self.calls: list = []

    async def plan(self, task: TaskSpec, failure_context=None) -> Plan:
        self.calls.append(failure_context)
        if failure_context is None:
            return Plan(nodes=[])
        return Plan(nodes=[
            PlanNode(
                id="n1",
                description="assists",
                capability_hints=["fake"],
                covers_requirement_ids=["r1"],
            )
        ])

class StubPlanner:
    def __init__(self) -> None:
        self.calls: list = []

    async def plan(self, task: TaskSpec) -> Plan:
        self.calls.append(None)
        return Plan(nodes=[])

class Synthesizer:
    async def synthesize(self, task, evidence) -> DraftReport:
        return DraftReport(
            sections=["Answer"],
            claims=[Claim(
                text="11.6 assists.",
                kind=ClaimKind.OBSERVED,
                evidence_ids=["evidence:n1"],
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

def runtime(planner) -> Runtime:
    return Runtime(
        intake=Intake(),
        planner=planner,
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=Synthesizer(),
        mechanical_verifier=PassVerifier(),
        semantic_verifier=PassVerifier(),
    )

@pytest.mark.anyio
async def test_uncovered_plan_retries_the_planner_with_the_coverage_error() -> None:
    planner = UnderCoveringPlanner()

    result = await runtime(planner).run("assists")

    assert result.verification.status == VerificationStatus.PASS
    assert planner.calls[0] is None
    assert "plan does not cover required evidence" in str(planner.calls[1])
    assert "r1" in str(planner.calls[1])
    assert [node.status for node in result.execution.plan.nodes] == [
        PlanStatus.COMPLETE]

@pytest.mark.anyio
async def test_a_planner_without_failure_context_still_fails_loud() -> None:
    planner = StubPlanner()

    with pytest.raises(ValueError, match="plan does not cover required evidence"):
        await runtime(planner).run("assists")

    assert planner.calls == [None]

class TwoRequirementTask:
    async def understand(self, request: str) -> TaskSpec:
        return TaskSpec(
            goal="assists and awards",
            mode=RunMode.QUICK,
            deliverable="text",
            required_evidence=["fake", "other"],
            requirements=[
                {"id": "r1", "description": "assists",
                 "capability_options": ["fake"]},
                {"id": "r2", "description": "awards",
                 "capability_options": ["other"]},
            ],
        )

class OneNodePlanner:
    async def plan(self, task: TaskSpec, failure_context=None) -> Plan:
        return Plan(nodes=[
            PlanNode(
                id="n1", description="assists",
                capability_hints=["fake"], covers_requirement_ids=["r1"],
            )
        ])

@pytest.mark.anyio
async def test_a_partial_plan_executes_and_gaps_the_uncovered_branch() -> None:
    runtime = Runtime(
        intake=TwoRequirementTask(),
        planner=OneNodePlanner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=Synthesizer(),
        mechanical_verifier=PassVerifier(),
        semantic_verifier=PassVerifier(),
    )

    result = await runtime.run("assists and awards")

    assert [node.status for node in result.execution.plan.nodes] == [
        PlanStatus.COMPLETE]
    assert [gap.kind for gap in result.gaps] == [
        "missing_evidence"]
    assert "awards" in " ".join(gap.message for gap in result.gaps)
