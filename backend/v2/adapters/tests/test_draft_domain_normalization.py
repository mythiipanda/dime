from datetime import UTC, datetime

from v2.adapters.capabilities import CAPABILITIES
from v2.adapters.core import build_envelope
from v2.adapters.models import _validate_draft
from v2.contracts import Claim, DraftReport, EvidenceOutputBinding

def _envelope():
    return build_envelope(
        CAPABILITIES["team_four_factors"],
        {"season": "2025-26"},
        {"ok": True, "rows": [{
            "TEAM_ID": 1610612760,
            "TEAM_NAME": "Oklahoma City Thunder",
            "SEASON": "2025-26",
            "EFG_PCT": 0.557,
            "FT_RATE": 0.181,
            "ORB_PCT": 0.264,
            "TOV_PCT": 0.118,
        }], "meta": {
            "source": "warehouse",
            "season": "2025-26",
            "warehouse_id": "frozen-eval",
            "warehouse_sha256": "a" * 64,
        }},
        entities=None,
        observed_at=datetime.now(UTC),
    )

def _draft(envelope, domain):
    binding = EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id="team_four_factors_req",
        output_id="EFG_PCT",
        node_id="node_team_four_factors",
        evidence_id=envelope.evidence_id,
        selector="rows[0].EFG_PCT",
        row_selector="rows[0]",
        value={"kind": "float", "value": 0.557},
        subject_entity_type="team",
        subject_entity_id="1610612760",
        subject_selector="rows[0].TEAM_ID",
        unit={"kind": "unitless"},
        domain=domain,
    )
    claim = Claim(
        text="The Thunder posted a 0.557 effective field-goal percentage.",
        kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=[binding],
    )
    return DraftReport(sections=["Four factors"], claims=[claim])

def test_generalized_domain_is_normalized_to_cited_capability():
    envelope = _envelope()
    draft = _validate_draft(_draft(envelope, "sports"), [envelope])
    assert draft.claims[0].output_bindings[0].domain == "team_four_factors"

def test_foreign_domain_is_normalized_from_cited_evidence():
    envelope = _envelope()
    draft = _validate_draft(_draft(envelope, "football"), [envelope])
    assert draft.claims[0].output_bindings[0].domain == "team_four_factors"

def test_domain_equal_to_capability_domain_is_preserved():
    envelope = _envelope()
    draft = _validate_draft(_draft(envelope, "basketball"), [envelope])
    assert draft.claims[0].output_bindings[0].domain == "basketball"

def test_domain_equal_to_capability_name_is_preserved():
    envelope = _envelope()
    draft = _validate_draft(_draft(envelope, "team_four_factors"), [envelope])
    assert draft.claims[0].output_bindings[0].domain == "team_four_factors"
