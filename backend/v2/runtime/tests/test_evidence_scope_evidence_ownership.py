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

_NODE_ID = "qualified_leaders:05b5922eaefae72d"
_REQUIREMENT_ID = "player_assists_leader_2024_25"

def _rows():
    return [
        {
            "PLAYER_ID": 1629027,
            "PLAYER_NAME": "Trae Young",
            "GP": 76,
            "MIN": 2700,
            "AST": 880,
            "PTS": 1500,
        },
        {
            "PLAYER_ID": 1628369,
            "PLAYER_NAME": "Nikola Jokic",
            "GP": 74,
            "MIN": 2600,
            "AST": 700,
            "PTS": 1900,
        },
    ]

def _envelope():
    return build_envelope(
        CAPABILITIES["qualified_leaders"],
        {"season": "2024-25", "stat_category": "AST"},
        {"ok": True, "rows": _rows(), "meta": {
            "source": "warehouse",
            "season": "2024-25",
            "warehouse_id": "frozen-eval",
            "warehouse_sha256": "a" * 64,
        }},
        entities=None,
        observed_at=datetime.now(UTC),
    )

def _task():
    return TaskSpec(
        goal="Who led the NBA in assists in the 2024-25 season, and how many?",
        mode="quick",
        deliverable="Assists leader and total assists",
        requested_outputs=["PLAYER_NAME", "AST"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="1629027", type="player", display_name="Trae Young")],
        requirements=[EvidenceRequirement(
            id=_REQUIREMENT_ID,
            description="2024-25 assists leaderboard",
            capability_options=["qualified_leaders"],
            capability_arguments={"stat_category": "AST", "season": "2024-25"},
            requested_outputs=["PLAYER_NAME", "AST"],
        )],
    )

def _bindings(node_id=_NODE_ID, evidence_id=_NODE_ID):
    return [
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=_REQUIREMENT_ID,
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
            requirement_kind="evidence",
            requirement_id=_REQUIREMENT_ID,
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

def _node(node_id=_NODE_ID):
    return PlanNode(
        id=node_id,
        description="2024-25 assists leaderboard",
        capability_hints=["qualified_leaders"],
        covers_requirement_ids=[_REQUIREMENT_ID],
        arguments={"stat_category": "AST", "season": "2024-25"},
        status="complete",
    )

def _admit(task, envelope, bindings, nodes=None):
    nodes = nodes or [_node()]
    attempts = {node.id: 1 for node in nodes}
    by_node = {node.id: envelope for node in nodes if node.id == _NODE_ID}
    execution = ExecutionResult(
        plan=Plan(nodes=nodes),
        evidence_by_node=by_node,
        attempts=attempts,
    )
    evidence_ids = list(dict.fromkeys(item.evidence_id for item in bindings))
    claim = Claim(
        text="Trae Young led the NBA with 880 assists in 2024-25.",
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

def test_evidence_scope_binding_citing_node_id_admits_with_corrected_id():
    envelope = _envelope()
    assert envelope.evidence_id != _NODE_ID
    admitted = _admit(_task(), envelope, _bindings())
    assert all(item.evidence_id == envelope.evidence_id for item in admitted.output_bindings)
    assert admitted.evidence_ids == [envelope.evidence_id]
    assert [item.evidence_id for item in admitted.sources] == [envelope.evidence_id]

def test_evidence_scope_binding_without_node_evidence_still_rejects():
    envelope = _envelope()
    ghost = "qualified_leaders:0000000000000000"
    bindings = _bindings(node_id=ghost, evidence_id=ghost)
    nodes = [_node(), _node(ghost)]
    with pytest.raises(ValueError, match="ownership"):
        _admit(_task(), envelope, bindings, nodes=nodes)
