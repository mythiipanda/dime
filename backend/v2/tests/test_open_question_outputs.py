from datetime import UTC, datetime

from v2.adapters.capabilities import CAPABILITIES
from v2.adapters.core import build_envelope
from v2.adapters.models import (_backfill_open_question_outputs,
                                _drop_unresolvable_requested_outputs)
from v2.contracts import (
    CalculationRequirement,
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
from v2.runtime.models import (
    ExecutionResult,
    admit_verified_claim_bindings,
    build_output_statuses,
    propagate_evidence_to_task,
)

_NODE_ID = "node_team_four_factors"
_REQUIREMENT_ID = "req_team_four_factors"
_OUTPUTS = ["EFG_PCT", "FT_RATE", "ORB_PCT", "TOV_PCT"]

def _open_task():
    return TaskSpec(
        goal="What are the Thunder four factors in the 2025-26 season?",
        mode="quick",
        deliverable="The Oklahoma City Thunder four-factor profile for 2025-26.",
        season=SeasonRef(value="2025-26", source="user", confidence=1.0),
        entities=[EntityRef(id="1610612760", type="team",
                            display_name="Oklahoma City Thunder")],
        required_evidence=["team_four_factors"],
        requirements=[EvidenceRequirement(
            id=_REQUIREMENT_ID,
            description="Thunder four factors for 2025-26",
            capability_options=["team_four_factors"],
        )],
    )

def test_backfill_fills_empty_authority_from_capability_catalog():
    filled = _backfill_open_question_outputs(_open_task())
    assert sorted(filled.requested_outputs) == sorted(_OUTPUTS)
    assert sorted(filled.requirements[0].requested_outputs) == sorted(_OUTPUTS)

def test_backfill_leaves_named_authority_untouched():
    named = _open_task().model_copy(update={
        "requested_outputs": ["EFG_PCT"],
        "requirements": [_open_task().requirements[0].model_copy(
            update={"requested_outputs": ["EFG_PCT"]})],
    })
    assert _backfill_open_question_outputs(named) == named

def test_backfill_skips_requirements_without_catalog_options():
    task = _open_task().model_copy(update={
        "requirements": [_open_task().requirements[0].model_copy(
            update={"capability_options": ["not_a_capability"]})],
    })
    assert _backfill_open_question_outputs(task) == task

def _envelope():
    return build_envelope(
        CAPABILITIES["team_four_factors"],
        {"season": "2025-26"},
        {"ok": True, "rows": [{
            "TEAM_ID": 1610612760,
            "TEAM_NAME": "Oklahoma City Thunder",
            "SEASON": "2025-26",
            "EFG_PCT": 0.557,
            "FT_RATE": 0.181,
            "ORB_PCT": 0.264,
            "TOV_PCT": 0.118,
        }], "meta": {
            "source": "warehouse",
            "season": "2025-26",
            "warehouse_id": "frozen-eval",
            "warehouse_sha256": "a" * 64,
        }},
        entities=None,
        observed_at=datetime.now(UTC),
    )

def _bindings(envelope):
    values = {"EFG_PCT": 0.557, "FT_RATE": 0.181,
              "ORB_PCT": 0.264, "TOV_PCT": 0.118}
    return [
        EvidenceOutputBinding(
            requirement_kind="task",
            requirement_id=None,
            output_id=output_id,
            node_id=_NODE_ID,
            evidence_id=envelope.evidence_id,
            selector=f"rows[0].{output_id}",
            row_selector="rows[0]",
            value={"kind": "float", "value": values[output_id]},
            subject_entity_type="team",
            subject_entity_id="1610612760",
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "unitless"},
            domain="team_four_factors",
        )
        for output_id in _OUTPUTS
    ]

def test_unresolvable_intake_outputs_drop_before_planning():
    task = _open_task().model_copy(update={
        "requested_outputs": ["EFG_PCT", "OREB_PCT", "DREB_PCT"],
        "requirements": [_open_task().requirements[0].model_copy(
            update={"requested_outputs": ["EFG_PCT", "OREB_PCT", "DREB_PCT"]})],
    })
    repaired = _drop_unresolvable_requested_outputs(task)
    assert repaired.requested_outputs == ["EFG_PCT"]
    assert repaired.requirements[0].requested_outputs == ["EFG_PCT"]

def test_drop_keeps_identity_and_calculation_outputs():
    task = _open_task().model_copy(update={
        "requested_outputs": ["TEAM_NAME", "OREB_PCT", "FOUR_FACTOR_MARGIN"],
        "calculation_requirements": [CalculationRequirement(
            id="margin",
            description="factor margin",
            requested_outputs=["FOUR_FACTOR_MARGIN"],
        )],
        "requirements": [_open_task().requirements[0].model_copy(
            update={"requested_outputs": ["TEAM_NAME", "OREB_PCT"]})],
    })
    repaired = _drop_unresolvable_requested_outputs(task)
    assert repaired.requested_outputs == ["TEAM_NAME", "FOUR_FACTOR_MARGIN"]
    assert repaired.requirements[0].requested_outputs == ["TEAM_NAME"]

def test_drop_leaves_resolvable_authority_untouched():
    task = _open_task().model_copy(update={
        "requested_outputs": ["EFG_PCT", "TOV_PCT"],
        "requirements": [_open_task().requirements[0].model_copy(
            update={"requested_outputs": ["EFG_PCT", "TOV_PCT"]})],
    })
    assert _drop_unresolvable_requested_outputs(task) == task

def test_structural_capability_outputs_survive_the_drop():
    task = _open_task().model_copy(update={
        "requested_outputs": ["WINNER", "SCORES"],
        "required_evidence": ["season_series"],
        "requirements": [EvidenceRequirement(
            id="series",
            description="Celtics Knicks 2024-25 series",
            capability_options=["season_series"],
            requested_outputs=["WINNER", "SCORES"],
        )],
    })
    assert _drop_unresolvable_requested_outputs(task) == task

def test_backfilled_authority_admits_claims_and_completes_every_status():
    task = _backfill_open_question_outputs(_open_task())
    envelope = _envelope()
    node = PlanNode(
        id=_NODE_ID,
        description="Thunder four factors for 2025-26",
        capability_hints=["team_four_factors"],
        covers_requirement_ids=[_REQUIREMENT_ID],
        arguments={},
        status="complete",
    )
    execution = ExecutionResult(
        plan=Plan(nodes=[node]),
        evidence_by_node={_NODE_ID: envelope},
        attempts={_NODE_ID: 1},
    )
    bindings = _bindings(envelope)
    claim = Claim(
        text="The Thunder posted a 0.557 effective field-goal percentage in 2025-26.",
        kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=bindings,
    )
    draft = DraftReport(sections=["Four factors"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=[envelope.evidence_id],
        sources=[ClaimSource(
            evidence_id=envelope.evidence_id,
            source=envelope.source,
            capability=envelope.capability,
            observed_at=envelope.observed_at,
        )],
        output_bindings=bindings,
    )
    admitted = admit_verified_claim_bindings(task, execution, draft, verified)
    assert sorted(item.output_id for item in admitted.output_bindings) == sorted(_OUTPUTS)
    mirrored = propagate_evidence_to_task(task, execution, draft, [admitted])
    rows = build_output_statuses(task, mirrored, [])
    assert len(rows) == 8
    assert {row.status for row in rows} == {"complete"}

def test_a_metric_id_no_capability_can_serve_is_dropped() -> None:
    from v2.adapters.models import _drop_unresolvable_requested_outputs
    from v2.contracts import EvidenceRequirement, TaskSpec

    task = TaskSpec(
        goal="mvp",
        mode="quick",
        deliverable="winner and share",
        requirements=[EvidenceRequirement(
            id="award",
            description="official MVP result",
            capability_options=["award_results"],
            requested_outputs=["PLAYER", "AWARD_SHARE"],
            metric_ids=["MVP", "AWARD_SHARE"],
        )],
    )

    result = _drop_unresolvable_requested_outputs(task)

    assert result.requirements[0].metric_ids == ["AWARD_SHARE"]

def test_an_open_vocabulary_capability_keeps_the_metric_id() -> None:
    from v2.adapters.models import _drop_unresolvable_requested_outputs
    from v2.contracts import EvidenceRequirement, TaskSpec

    task = TaskSpec(
        goal="rates",
        mode="deep_dive",
        deliverable="table",
        requirements=[EvidenceRequirement(
            id="rates",
            description="agent-written rate query",
            capability_options=["sql_exec"],
            requested_outputs=["TS_PCT"],
            metric_ids=["TS_PCT"],
        )],
    )

    assert _drop_unresolvable_requested_outputs(task) == task
