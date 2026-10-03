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
        requested_outputs=["PLAYER_NAME", "ASSIST_TOTAL"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="1629027", type="player", display_name="Trae Young")],
        requirements=[EvidenceRequirement(
            id=_REQUIREMENT_ID,
            description="2024-25 assists leaderboard",
            capability_options=["qualified_leaders"],
            capability_arguments={"stat_category": "AST", "season": "2024-25"},
            requested_outputs=["PLAYER_NAME", "ASSIST_TOTAL"],
        )],
    )


def _bindings(node_id=_NODE_ID, evidence_id=_NODE_ID, metric_leaf="AST", metric_value=880):
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
            output_id="ASSIST_TOTAL",
            node_id=node_id,
            evidence_id=evidence_id,
            selector=f"rows[0].{metric_leaf}",
            row_selector="rows[0]",
            value={"kind": "integer", "value": metric_value},
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


def test_q1_assist_total_served_by_ast_column_admits():
    admitted = _admit(_task(), _envelope(), _bindings())
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["PLAYER_NAME"].value.value == "Trae Young"
    assert by_output["ASSIST_TOTAL"].value.value == 880


def test_pts_leaf_on_assist_total_output_still_rejects():
    with pytest.raises(ValueError, match="binding selector metric does not match output"):
        _admit(_task(), _envelope(), _bindings(metric_leaf="PTS", metric_value=1500))
