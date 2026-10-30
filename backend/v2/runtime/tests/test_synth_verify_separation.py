from __future__ import annotations

import pytest
from v2.contracts import Claim, ClaimKind, DraftReport, Plan, PlanNode, RunMode, TaskSpec, VerificationReport, VerificationStatus
from v2.runtime.interfaces import freeze_draft, freeze_evidence, freeze_evidence_map, reject_self_verified_draft, validate_repair_evidence_closed, RepairAddsEvidenceError


def _draft() -> DraftReport:
    return DraftReport(sections=["Answer"], claims=[Claim(text="42", kind=ClaimKind.OBSERVED, evidence_ids=["evidence:facts"])])

def _evidence_map():
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    envelope = EvidenceEnvelope(evidence_id="evidence:facts", capability="fake", source="fake", observed_at=datetime.now(UTC), rows={"value": 42})
    return {"evidence:facts": envelope}

def test_verifier_draft_mutation_fails() -> None:
    frozen = freeze_draft(_draft())
    with pytest.raises(Exception):
        frozen.sections.append("smuggled")
    with pytest.raises(Exception):
        frozen.claims[0].text = "smuggled"
    with pytest.raises(Exception):
        frozen.claims.append(frozen.claims[0])
    with pytest.raises(Exception):
        frozen.gaps.append("smuggled")
    assert frozen.sections == ("Answer",)
    assert frozen.claims[0].text == "42"

def test_verifier_evidence_mutation_fails() -> None:
    frozen = freeze_evidence_map(_evidence_map())
    with pytest.raises(Exception):
        frozen["evidence:new"] = list(frozen.values())[0]
    envelope = frozen["evidence:facts"]
    with pytest.raises(Exception):
        envelope.capability = "smuggled"
    with pytest.raises(Exception):
        envelope.units["smuggled"] = "x"
    with pytest.raises(Exception):
        envelope.warnings.append("smuggled")
    with pytest.raises(Exception):
        envelope.model_copy(update={"capability": "smuggled"})
    assert envelope.capability == "fake"

def test_verifier_evidence_rows_mutation_fails() -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    envelope = EvidenceEnvelope(evidence_id="e", capability="fake", source="fake", observed_at=datetime.now(UTC), rows=[{"value": 1}])
    frozen = freeze_evidence(envelope)
    with pytest.raises(Exception):
        frozen.rows.append({"value": 2})
    with pytest.raises(Exception):
        frozen.rows[0]["value"] = 2

def test_repair_cannot_add_evidence_id() -> None:
    admitted = _evidence_map()
    repaired = DraftReport(sections=["Answer"], claims=[Claim(text="42 plus extra", kind=ClaimKind.OBSERVED, evidence_ids=["evidence:smuggled"])])
    with pytest.raises(RepairAddsEvidenceError, match="evidence:smuggled"):
        validate_repair_evidence_closed(admitted, repaired)

def test_repair_may_drop_claims() -> None:
    admitted = _evidence_map()
    repaired = DraftReport(sections=["Answer"], claims=[])
    validate_repair_evidence_closed(admitted, repaired)

def test_self_verified_draft_rejected() -> None:
    with pytest.raises(ValueError, match="cannot mark its own claims verified"):
        reject_self_verified_draft({"sections": ["A"], "claims": [], "status": "pass"})
    with pytest.raises(ValueError, match="cannot mark its own claims verified"):
        reject_self_verified_draft({"sections": ["A"], "claims": [{"text": "x", "supported": True}]})
    with pytest.raises(ValueError, match="cannot mark its own claims verified"):
        reject_self_verified_draft(VerificationReport(status=VerificationStatus.PASS))


@pytest.fixture
def anyio_backend():
    return "asyncio"
