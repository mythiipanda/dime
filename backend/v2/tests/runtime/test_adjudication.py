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


def test_verified_claim_carries_per_claim_provenance_for_mixed_sources():
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope

    draft = DraftReport(sections=["Comparison"], claims=[
        Claim(text="SGA scored 31.1 PPG.", kind="observed",
              evidence_ids=["warehouse-sga"]),
        Claim(text="Luka scored 33.5 PPG.", kind="observed",
              evidence_ids=["fallback-luka"]),
    ])
    report = VerificationReport(status="pass", claim_results=[
        ClaimResult(claim_index=0, supported=True),
        ClaimResult(claim_index=1, supported=True),
    ])
    evidence = {
        "warehouse-sga": EvidenceEnvelope(
            evidence_id="warehouse-sga", capability="player_report",
            source="warehouse:silver_player_season", observed_at=datetime.now(UTC),
            rows={"player": "SGA", "ppg": 31.1}),
        "fallback-luka": EvidenceEnvelope(
            evidence_id="fallback-luka", capability="player_report",
            source="fallback:basketball-reference", observed_at=datetime.now(UTC),
            rows={"player": "Luka", "ppg": 33.5}),
    }
    claims = _verified_claims(draft, report, evidence)
    assert claims[0].sources[0].source.startswith("warehouse:")
    assert claims[1].sources[0].source.startswith("fallback:")
    assert claims[0].sources != claims[1].sources


def test_execution_errors_surface_as_typed_gaps() -> None:
    draft = DraftReport(sections=["Trade"], claims=[])
    report = VerificationReport(status="partial")
    gaps = _verification_gaps(
        draft, report,
        {"salary": ["AdapterError: cap ledger unavailable"]},
    )
    assert len(gaps) == 1
    assert gaps[0].kind == "execution_failure"
    assert gaps[0].message == "AdapterError: cap ledger unavailable"
    assert gaps[0].blocks == ["node:salary"]
