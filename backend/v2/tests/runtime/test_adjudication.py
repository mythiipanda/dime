from v2.contracts import (
    Claim, ClaimResult, DraftReport, VerificationReport,
)
from v2.runtime.loop import _verification_gaps, _verified_claims


def test_adjudication_keeps_model_prose_and_marks_supported_claims():
    draft = DraftReport(sections=["Answer"], claims=[
        Claim(text="Boston won 61 games.", kind="observed", evidence_ids=["ev"]),
        Claim(text="Boston won 62 games.", kind="observed", evidence_ids=["ev"]),
    ])
    report = VerificationReport(status="partial", claim_results=[
        ClaimResult(claim_index=0, supported=True),
        ClaimResult(claim_index=1, supported=False, reasons=["uncited numeral 62"]),
    ])
    claims = _verified_claims(draft, report)
    assert [item.claim.text for item in claims] == ["Boston won 61 games."]
    assert claims[0].evidence_ids == ["ev"]
    gaps = _verification_gaps(draft, report)
    assert gaps[0].kind == "unsupported_claim"
    assert gaps[0].blocks == ["claim:1"]
