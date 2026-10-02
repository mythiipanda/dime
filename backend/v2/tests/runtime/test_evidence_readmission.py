from __future__ import annotations

from datetime import UTC, datetime

import pytest

from v2.adapters.capabilities import CAPABILITIES
from v2.adapters.core import build_envelope
from v2.contracts import (
    Claim,
    ClaimSource,
    DraftReport,
    EntityRef,
    EvidenceOutputBinding,
    EvidenceRequirement,
    Plan,
    PlanNode,
    SeasonRef,
    TaskSpec,
    VerifiedClaim,
)
from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings


def _meta():
    return {
        "source": "warehouse",
        "season": "2024-25",
        "warehouse_id": "frozen-eval",
        "warehouse_sha256": "a" * 64,
    }


def _bos_first_rows():
    return [
        {
            "TEAM_ID": 1610612738,
            "TEAM_NAME": "Boston Celtics",
            "TEAM": "BOS",
            "GP": 82,
            "W": 61,
            "L": 21,
            "OFF_RATING": 120.0,
            "DEF_RATING": 111.7,
            "NET_RATING": 8.3,
            "PACE": 99.0,
        },
        {
            "TEAM_ID": 1610612737,
            "TEAM_NAME": "Atlanta Hawks",
            "TEAM": "ATL",
            "GP": 82,
            "W": 40,
            "L": 42,
            "OFF_RATING": 115.0,
            "DEF_RATING": 116.5,
            "NET_RATING": -1.5,
            "PACE": 100.0,
        },
    ]


def _build(rows):
    return build_envelope(
        CAPABILITIES["team_ratings"],
        {"season": "2024-25"},
        {"ok": True, "rows": rows, "meta": dict(_meta())},
        entities=None,
        observed_at=datetime.now(UTC),
    )


def _task(*team_ids):
    return TaskSpec(
        goal="team ratings readmission probe",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[
            EntityRef(
                id=team_id,
                type="team",
                display_name="Boston Celtics" if team_id == "BOS" else team_id,
            )
            for team_id in team_ids
        ],
        requirements=[
            EvidenceRequirement(
                id="ratings",
                description="team ratings readmission probe",
                capability_options=["team_ratings"],
                requested_outputs=["NET_RATING"],
            )
        ],
    )


def _binding(envelope, subject_id, index, value):
    return EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id="ratings",
        output_id="NET_RATING",
        node_id="ratings",
        evidence_id=envelope.evidence_id,
        selector=f"rows[{index}].NET_RATING",
        row_selector=f"rows[{index}]",
        value=value,
        subject_entity_type="team",
        subject_entity_id=subject_id,
        subject_selector=f"rows[{index}].TEAM_ID",
        unit={"kind": "declared", "value": "points_per_100_possessions"},
        domain="team_ratings",
    )


def _admit(task, envelope, binding):
    node = PlanNode(
        id="ratings",
        description="readmission probe",
        capability_hints=[envelope.capability],
        covers_requirement_ids=["ratings"],
        status="complete",
    )
    execution = ExecutionResult(
        plan=Plan(nodes=[node]),
        evidence_by_node={"ratings": envelope},
        attempts={"ratings": 1},
    )
    claim = Claim(
        text="readmission probe claim",
        kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=[binding],
    )
    draft = DraftReport(sections=["probe"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=[envelope.evidence_id],
        sources=[
            ClaimSource(
                evidence_id=envelope.evidence_id,
                source=envelope.source,
                capability=envelope.capability,
                observed_at=envelope.observed_at,
            )
        ],
        output_bindings=[binding],
    )
    return admit_verified_claim_bindings(task, execution, draft, verified)


def test_wrong_row_binding_carrying_subject_value_readmits():
    envelope = _build(_bos_first_rows())
    binding = _binding(envelope, "BOS", 1, {"kind": "float", "value": 8.3})
    admitted = _admit(_task("BOS"), envelope, binding)
    fixed = admitted.output_bindings[0]
    assert fixed.selector == "rows[0].NET_RATING"
    assert fixed.row_selector == "rows[0]"
    assert fixed.subject_selector == "rows[0].TEAM_ID"
    assert fixed.value.value == 8.3


def test_decimal_declared_value_matching_row_float_admits():
    envelope = _build(_bos_first_rows()[:1])
    binding = _binding(envelope, "BOS", 0, {"kind": "decimal", "value": "8.30"})
    admitted = _admit(_task("BOS"), envelope, binding)
    assert admitted.output_bindings[0].value.value == "8.30"


def test_missing_subject_trio_still_rejects():
    envelope = _build(_bos_first_rows())
    binding = EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id="ratings",
        output_id="NET_RATING",
        node_id="ratings",
        evidence_id=envelope.evidence_id,
        selector="rows[0].NET_RATING",
        value={"kind": "float", "value": 8.3},
        unit={"kind": "declared", "value": "points_per_100_possessions"},
        domain="team_ratings",
    )
    with pytest.raises(ValueError):
        _admit(_task("BOS"), envelope, binding)


def test_different_subject_row_still_rejects():
    envelope = _build(_bos_first_rows())
    binding = _binding(envelope, "ATL", 0, {"kind": "float", "value": 8.3})
    with pytest.raises(
        ValueError, match="binding selector row does not match subject"
    ):
        _admit(_task("BOS", "ATL"), envelope, binding)
