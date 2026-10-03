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

_TEAM_ID = "1610612737"
_REQUIREMENT = "team_record_2024_25"
_NODE_ID = "team_standings_2024_25"


def _envelope():
    return build_envelope(
        CAPABILITIES["standings"],
        {"season": "2024-25"},
        {"ok": True, "rows": [
            {"TeamID": 1610612737, "team": "Test Club", "WINS": 68,
             "LOSSES": 14, "WinPCT": 0.829},
        ], "meta": {
            "source": "warehouse",
            "season": "2024-25",
            "warehouse_id": "frozen-eval",
            "warehouse_sha256": "a" * 64,
        }},
        observed_at=datetime.now(UTC),
    )


def _task():
    return TaskSpec(
        goal="2024-25 win-loss record and win share",
        mode="quick",
        deliverable="record answer",
        requested_outputs=["WINS", "LOSSES", "WIN_PCT"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id=_TEAM_ID, type="team", display_name="Test Club")],
        requirements=[EvidenceRequirement(
            id=_REQUIREMENT,
            description="2024-25 team win-loss record",
            capability_options=["standings"],
            capability_arguments={"season": "2024-25"},
            requested_outputs=["WINS", "LOSSES", "WIN_PCT"],
        )],
    )


def _bindings(node_id, evidence_id, wins=68):
    return [
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=_REQUIREMENT,
            output_id="WINS",
            node_id=node_id,
            evidence_id=evidence_id,
            selector="rows[0].WINS",
            row_selector="rows[0]",
            value={"kind": "integer", "value": wins},
            subject_entity_type="team",
            subject_entity_id=_TEAM_ID,
            subject_selector="rows[0].TeamID",
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
            subject_selector="rows[0].TeamID",
            unit={"kind": "declared", "value": "count"},
            domain="standings",
        ),
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=_REQUIREMENT,
            output_id="WIN_PCT",
            node_id=node_id,
            evidence_id=evidence_id,
            selector="rows[0].WinPCT",
            row_selector="rows[0]",
            value={"kind": "float", "value": 0.829},
            subject_entity_type="team",
            subject_entity_id=_TEAM_ID,
            subject_selector="rows[0].TeamID",
            unit={"kind": "declared", "value": "fraction_0_1"},
            domain="standings",
        ),
    ]


def _node():
    return PlanNode(
        id=_NODE_ID,
        description="standings for the 2024-25 season",
        capability_hints=["standings"],
        covers_requirement_ids=[_REQUIREMENT],
        arguments={"season": "2024-25"},
        status="complete",
    )


def _admit(bindings):
    envelope = _envelope()
    execution = ExecutionResult(
        plan=Plan(nodes=[_node()]),
        evidence_by_node={_NODE_ID: envelope},
        attempts={_NODE_ID: 1},
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


def test_plan_envelope_carries_zero_entities():
    assert _envelope().entities == []


def test_entityless_team_record_admits():
    envelope = _envelope()
    admitted = _admit(_bindings(_NODE_ID, envelope.evidence_id))
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["WINS"].value.value == 68
    assert by_output["LOSSES"].value.value == 14
    assert by_output["WIN_PCT"].value.value == 0.829


def test_invented_evidence_with_true_node_rejects():
    with pytest.raises(ValueError, match="ownership"):
        _admit(_bindings(_NODE_ID, "standings:0000000000000000"))


def test_invented_value_with_true_evidence_rejects():
    envelope = _envelope()
    with pytest.raises(ValueError, match="exactly match"):
        _admit(_bindings(_NODE_ID, envelope.evidence_id, wins=69))
