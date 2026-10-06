from datetime import UTC, datetime

import pytest

from v2.contracts import (
    Claim,
    ClaimSource,
    DraftReport,
    EntityRef,
    EvidenceEnvelope,
    EvidenceOutputBinding,
    Plan,
    PlanNode,
    TaskSpec,
    VerifiedClaim,
)
from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings

_EVIDENCE_ID = "team_ratings:846a59cd8b5b96a7"
_OWNER_NODE = "q2_celtics_ratings_node"
_PROSE_UNIT = "points per 100 possessions"
_SNAKE_UNIT = "points_per_100_possessions"
_VALUES = (("NET_RATING", 9.4), ("OFF_RATING", 118.2), ("DEF_RATING", 108.8))

def _envelope():
    return EvidenceEnvelope(
        evidence_id=_EVIDENCE_ID,
        capability="team_ratings",
        source="test:warehouse",
        observed_at=datetime.now(UTC),
        season="2024-25",
        rows=[{
            "TEAM_ID": "BOS",
            "TEAM_NAME": "Boston Celtics",
            "NET_RATING": 9.4,
            "OFF_RATING": 118.2,
            "DEF_RATING": 108.8,
        }],
        units={
            "NET_RATING": _SNAKE_UNIT,
            "OFF_RATING": _SNAKE_UNIT,
            "DEF_RATING": _SNAKE_UNIT,
        },
        entities=[EntityRef(id="BOS", type="team", display_name="BOS")],
    )

def _task():
    return TaskSpec(
        goal="how did the Celtics rate in 2024-25",
        mode="quick",
        deliverable="answer",
        requested_outputs=["NET_RATING", "OFF_RATING", "DEF_RATING"],
        entities=[EntityRef(id="BOS", type="team", display_name="BOS")],
    )

def _bindings(unit_value):
    return [
        EvidenceOutputBinding(
            requirement_kind="task",
            requirement_id=None,
            output_id=output_id,
            node_id=_EVIDENCE_ID,
            evidence_id=_EVIDENCE_ID,
            selector=f"rows[0].{output_id}",
            row_selector="rows[0]",
            value={"kind": "float", "value": value},
            subject_entity_type="team",
            subject_entity_id="BOS",
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "declared", "value": unit_value},
            domain="team_ratings",
        )
        for output_id, value in _VALUES
    ]

def _admit(bindings):
    envelope = _envelope()
    execution = ExecutionResult(
        plan=Plan(nodes=[PlanNode(
            id=_OWNER_NODE,
            description="Celtics ratings 2024-25",
            capability_hints=["team_ratings"],
            status="complete",
        )]),
        evidence_by_node={_OWNER_NODE: envelope},
        attempts={_OWNER_NODE: 1},
    )
    evidence_ids = list(dict.fromkeys(item.evidence_id for item in bindings))
    claim = Claim(
        text="verified claim",
        kind="observed",
        evidence_ids=evidence_ids,
        output_bindings=bindings,
    )
    draft = DraftReport(sections=["claim"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=evidence_ids,
        sources=[
            ClaimSource(
                evidence_id=evidence_id,
                source=envelope.source,
                capability=envelope.capability,
                observed_at=envelope.observed_at,
            )
            for evidence_id in evidence_ids
        ],
        output_bindings=bindings,
    )
    return admit_verified_claim_bindings(_task(), execution, draft, verified)

def test_prose_unit_surface_form_admits():
    admitted = _admit(_bindings(_PROSE_UNIT))
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["NET_RATING"].value.value == 9.4
    assert by_output["OFF_RATING"].value.value == 118.2
    assert by_output["DEF_RATING"].value.value == 108.8

def test_genuine_unit_mismatch_still_rejects():
    with pytest.raises(ValueError, match="binding unit does not match output authority"):
        _admit(_bindings("assists"))
