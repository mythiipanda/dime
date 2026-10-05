from __future__ import annotations

import pytest
from v2.adapters.models import load_model_budgets, route_budgets
from v2.contracts import (
    Claim,
    ClaimKind,
    ClaimResult,
    DraftReport,
    GapKind,
    Plan,
    PlanNode,
    RunMode,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime import FakeCapability, PlanExecutor, Runtime


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Intake:
    async def understand(self, request: str) -> TaskSpec:
        return TaskSpec(goal=request, mode=RunMode.QUICK, deliverable="text")


class Planner:
    async def plan(self, task: TaskSpec) -> Plan:
        return Plan(nodes=[PlanNode(id="facts", description="facts", capability_hints=["fake"])])


class Synthesizer:
    async def synthesize(self, task, evidence) -> DraftReport:
        return DraftReport(
            sections=["Answer"],
            claims=[Claim(text="42", kind=ClaimKind.OBSERVED, evidence_ids=["evidence:facts"])],
        )


class PassingMechanical:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[{"claim_index": index, "supported": True} for index, _claim in enumerate(draft.claims)],
        )


class RepairMechanical:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(
            status=VerificationStatus.REPAIR,
            claim_results=[{"claim_index": index, "supported": True} for index, _claim in enumerate(draft.claims)],
            missing_branches=["factual branch needs rewrite"],
            repair_instructions=["rewrite the factual branch"],
        )


class FailingSemantic:
    async def verify(self, task, draft, evidence):
        raise RuntimeError("provider unavailable")


class UncertainSemantic:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[
                ClaimResult(claim_index=index, supported=True, uncertain=True, evidence_spans=["42"])
                for index, _claim in enumerate(draft.claims)
            ],
        )


def make_runtime(mechanical, semantic) -> Runtime:
    return Runtime(
        intake=Intake(),
        planner=Planner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=Synthesizer(),
        mechanical_verifier=mechanical,
        semantic_verifier=semantic,
    )


def test_semantic_route_policy_matches_planner_grade_resilience() -> None:
    policy = route_budgets(None, "semantic_verifier")
    assert policy == route_budgets(None, "planner")
    assert policy.attempt_timeout_s is None
    assert policy.total_budget_s is None
    assert set(vars(policy)) == {"attempt_timeout_s", "total_budget_s"}
    assert set(load_model_budgets().routes) <= {
        "intake", "requirement_review", "planner", "synthesizer",
        "semantic_verifier", "repair"}


@pytest.mark.anyio
async def test_semantic_failure_with_passing_mechanical_marks_judge_unavailable() -> None:
    result = await make_runtime(PassingMechanical(), FailingSemantic()).run("answer")
    assert result.verification.status == VerificationStatus.PARTIAL
    kinds = [gap.kind for gap in result.gaps]
    assert GapKind.JUDGE_UNAVAILABLE in kinds
    assert result.verified_claims[0].claim.text == "42"


@pytest.mark.anyio
async def test_semantic_failure_with_repair_mechanical_marks_judge_unavailable() -> None:
    result = await make_runtime(RepairMechanical(), FailingSemantic()).run("answer")
    assert result.verification.status == VerificationStatus.PARTIAL
    kinds = [gap.kind for gap in result.gaps]
    assert GapKind.JUDGE_UNAVAILABLE in kinds


@pytest.mark.anyio
async def test_judge_unavailable_gap_reaches_plain_language_answer_text() -> None:
    from v2.api.routes import _answer_text

    result = await make_runtime(RepairMechanical(), FailingSemantic()).run("answer")
    assert any(gap.kind == GapKind.JUDGE_UNAVAILABLE for gap in result.gaps)
    text = _answer_text(result)
    assert "I couldn't double-check this answer, so treat the details with extra care." in text


def test_verification_gaps_maps_judge_marker_not_missing_evidence() -> None:
    from v2.runtime.loop import JUDGE_UNAVAILABLE_BRANCH, _verification_gaps

    report = VerificationReport(status="partial", missing_branches=[JUDGE_UNAVAILABLE_BRANCH])
    gaps = _verification_gaps(DraftReport(sections=[], claims=[]), report)
    assert len(gaps) == 1
    assert gaps[0].kind == GapKind.JUDGE_UNAVAILABLE


@pytest.mark.anyio
async def test_uncertain_verdict_blocks_pass_and_withholds_claim() -> None:
    result = await make_runtime(PassingMechanical(), UncertainSemantic()).run("answer")
    assert result.verification.status == VerificationStatus.PARTIAL
    assert result.verified_claims == []
    assert result.gaps != []


def test_claim_result_accepts_evidence_spans_and_uncertain() -> None:
    item = ClaimResult(claim_index=0, supported=True, evidence_spans=["42"], uncertain=True)
    assert item.evidence_spans == ["42"]
    assert item.uncertain is True
    assert ClaimResult.model_validate(item.model_dump()) == item


def test_semantic_report_and_merge_round_trip_new_fields() -> None:
    from v2.runtime.verifier import merge_verification_reports, validate_semantic_report

    mechanical = VerificationReport(
        status="pass",
        claim_results=[ClaimResult(claim_index=0, supported=True)],
    )
    semantic = validate_semantic_report(
        {
            "status": "pass",
            "claim_results": [
                {"claim_index": 0, "supported": True, "evidence_spans": ["42"], "uncertain": True}
            ],
            "missing_branches": [],
            "contradictions": [],
            "repair_instructions": [],
        }
    )
    assert semantic.claim_results[0].evidence_spans == ["42"]
    assert semantic.claim_results[0].uncertain is True
    merged = merge_verification_reports(mechanical, semantic)
    assert merged.claim_results[0].evidence_spans == ["42"]
    assert merged.claim_results[0].uncertain is True


def test_loop_merge_preserves_evidence_spans_and_uncertain() -> None:
    from v2.runtime.loop import _merge_verification

    mechanical = VerificationReport(
        status="pass",
        claim_results=[ClaimResult(claim_index=0, supported=True, evidence_spans=["mech"])],
    )
    semantic = VerificationReport(
        status="pass",
        claim_results=[ClaimResult(claim_index=0, supported=True, evidence_spans=["sem"], uncertain=True)],
    )
    merged = _merge_verification(mechanical, semantic)
    assert merged.claim_results[0].uncertain is True
    assert merged.claim_results[0].evidence_spans == ["mech", "sem"]
