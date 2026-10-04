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

_Q1_EVIDENCE_ID = "qualified_leaders:05b5922eaefae72d"
_Q1_TRUE_NODE = "q1_assist_leader_node"
_Q1_REQUIREMENT = "assist_leader_2024_25"
_Q1_STRIPPED_NODE = "qualified_leaders"
_Q1_INVENTED_NODE = "node_ratings"

_Q2_EVIDENCE_ID = "team_ratings:846a59cd8b5b96a7"
_Q2_TRUE_NODE = "q2_celtics_ratings_node"
_Q2_REQUIREMENT = "celtics_ratings_2024_25"
_Q2_LIVE_NODE = "node_ratings"

_RATINGS_UNIT = "points_per_100_possessions"


def _q1_envelope():
    return EvidenceEnvelope(
        evidence_id=_Q1_EVIDENCE_ID,
        capability="qualified_leaders",
        source="test:warehouse",
        observed_at=datetime.now(UTC),
        season="2024-25",
        rows=[{"PLAYER_ID": 1629027, "PLAYER_NAME": "Trae Young", "AST": 880}],
        units={"AST": "count"},
        entities=[EntityRef(id="1629027", type="player", display_name="Trae Young")],
    )


def _q1_task():
    return TaskSpec(
        goal="who led the league in assists in 2024-25",
        mode="quick",
        deliverable="answer",
        requested_outputs=["PLAYER_NAME", "AST"],
        entities=[EntityRef(id="1629027", type="player", display_name="Trae Young")],
        requirements=[
            EvidenceRequirement(
                id=_Q1_REQUIREMENT,
                description="2024-25 assists leader",
                capability_options=["qualified_leaders"],
                requested_outputs=["PLAYER_NAME", "AST"],
            )
        ],
    )


def _q1_bindings(node_id, evidence_id=_Q1_EVIDENCE_ID):
    return [
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=_Q1_REQUIREMENT,
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
            requirement_id=_Q1_REQUIREMENT,
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


def _q1_node(node_id=_Q1_TRUE_NODE):
    return PlanNode(
        id=node_id,
        description="assists leaderboard 2024-25",
        capability_hints=["qualified_leaders"],
        covers_requirement_ids=[_Q1_REQUIREMENT],
        status="complete",
    )


def _q2_envelope():
    return EvidenceEnvelope(
        evidence_id=_Q2_EVIDENCE_ID,
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
            "NET_RATING": _RATINGS_UNIT,
            "OFF_RATING": _RATINGS_UNIT,
            "DEF_RATING": _RATINGS_UNIT,
        },
        entities=[EntityRef(id="BOS", type="team", display_name="BOS")],
    )


def _q2_task():
    return TaskSpec(
        goal="how did the Celtics rate in 2024-25",
        mode="quick",
        deliverable="answer",
        requested_outputs=["NET_RATING", "OFF_RATING", "DEF_RATING"],
        entities=[EntityRef(id="BOS", type="team", display_name="BOS")],
        requirements=[
            EvidenceRequirement(
                id=_Q2_REQUIREMENT,
                description="2024-25 Celtics ratings",
                capability_options=["team_ratings"],
                requested_outputs=["NET_RATING", "OFF_RATING", "DEF_RATING"],
            )
        ],
    )


def _q2_bindings(node_id, evidence_id=_Q2_EVIDENCE_ID):
    return [
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=_Q2_REQUIREMENT,
            output_id="NET_RATING",
            node_id=node_id,
            evidence_id=evidence_id,
            selector="rows[0].NET_RATING",
            row_selector="rows[0]",
            value={"kind": "float", "value": 9.4},
            subject_entity_type="team",
            subject_entity_id="BOS",
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "declared", "value": _RATINGS_UNIT},
            domain="team_ratings",
        ),
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=_Q2_REQUIREMENT,
            output_id="OFF_RATING",
            node_id=node_id,
            evidence_id=evidence_id,
            selector="rows[0].OFF_RATING",
            row_selector="rows[0]",
            value={"kind": "float", "value": 118.2},
            subject_entity_type="team",
            subject_entity_id="BOS",
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "declared", "value": _RATINGS_UNIT},
            domain="team_ratings",
        ),
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=_Q2_REQUIREMENT,
            output_id="DEF_RATING",
            node_id=node_id,
            evidence_id=evidence_id,
            selector="rows[0].DEF_RATING",
            row_selector="rows[0]",
            value={"kind": "float", "value": 108.8},
            subject_entity_type="team",
            subject_entity_id="BOS",
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "declared", "value": _RATINGS_UNIT},
            domain="team_ratings",
        ),
    ]


def _q2_node(node_id=_Q2_TRUE_NODE):
    return PlanNode(
        id=node_id,
        description="Celtics ratings 2024-25",
        capability_hints=["team_ratings"],
        covers_requirement_ids=[_Q2_REQUIREMENT],
        status="complete",
    )


def _admit(task, envelope, bindings, owner_node_id, nodes):
    execution = ExecutionResult(
        plan=Plan(nodes=nodes),
        evidence_by_node={owner_node_id: envelope},
        attempts={node.id: 1 for node in nodes},
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
    return admit_verified_claim_bindings(task, execution, draft, verified)


def test_stripped_node_id_with_evidence_id_hit_admits():
    admitted = _admit(
        _q1_task(), _q1_envelope(), _q1_bindings(_Q1_STRIPPED_NODE),
        _Q1_TRUE_NODE, [_q1_node()],
    )
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["PLAYER_NAME"].value.value == "Trae Young"
    assert by_output["AST"].value.value == 880


def test_invented_node_id_with_evidence_id_hit_admits():
    admitted = _admit(
        _q1_task(), _q1_envelope(), _q1_bindings(_Q1_INVENTED_NODE),
        _Q1_TRUE_NODE, [_q1_node()],
    )
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["PLAYER_NAME"].value.value == "Trae Young"
    assert by_output["AST"].value.value == 880


def test_conflated_node_id_with_evidence_id_hit_admits():
    admitted = _admit(
        _q1_task(), _q1_envelope(), _q1_bindings(_Q1_EVIDENCE_ID),
        _Q1_TRUE_NODE, [_q1_node()],
    )
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["PLAYER_NAME"].value.value == "Trae Young"
    assert by_output["AST"].value.value == 880


def test_evidence_id_miss_with_true_node_admits_with_corrected_id():
    ghost = "qualified_leaders:0000000000000000"
    admitted = _admit(
        _q1_task(), _q1_envelope(), _q1_bindings(_Q1_TRUE_NODE, ghost),
        _Q1_TRUE_NODE, [_q1_node()],
    )
    assert [item.evidence_id for item in admitted.output_bindings] == [_Q1_EVIDENCE_ID, _Q1_EVIDENCE_ID]
    assert admitted.evidence_ids == [_Q1_EVIDENCE_ID]
    assert [item.evidence_id for item in admitted.sources] == [_Q1_EVIDENCE_ID]
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["PLAYER_NAME"].value.value == "Trae Young"
    assert by_output["AST"].value.value == 880


def test_evidence_id_miss_with_true_node_wrong_values_rejects():
    ghost = "qualified_leaders:0000000000000000"
    bindings = _q1_bindings(_Q1_TRUE_NODE, ghost)
    bad = [
        item.model_copy(update={"value": item.value.model_copy(update={"value": 1})})
        if item.output_id == "AST" else item
        for item in bindings
    ]
    with pytest.raises(ValueError, match="binding value"):
        _admit(
            _q1_task(), _q1_envelope(), bad,
            _Q1_TRUE_NODE, [_q1_node()],
        )


def test_evidence_and_node_miss_rejects():
    ghost = "qualified_leaders:0000000000000000"
    with pytest.raises(ValueError, match="ownership"):
        _admit(
            _q1_task(), _q1_envelope(), _q1_bindings(ghost, ghost),
            _Q1_TRUE_NODE, [_q1_node(), _q1_node(ghost)],
        )


def test_live_q1_bindings_admit():
    admitted = _admit(
        _q1_task(), _q1_envelope(), _q1_bindings(_Q1_STRIPPED_NODE),
        _Q1_TRUE_NODE, [_q1_node()],
    )
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["PLAYER_NAME"].value.value == "Trae Young"
    assert by_output["AST"].value.value == 880


def test_live_q2_bindings_admit():
    admitted = _admit(
        _q2_task(), _q2_envelope(), _q2_bindings(_Q2_LIVE_NODE),
        _Q2_TRUE_NODE, [_q2_node()],
    )
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["NET_RATING"].value.value == 9.4
    assert by_output["OFF_RATING"].value.value == 118.2
    assert by_output["DEF_RATING"].value.value == 108.8
