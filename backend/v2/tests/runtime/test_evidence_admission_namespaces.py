from __future__ import annotations

from datetime import UTC, datetime

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


def _team_rows():
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
        }
    ]


def _leader_rows():
    return [
        {
            "PLAYER_ID": 1629027,
            "PLAYER_NAME": "Trae Young",
            "TEAM": "ATL",
            "GP": 76,
            "AST": 880,
        }
    ]


def _build(team_rows, capability, arguments):
    return build_envelope(
        CAPABILITIES[capability],
        arguments,
        {"ok": True, "rows": team_rows, "meta": dict(_meta())},
        entities=None,
        observed_at=datetime.now(UTC),
    )


def _admit(task, envelope, node_id, binding):
    node = PlanNode(
        id=node_id,
        description="namespace probe",
        capability_hints=[envelope.capability],
        covers_requirement_ids=[binding.requirement_id],
        status="complete",
    )
    execution = ExecutionResult(
        plan=Plan(nodes=[node]),
        evidence_by_node={node_id: envelope},
        attempts={node_id: 1},
    )
    claim = Claim(
        text="namespace probe claim",
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


def _team_task():
    return TaskSpec(
        goal="team ratings namespace probe",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="BOS", type="team", display_name="Boston Celtics")],
        requirements=[
            EvidenceRequirement(
                id="ratings",
                description="team ratings namespace probe",
                capability_options=["team_ratings"],
                requested_outputs=["NET_RATING"],
            )
        ],
    )


def _team_binding(envelope, subject_id):
    return EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id="ratings",
        output_id="NET_RATING",
        node_id="ratings",
        evidence_id=envelope.evidence_id,
        selector="rows[0].NET_RATING",
        row_selector="rows[0]",
        value={"kind": "float", "value": 8.3},
        subject_entity_type="team",
        subject_entity_id=subject_id,
        subject_selector="rows[0].TEAM_ID",
        unit={"kind": "declared", "value": "points_per_100_possessions"},
        domain="team_ratings",
    )


def test_team_abbreviation_subject_admits():
    envelope = _build(_team_rows(), "team_ratings", {"season": "2024-25"})
    admitted = _admit(_team_task(), envelope, "ratings", _team_binding(envelope, "BOS"))
    assert admitted.output_bindings[0].value.value == 8.3


def test_team_numeric_subject_admits():
    envelope = _build(_team_rows(), "team_ratings", {"season": "2024-25"})
    admitted = _admit(
        _team_task(), envelope, "ratings", _team_binding(envelope, "1610612738")
    )
    assert admitted.output_bindings[0].value.value == 8.3


def test_league_scoped_player_subject_admits():
    envelope = _build(_leader_rows(), "qualified_leaders", {"season": "2024-25"})
    task = TaskSpec(
        goal="league leaders namespace probe",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="nba", type="league", display_name="NBA")],
        requirements=[
            EvidenceRequirement(
                id="leaders",
                description="league leaders namespace probe",
                capability_options=["qualified_leaders"],
                requested_outputs=["AST"],
            )
        ],
    )
    binding = EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id="leaders",
        output_id="AST",
        node_id="leaders",
        evidence_id=envelope.evidence_id,
        selector="rows[0].AST",
        row_selector="rows[0]",
        value={"kind": "integer", "value": 880},
        subject_entity_type="player",
        subject_entity_id="1629027",
        subject_selector="rows[0].PLAYER_ID",
        unit={"kind": "declared", "value": "count"},
        domain="qualified_leaders",
    )
    admitted = _admit(task, envelope, "leaders", binding)
    assert admitted.output_bindings[0].value.value == 880


def test_absent_subject_still_rejected():
    import pytest

    envelope = _build(_team_rows(), "team_ratings", {"season": "2024-25"})
    binding = _team_binding(envelope, "NYK")
    with pytest.raises(ValueError):
        _admit(_team_task(), envelope, "ratings", binding)
