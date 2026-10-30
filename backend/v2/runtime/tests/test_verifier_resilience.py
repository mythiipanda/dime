from __future__ import annotations

import pytest
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


@pytest.fixture
def anyio_backend():
    return "asyncio"
