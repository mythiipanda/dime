from __future__ import annotations

from datetime import UTC, datetime

import pytest

from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    EvidenceEnvelope,
    EvidenceRequirement,
    Plan,
    PlanNode,
    RunMode,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime import FakeCapability, PlanExecutor, Runtime

MECHANICAL_INSTRUCTION = "Mechanical gate requested repair."
JUDGE_UNAVAILABLE = (
    "Semantic verification was unavailable; published claims passed deterministic verification."
)


class StubIntake:
    async def understand(self, request: str) -> TaskSpec:
        return _task()


class StubPlanner:
    async def plan(self, task: TaskSpec) -> Plan:
        return Plan(nodes=[PlanNode(
            id="n1",
            description="Read fixture value",
            capability_hints=["fixture"],
            covers_requirement_ids=["facts"],
        )])


class StubSynthesizer:
    async def synthesize(self, task, evidence) -> DraftReport:
        return _draft()


class Mechanical:
    def __init__(self, status: VerificationStatus) -> None:
        self.status = status
        self.calls = 0

    async def verify(self, task, draft, evidence) -> VerificationReport:
        self.calls += 1
        return VerificationReport(
            status=self.status,
            claim_results=[{"claim_index": 0, "supported": True}],
            repair_instructions=(
                [MECHANICAL_INSTRUCTION]
                if self.status == VerificationStatus.REPAIR else []
            ),
        )


class Semantic:
    def __init__(self, outcome: str = "pass") -> None:
        self.outcome = outcome
        self.calls = 0

    async def verify(self, task, draft, evidence) -> VerificationReport:
        self.calls += 1
        if self.outcome == "raise":
            raise RuntimeError("fixture semantic verifier failure")
        if self.outcome == "unsupported":
            return VerificationReport(
                status=VerificationStatus.PARTIAL,
                claim_results=[{
                    "claim_index": 0,
                    "supported": False,
                    "reasons": ["semantic review rejected this claim"],
                }],
            )
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[{"claim_index": 0, "supported": True}],
        )


def _task() -> TaskSpec:
    return TaskSpec(
        goal="Report the fixture value.",
        mode=RunMode.QUICK,
        deliverable="The fixture value.",
        requirements=[EvidenceRequirement(
            id="facts",
            description="Read the fixture value.",
            capability_options=["fixture"],
        )],
    )


def _draft() -> DraftReport:
    return DraftReport(
        sections=["Ada's fixture value is 1."],
        claims=[Claim(
            text="Ada's fixture value is 1.",
            kind=ClaimKind.OBSERVED,
            evidence_ids=["evidence:n1"],
        )],
    )


def _evidence() -> EvidenceEnvelope:
    return EvidenceEnvelope(
        evidence_id="evidence:n1",
        capability="fixture",
        source="fake",
        observed_at=datetime.now(UTC),
        rows=[{"PLAYER": "Ada", "VALUE": 1}],
    )


def _runtime(mechanical: Mechanical, semantic: Semantic) -> Runtime:
    return Runtime(
        intake=StubIntake(),
        planner=StubPlanner(),
        executor=PlanExecutor({
            "fixture": FakeCapability("fixture", [{"PLAYER": "Ada", "VALUE": 1}]),
        }),
        synthesizer=StubSynthesizer(),
        mechanical_verifier=mechanical,
        semantic_verifier=semantic,
        repair_attempts=0,
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_semantic_review_runs_but_cannot_clear_mechanical_repair() -> None:
    mechanical = Mechanical(VerificationStatus.REPAIR)
    semantic = Semantic()
    runtime = _runtime(mechanical, semantic)
    task, draft, evidence = _task(), _draft(), {"evidence:n1": _evidence()}
    draft_before = draft.model_dump()
    evidence_before = {key: item.model_dump() for key, item in evidence.items()}

    report = await runtime._verify(task, draft, evidence)

    assert semantic.calls == 1
    assert report.status == VerificationStatus.REPAIR
    assert report.repair_instructions == [MECHANICAL_INSTRUCTION]
    assert JUDGE_UNAVAILABLE not in report.missing_branches
    assert draft.model_dump() == draft_before
    assert {key: item.model_dump() for key, item in evidence.items()} == evidence_before


@pytest.mark.anyio
async def test_zero_repair_run_keeps_mechanical_failure_visible() -> None:
    mechanical = Mechanical(VerificationStatus.REPAIR)
    semantic = Semantic()

    result = await _runtime(mechanical, semantic).run("fixture request")

    assert semantic.calls == 1
    assert result.verification.status == VerificationStatus.PARTIAL
    assert result.verification.repair_instructions == [MECHANICAL_INSTRUCTION]
    assert any(gap.message == MECHANICAL_INSTRUCTION for gap in result.gaps)
    assert result.verified_claims


@pytest.mark.anyio
async def test_semantic_rejection_vetoes_publication_after_mechanical_support() -> None:
    mechanical = Mechanical(VerificationStatus.REPAIR)
    semantic = Semantic("unsupported")

    result = await _runtime(mechanical, semantic).run("fixture request")

    assert semantic.calls == 1
    assert result.verification.status == VerificationStatus.PARTIAL
    assert result.verification.claim_results[0].supported is False
    assert result.verified_claims == []
    assert MECHANICAL_INSTRUCTION in [gap.message for gap in result.gaps]


@pytest.mark.anyio
async def test_semantic_failure_preserves_mechanical_repair_and_marks_actual_failure() -> None:
    mechanical = Mechanical(VerificationStatus.REPAIR)
    semantic = Semantic("raise")
    task, draft, evidence = _task(), _draft(), {"evidence:n1": _evidence()}
    draft_before = draft.model_dump()
    evidence_before = {key: item.model_dump() for key, item in evidence.items()}

    report = await _runtime(mechanical, semantic)._verify(task, draft, evidence)

    assert semantic.calls == 1
    assert report.status == VerificationStatus.REPAIR
    assert report.repair_instructions == [MECHANICAL_INSTRUCTION]
    assert JUDGE_UNAVAILABLE in report.missing_branches
    assert draft.model_dump() == draft_before
    assert {key: item.model_dump() for key, item in evidence.items()} == evidence_before


@pytest.mark.anyio
async def test_nonrepair_verification_behavior_is_unchanged() -> None:
    mechanical = Mechanical(VerificationStatus.PASS)
    semantic = Semantic()

    result = await _runtime(mechanical, semantic).run("fixture request")

    assert semantic.calls == 1
    assert result.verification.status == VerificationStatus.PASS
    assert result.verification.repair_instructions == []
