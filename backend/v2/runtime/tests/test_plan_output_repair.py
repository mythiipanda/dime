from __future__ import annotations

from datetime import UTC, datetime

import pytest
from v2.adapters.models import PlanOutputError
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
        goal="assists",
        mode=RunMode.QUICK,
        deliverable="text",
        requirements=[
            {"id": "r1", "description": "assists",
             "capability_options": ["cap_a"]},
        ],
    )

class Intake:
    async def understand(self, request: str) -> TaskSpec:
        return make_task()

class Planner:
    def __init__(self) -> None:
        self.calls: list = []

    async def plan(self, task: TaskSpec, failure_context=None) -> Plan:
        self.calls.append(failure_context)
        if failure_context is None:
            raise PlanOutputError(
                "PLAN_OUTPUT_UNRESOLVABLE: requested output 'AST' "
                "does not resolve against capability 'cap_a'",
                output_id="AST", capability="cap_a",
                vocabulary=["APG"], node_id="n1",
            )
        return Plan(nodes=[
            PlanNode(
                id="n1", description="ok",
                capability_hints=["cap_a"],
                covers_requirement_ids=["r1"],
            )
        ])

class Executor:
    async def execute(self, task, plan, run_id=None, resume=True) -> ExecutionResult:
        return ExecutionResult(
            plan=Plan(nodes=[
                n.model_copy(update={"status": PlanStatus.COMPLETE})
                for n in plan.nodes
            ]),
            evidence_by_node={
                plan.nodes[0].id: EvidenceEnvelope(
                    evidence_id="evidence:n1",
                    capability="cap_a",
                    source="fake",
                    observed_at=datetime.now(UTC),
                    rows={"APG": 11.6},
                )
            },
            attempts={plan.nodes[0].id: 1},
        )

class Synthesizer:
    async def synthesize(self, task, evidence) -> DraftReport:
        return DraftReport(
            sections=["Answer"],
            claims=[Claim(
                text="APG is 11.6.",
                kind=ClaimKind.OBSERVED,
                evidence_ids=["evidence:n1"],
            )],
        )

class PassVerifier:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[
                {"claim_index": i, "supported": True}
                for i, _ in enumerate(draft.claims)
            ],
        )

@pytest.mark.anyio
async def test_plan_output_error_retries_planner_with_failure_context() -> None:
    planner = Planner()
    runtime = Runtime(
        intake=Intake(),
        planner=planner,
        executor=Executor(),
        synthesizer=Synthesizer(),
        mechanical_verifier=PassVerifier(),
        semantic_verifier=PassVerifier(),
    )
    result = await runtime.run("assists")
    assert result.verification.status == VerificationStatus.PASS
    assert planner.calls[0] is None
    assert "PLAN_OUTPUT_UNRESOLVABLE" in str(planner.calls[1])
