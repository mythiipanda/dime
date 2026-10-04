from datetime import UTC, datetime

import pytest

from v2.contracts import (
    Claim,
    ClaimSource,
    DraftReport,
    EntityRef,
    EvidenceEnvelope,
    EvidenceOutputBinding,
    EvidenceRequirement,
    Plan,
    PlanNode,
    TaskSpec,
    VerifiedClaim,
)
from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings

_TRUE_NODE = "okc_standings_2024_25"
_GHOST_NODE = "node_standings"
_EVIDENCE_ID = "standings:a34a5a591d13db55"
_GHOST_EVIDENCE_ID = "standings:0000000000000000"
_REQUIREMENT = "okc_record_2024_25"
_TEAM_ID = "1610612737"


def _envelope():
    return EvidenceEnvelope(
        evidence_id=_EVIDENCE_ID,
        capability="standings",
        source="test:warehouse",
        observed_at=datetime.now(UTC),
        season="2024-25",
        rows=[{"TEAM_ID": _TEAM_ID, "WINS": 68, "LOSSES": 14}],
        units={"WINS": "count", "LOSSES": "count"},
        entities=[EntityRef(id=_TEAM_ID, type="team", display_name="Test Club")],
    )


def _task():
    return TaskSpec(
        goal="win-loss record in 2024-25",
        mode="quick",
        deliverable="answer",
        requested_outputs=["WINS", "LOSSES"],
        entities=[EntityRef(id=_TEAM_ID, type="team", display_name="Test Club")],
        requirements=[
            EvidenceRequirement(
                id=_REQUIREMENT,
                description="2024-25 win-loss record",
                capability_options=["standings"],
                requested_outputs=["WINS", "LOSSES"],
            )
        ],
    )


def _bindings(node_id, evidence_id):
    return [
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=_REQUIREMENT,
            output_id="WINS",
            node_id=node_id,
            evidence_id=evidence_id,
            selector="rows[0].WINS",
            row_selector="rows[0]",
            value={"kind": "integer", "value": 68},
            subject_entity_type="team",
            subject_entity_id=_TEAM_ID,
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "declared", "value": "count"},
            domain="standings",
        ),
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=_REQUIREMENT,
            output_id="LOSSES",
            node_id=node_id,
            evidence_id=evidence_id,
            selector="rows[0].LOSSES",
            row_selector="rows[0]",
            value={"kind": "integer", "value": 14},
            subject_entity_type="team",
            subject_entity_id=_TEAM_ID,
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "declared", "value": "count"},
            domain="standings",
        ),
    ]


def _node():
    return PlanNode(
        id=_TRUE_NODE,
        description="standings for the 2024-25 season",
        capability_hints=["standings"],
        covers_requirement_ids=[_REQUIREMENT],
        status="complete",
    )


def _admit(bindings):
    envelope = _envelope()
    execution = ExecutionResult(
        plan=Plan(nodes=[_node()]),
        evidence_by_node={_TRUE_NODE: envelope},
        attempts={_TRUE_NODE: 1},
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


def test_nonexistent_node_with_real_evidence_binds():
    admitted = _admit(_bindings(_GHOST_NODE, _EVIDENCE_ID))
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["WINS"].value.value == 68
    assert by_output["LOSSES"].value.value == 14


def test_invented_evidence_with_true_node_admits_with_corrected_id():
    admitted = _admit(_bindings(_TRUE_NODE, _GHOST_EVIDENCE_ID))
    assert [item.evidence_id for item in admitted.output_bindings] == [_EVIDENCE_ID, _EVIDENCE_ID]
    assert admitted.evidence_ids == [_EVIDENCE_ID]
    assert [item.evidence_id for item in admitted.sources] == [_EVIDENCE_ID]
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["WINS"].value.value == 68
    assert by_output["LOSSES"].value.value == 14


def test_invented_evidence_with_true_node_wrong_values_rejects():
    bindings = _bindings(_TRUE_NODE, _GHOST_EVIDENCE_ID)
    bad = [
        item.model_copy(update={"value": item.value.model_copy(update={"value": 999})})
        for item in bindings
    ]
    with pytest.raises(ValueError, match="binding value"):
        _admit(bad)
