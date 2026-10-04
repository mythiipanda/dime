from datetime import datetime, timezone

import pytest

from v2.contracts import (
    Claim,
    DraftReport,
    EntityRef,
    EvidenceEnvelope,
    EvidenceOutputBinding,
    EvidenceRequirement,
    Plan,
    PlanNode,
    PlanStatus,
    TaskSpec,
    VerifiedClaim,
)
from v2.runtime.models import (
    BindingFormMismatch,
    ExecutionResult,
    admit_verified_claim_bindings,
    build_output_statuses,
    propagate_evidence_to_task,
)


NODE_ID = "qualified_leaders:05b5922eaefae72d"
REQ_ID = "assist_leader_2024_25"


def _trae():
    return EntityRef(id="1629027", type="player", display_name="Trae Young")


def _jokic():
    return EntityRef(id="1628369", type="player", display_name="Nikola Jokic")


def _league():
    return EntityRef(id="NBA", type="league", display_name="NBA")


def _bos():
    return EntityRef(id="1610612738", type="team", display_name="Boston Celtics")


def _rows():
    return [{"PLAYER_NAME": "Trae Young", "PLAYER_ID": "1629027", "AST": 880}]


def _envelope(with_player):
    return EvidenceEnvelope(
        evidence_id=NODE_ID,
        capability="qualified_leaders",
        source="warehouse",
        observed_at=datetime.now(timezone.utc),
        season="2024-25",
        entities=[_trae()] if with_player else [],
        rows=_rows(),
        units={"AST": "count"},
    )


def _plan(covers):
    return Plan(nodes=[
        PlanNode(
            id=NODE_ID,
            description="assists leaders board",
            capability_hints=["qualified_leaders"],
            covers_requirement_ids=list(covers),
            status=PlanStatus.COMPLETE,
        ),
    ])


def _execution(envelope, covers=(REQ_ID,)):
    return ExecutionResult(
        plan=_plan(list(covers)),
        evidence_by_node={NODE_ID: envelope},
        attempts={NODE_ID: 1},
    )


def _draft():
    return DraftReport(sections=["summary"], claims=[])


def _task(entities, requirements):
    return TaskSpec(
        goal="Who led the 2024-25 season in assists?",
        mode="quick",
        deliverable="The assists leader for 2024-25",
        requested_outputs=["PLAYER_NAME", "AST"],
        entities=list(entities),
        requirements=list(requirements),
    )


def _requirement(requirement_id, outputs):
    return EvidenceRequirement(
        id=requirement_id,
        description="assists leader 2024-25",
        capability_options=["qualified_leaders"],
        requested_outputs=list(outputs),
    )


def _binding(output_id, value, requirement_id, unit):
    return EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id=requirement_id,
        output_id=output_id,
        node_id=NODE_ID,
        evidence_id=NODE_ID,
        selector="rows[0]." + output_id,
        row_selector="rows[0]",
        value=value,
        subject_entity_type="player",
        subject_entity_id="1629027",
        subject_selector="rows[0].PLAYER_ID",
        unit=unit,
        domain="qualified_leaders",
    )


def _bindings():
    return [
        _binding(
            "PLAYER_NAME",
            {"kind": "string", "value": "Trae Young"},
            REQ_ID,
            {"kind": "unitless"},
        ),
        _binding(
            "AST",
            {"kind": "integer", "value": 880},
            REQ_ID,
            {"kind": "declared", "value": "count"},
        ),
    ]


def _claim(bindings, claim_index=0):
    return VerifiedClaim(
        claim_index=claim_index,
        claim=Claim(
            text="Trae Young led with 880 assists",
            kind="observed",
            evidence_ids=[NODE_ID],
            output_bindings=list(bindings),
        ),
        evidence_ids=[NODE_ID],
        output_bindings=list(bindings),
    )


def _statuses(task, claims):
    rows = build_output_statuses(task, claims, [])
    return {
        (row.requirement_kind, row.requirement_id, row.output_id): row
        for row in rows
    }


def test_empty_task_entities_admit_and_propagate():
    task = _task([], [_requirement(REQ_ID, ["PLAYER_NAME", "AST"])])
    execution = _execution(_envelope(True))
    draft = _draft()
    admitted = admit_verified_claim_bindings(
        task, execution, draft, _claim(_bindings()))
    propagated = propagate_evidence_to_task(task, execution, draft, [admitted])
    by_key = _statuses(task, propagated)
    assert by_key[("task", None, "PLAYER_NAME")].status == "complete"
    assert by_key[("task", None, "AST")].status == "complete"


def test_league_task_entities_admit_and_propagate():
    task = _task([_league()], [_requirement(REQ_ID, ["PLAYER_NAME", "AST"])])
    execution = _execution(_envelope(True))
    draft = _draft()
    admitted = admit_verified_claim_bindings(
        task, execution, draft, _claim(_bindings()))
    propagated = propagate_evidence_to_task(task, execution, draft, [admitted])
    by_key = _statuses(task, propagated)
    assert by_key[("task", None, "PLAYER_NAME")].status == "complete"
    assert by_key[("task", None, "AST")].status == "complete"


def test_team_scoped_task_rejects_player_subject():
    task = _task([_bos()], [_requirement(REQ_ID, ["PLAYER_NAME", "AST"])])
    execution = _execution(_envelope(True))
    with pytest.raises(
        ValueError, match="binding subject is outside requested scope"
    ):
        admit_verified_claim_bindings(
            task, execution, _draft(), _claim(_bindings()))


def test_empty_envelope_entities_stays_rejected():
    task = _task([], [_requirement(REQ_ID, ["PLAYER_NAME", "AST"])])
    execution = _execution(_envelope(False))
    with pytest.raises(
        ValueError, match="binding subject is outside requested scope"
    ):
        admit_verified_claim_bindings(
            task, execution, _draft(), _claim(_bindings()))


def test_competing_claims_leave_task_output_unchanged():
    rows = [
        {"PLAYER_NAME": "Trae Young", "PLAYER_ID": "1629027", "AST": 880},
        {"PLAYER_NAME": "Nikola Jokic", "PLAYER_ID": "1628369", "AST": 700},
    ]
    envelope = EvidenceEnvelope(
        evidence_id=NODE_ID,
        capability="qualified_leaders",
        source="warehouse",
        observed_at=datetime.now(timezone.utc),
        season="2024-25",
        entities=[_trae(), _jokic()],
        rows=rows,
        units={"AST": "count"},
    )
    task = TaskSpec(
        goal="Who led the 2024-25 season in assists?",
        mode="quick",
        deliverable="The assists leader for 2024-25",
        requested_outputs=["PLAYER_NAME"],
        entities=[_trae(), _jokic()],
        requirements=[
            _requirement("leaders_a", ["PLAYER_NAME"]),
            _requirement("leaders_b", ["PLAYER_NAME"]),
        ],
    )
    execution = ExecutionResult(
        plan=_plan(["leaders_a", "leaders_b"]),
        evidence_by_node={NODE_ID: envelope},
        attempts={NODE_ID: 1},
    )
    draft = _draft()
    first = _binding(
        "PLAYER_NAME",
        {"kind": "string", "value": "Trae Young"},
        "leaders_a",
        {"kind": "unitless"},
    )
    second = EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id="leaders_b",
        output_id="PLAYER_NAME",
        node_id=NODE_ID,
        evidence_id=NODE_ID,
        selector="rows[1].PLAYER_NAME",
        row_selector="rows[1]",
        value={"kind": "string", "value": "Nikola Jokic"},
        subject_entity_type="player",
        subject_entity_id="1628369",
        subject_selector="rows[1].PLAYER_ID",
        unit={"kind": "unitless"},
        domain="qualified_leaders",
    )
    admitted = [
        admit_verified_claim_bindings(task, execution, draft, _claim([first], 0)),
        admit_verified_claim_bindings(
            task, execution, draft, _claim([second], 1)),
    ]
    propagated = propagate_evidence_to_task(task, execution, draft, admitted)
    assert propagated == admitted
    kinds = {
        binding.requirement_kind
        for claim in propagated
        for binding in claim.output_bindings
    }
    assert kinds == {"evidence"}
    by_key = _statuses(task, propagated)
    assert by_key[("task", None, "PLAYER_NAME")].status == "missing"


def test_player_task_with_entityless_envelope_admits_row_local_match():
    task = _task([_trae()], [_requirement(REQ_ID, ["PLAYER_NAME", "AST"])])
    execution = _execution(_envelope(False))
    admitted = admit_verified_claim_bindings(
        task, execution, _draft(), _claim(_bindings()))
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["PLAYER_NAME"].value.value == "Trae Young"
    assert by_output["AST"].value.value == 880


def test_player_task_with_entityless_envelope_rejects_wrong_subject():
    task = _task([_trae()], [_requirement(REQ_ID, ["PLAYER_NAME", "AST"])])
    execution = _execution(_envelope(False))
    wrong = [
        item.model_copy(update={"subject_entity_id": "1628369"})
        for item in _bindings()
    ]
    with pytest.raises(
        ValueError, match="binding subject is outside requested scope"
    ):
        admit_verified_claim_bindings(
            task, execution, _draft(), _claim(wrong))


ASSIST_REQ_ID = "assists_leader_2024_25"


def _assist_rows():
    return [{"PLAYER_NAME": "Trae Young", "PLAYER_ID": "1629027",
             "AST": 880, "PTS": 1900}]


def _assist_envelope():
    return EvidenceEnvelope(
        evidence_id=NODE_ID,
        capability="qualified_leaders",
        source="warehouse",
        observed_at=datetime.now(timezone.utc),
        season="2024-25",
        entities=[_trae()],
        rows=_assist_rows(),
        units={"AST": "count", "PTS": "count"},
    )


def _assist_task():
    return TaskSpec(
        goal="Who led the 2024-25 season in assists?",
        mode="quick",
        deliverable="The assists leader for 2024-25",
        requested_outputs=["PLAYER_NAME", "ASSIST_TOTAL"],
        entities=[_trae()],
        requirements=[
            _requirement(ASSIST_REQ_ID, ["PLAYER_NAME", "ASSIST_TOTAL"]),
        ],
    )


def _assist_name_binding():
    return _binding(
        "PLAYER_NAME",
        {"kind": "string", "value": "Trae Young"},
        ASSIST_REQ_ID,
        {"kind": "unitless"},
    )


def _assist_total_binding(selector="rows[0].AST", value=880):
    return EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id=ASSIST_REQ_ID,
        output_id="ASSIST_TOTAL",
        node_id=NODE_ID,
        evidence_id=NODE_ID,
        selector=selector,
        row_selector="rows[0]",
        value={"kind": "integer", "value": value},
        subject_entity_type="player",
        subject_entity_id="1629027",
        subject_selector="rows[0].PLAYER_ID",
        unit={"kind": "declared", "value": "count"},
        domain="qualified_leaders",
    )


def test_assist_total_admits_ast_column():
    task = _assist_task()
    execution = _execution(_assist_envelope(), (ASSIST_REQ_ID,))
    admitted = admit_verified_claim_bindings(
        task, execution, _draft(),
        _claim([_assist_name_binding(), _assist_total_binding()]))
    assert [binding.output_id for binding in admitted.output_bindings] == [
        "PLAYER_NAME", "ASSIST_TOTAL"]


def test_pts_leaf_on_assist_total_still_rejected():
    task = _assist_task()
    execution = _execution(_assist_envelope(), (ASSIST_REQ_ID,))
    with pytest.raises(BindingFormMismatch):
        admit_verified_claim_bindings(
            task, execution, _draft(),
            _claim([_assist_name_binding(),
                    _assist_total_binding("rows[0].PTS", 1900)]))


LIVE_SHORT = "qualified_leaders"
LIVE_DIGEST = "qualified_leaders:05b5922eaefae72d"
LIVE_REQ = "assist_leader_2024_25"


def _live_envelope():
    return EvidenceEnvelope(
        evidence_id=LIVE_DIGEST,
        capability="qualified_leaders",
        source="warehouse",
        observed_at=datetime.now(timezone.utc),
        season="2024-25",
        entities=[_trae()],
        rows=_rows(),
        units={"AST": "count"},
    )


def _live_plan():
    return Plan(nodes=[
        PlanNode(
            id=LIVE_SHORT,
            description="assists leaders board",
            capability_hints=["qualified_leaders"],
            covers_requirement_ids=[LIVE_REQ],
            status=PlanStatus.COMPLETE,
        ),
    ])


def _live_execution():
    return ExecutionResult(
        plan=_live_plan(),
        evidence_by_node={LIVE_SHORT: _live_envelope()},
        attempts={LIVE_SHORT: 1},
    )


def _live_task():
    return TaskSpec(
        goal="Who led the 2024-25 season in assists?",
        mode="quick",
        deliverable="The assists leader for 2024-25",
        requested_outputs=["PLAYER_NAME", "AST"],
        entities=[],
        requirements=[_requirement(LIVE_REQ, ["PLAYER_NAME", "AST"])],
    )


def _live_binding(output_id, value, unit):
    return EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id=LIVE_REQ,
        output_id=output_id,
        node_id=LIVE_DIGEST,
        evidence_id=LIVE_DIGEST,
        selector="rows[0]." + output_id,
        row_selector="rows[0]",
        value=value,
        subject_entity_type="player",
        subject_entity_id="1629027",
        subject_selector="rows[0].PLAYER_ID",
        unit=unit,
        domain="qualified_leaders",
    )


def _live_claim():
    bindings = [
        _live_binding(
            "PLAYER_NAME",
            {"kind": "string", "value": "Trae Young"},
            {"kind": "unitless"},
        ),
        _live_binding(
            "AST",
            {"kind": "integer", "value": 880},
            {"kind": "declared", "value": "count"},
        ),
    ]
    return VerifiedClaim(
        claim_index=0,
        claim=Claim(
            text="Trae Young led with 880 assists",
            kind="observed",
            evidence_ids=[LIVE_DIGEST],
            output_bindings=list(bindings),
        ),
        evidence_ids=[LIVE_DIGEST],
        output_bindings=list(bindings),
    )


def test_short_slug_keyed_propagate_resolves_by_evidence_id():
    task = _live_task()
    execution = _live_execution()
    draft = _draft()
    admitted = admit_verified_claim_bindings(
        task, execution, draft, _live_claim())
    propagated = propagate_evidence_to_task(task, execution, draft, [admitted])
    clones = [
        binding
        for claim in propagated
        for binding in claim.output_bindings
        if binding.requirement_kind == "task"
    ]
    assert len(clones) == 2
    by_key = _statuses(task, propagated)
    assert by_key[("task", None, "PLAYER_NAME")].status == "complete"
    assert by_key[("task", None, "AST")].status == "complete"
