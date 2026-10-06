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

_SHORT_NODE_ID = "qualified_leaders"
_LIVE_EVIDENCE_ID = "qualified_leaders:05b5922eaefae72d"
_REQUIREMENT_ID = "assist_leader_2024_25"

def _envelope():
    return EvidenceEnvelope(
        evidence_id=_LIVE_EVIDENCE_ID,
        capability="qualified_leaders",
        source="test:warehouse",
        observed_at=datetime.now(UTC),
        season="2024-25",
        rows=[{"PLAYER_ID": 1629027, "PLAYER_NAME": "Trae Young", "AST": 880}],
        units={"AST": "count"},
        entities=[EntityRef(id="1629027", type="player", display_name="Trae Young")],
    )

def _task():
    return TaskSpec(
        goal="who led the league in assists in 2024-25",
        mode="quick",
        deliverable="answer",
        requested_outputs=["PLAYER_NAME", "AST"],
        entities=[EntityRef(id="1629027", type="player", display_name="Trae Young")],
        requirements=[
            EvidenceRequirement(
                id=_REQUIREMENT_ID,
                description="2024-25 assists leader",
                capability_options=["qualified_leaders"],
                requested_outputs=["PLAYER_NAME", "AST"],
            )
        ],
    )

def _bindings(node_id, evidence_id=_LIVE_EVIDENCE_ID, requirement_kind="evidence",
               requirement_id=_REQUIREMENT_ID):
    return [
        EvidenceOutputBinding(
            requirement_kind=requirement_kind,
            requirement_id=requirement_id,
            output_id="PLAYER_NAME",
            node_id=node_id,
            evidence_id=evidence_id,
            selector="rows[0].PLAYER_NAME",
            row_selector="rows[0]",
            value={"kind": "string", "value": "Trae Young"},
            subject_entity_type="player",
            subject_entity_id="1629027",
            subject_selector="rows[0].PLAYER_ID",
            unit={"kind": "unitless"},
            domain="qualified_leaders",
        ),
        EvidenceOutputBinding(
            requirement_kind=requirement_kind,
            requirement_id=requirement_id,
            output_id="AST",
            node_id=node_id,
            evidence_id=evidence_id,
            selector="rows[0].AST",
            row_selector="rows[0]",
            value={"kind": "integer", "value": 880},
            subject_entity_type="player",
            subject_entity_id="1629027",
            subject_selector="rows[0].PLAYER_ID",
            unit={"kind": "declared", "value": "count"},
            domain="qualified_leaders",
        ),
    ]

def _node(node_id=_SHORT_NODE_ID):
    return PlanNode(
        id=node_id,
        description="assists leaderboard 2024-25",
        capability_hints=["qualified_leaders"],
        covers_requirement_ids=[_REQUIREMENT_ID],
        status="complete",
    )

def _admit(task, envelope, bindings, nodes):
    execution = ExecutionResult(
        plan=Plan(nodes=nodes),
        evidence_by_node={_SHORT_NODE_ID: envelope},
        attempts={node.id: 1 for node in nodes},
    )
    evidence_ids = list(dict.fromkeys(item.evidence_id for item in bindings))
    claim = Claim(
        text="Trae Young led with 880 assists.",
        kind="observed",
        evidence_ids=evidence_ids,
        output_bindings=bindings,
    )
    draft = DraftReport(sections=["Assists leader"], claims=[claim])
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
    return admit_verified_claim_bindings(task, execution, draft, verified)

def test_evidence_scope_conflated_evidence_id_admits():
    admitted = _admit(_task(), _envelope(), _bindings(_LIVE_EVIDENCE_ID), [_node()])
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["PLAYER_NAME"].value.value == "Trae Young"
    assert by_output["AST"].value.value == 880

def test_task_scope_conflated_evidence_id_admits():
    task = TaskSpec(
        goal="who led the league in assists in 2024-25",
        mode="quick",
        deliverable="answer",
        requested_outputs=["PLAYER_NAME", "AST"],
        entities=[EntityRef(id="1629027", type="player", display_name="Trae Young")],
    )
    bindings = _bindings(_LIVE_EVIDENCE_ID, requirement_kind="task", requirement_id=None)
    admitted = _admit(task, _envelope(), bindings, [_node()])
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["PLAYER_NAME"].value.value == "Trae Young"
    assert by_output["AST"].value.value == 880

def test_true_node_id_match_still_admits():
    admitted = _admit(_task(), _envelope(), _bindings(_SHORT_NODE_ID), [_node()])
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["PLAYER_NAME"].value.value == "Trae Young"
    assert by_output["AST"].value.value == 880

def test_unknown_evidence_and_node_still_rejects():
    ghost = "qualified_leaders:0000000000000000"
    bindings = _bindings(ghost, ghost)
    with pytest.raises(ValueError, match="ownership"):
        _admit(_task(), _envelope(), bindings, [_node(), _node(ghost)])
