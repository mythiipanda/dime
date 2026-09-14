from __future__ import annotations

import pytest
from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    Plan,
    PlanNode,
    RunMode,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime import FakeCapability, PlanExecutor, Runtime


class Intake:
    async def understand(self, request: str) -> TaskSpec:
        return TaskSpec(goal=request, mode=RunMode.QUICK, deliverable="text")


class Planner:
    async def plan(self, task: TaskSpec) -> Plan:
        return Plan(
            nodes=[
                PlanNode(
                    id="facts",
                    description="facts",
                    capability_hints=["fake"],
                    completion_test="has facts",
                )
            ]
        )


class Synthesizer:
    async def synthesize(self, task, evidence) -> DraftReport:
        return DraftReport(
            sections=["Answer"],
            claims=[
                Claim(
                    text="42", kind=ClaimKind.OBSERVED, evidence_ids=["evidence:facts"]
                )
            ],
        )


class SequenceVerifier:
    def __init__(self, *statuses: VerificationStatus) -> None:
        self.statuses = list(statuses)

    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(status=self.statuses.pop(0))


class Repairer:
    async def repair(self, task, draft, evidence, verification) -> DraftReport:
        return draft.model_copy(update={"sections": ["Repaired"]})


def runtime(mechanical, semantic, repairer=None) -> Runtime:
    return Runtime(
        intake=Intake(),
        planner=Planner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=Synthesizer(),
        mechanical_verifier=mechanical,
        semantic_verifier=semantic,
        repairer=repairer,
    )


@pytest.mark.asyncio
async def test_passes_verified_quick_slice() -> None:
    result = await runtime(
        SequenceVerifier(VerificationStatus.PASS),
        SequenceVerifier(VerificationStatus.PASS),
    ).run("answer")

    assert result.verification.status == VerificationStatus.PASS
    assert result.repaired is False


@pytest.mark.asyncio
async def test_repairs_once_and_reverifies() -> None:
    result = await runtime(
        SequenceVerifier(VerificationStatus.REPAIR, VerificationStatus.PASS),
        SequenceVerifier(VerificationStatus.PASS, VerificationStatus.PASS),
        Repairer(),
    ).run("answer")

    assert result.repaired is True
    assert result.draft.sections == ["Repaired"]
    assert result.verification.status == VerificationStatus.PASS


@pytest.mark.asyncio
async def test_exhausted_repair_returns_named_partial() -> None:
    class RejectingVerifier:
        async def verify(self, task, draft, evidence):
            return VerificationReport(
                status=VerificationStatus.REPAIR,
                missing_branches=["clutch context"],
                repair_instructions=["add clutch evidence"],
            )

    result = await runtime(RejectingVerifier(), RejectingVerifier(), Repairer()).run(
        "answer"
    )

    assert result.verification.status == VerificationStatus.PARTIAL
    assert result.draft.gaps == ["clutch context", "add clutch evidence"]
