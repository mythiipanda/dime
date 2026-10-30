"""Requested measure basis at the evidence admission boundary.

Fixture C from R500: the task asks for cumulative points while the source
serves points per game. Before this check the binding was admitted and the
output reported ``complete``. The basis is now carried by TaskSpec /
EvidenceRequirement ``expected_bases`` and compared at admission against the
evidence/catalog authoritative unit, never against the model's binding unit.
"""
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from v2.adapters.models import ModelIntake, _finalize_requested_outputs
from v2.contracts import (
    CalculationOutputBinding,
    CalculationRequirement,
    Claim,
    DeclaredCalculation,
    DeclaredCalculationInput,
    DraftReport,
    EvidenceEnvelope,
    EvidenceRequirement,
    MeasureBasis,
    Plan,
    PlanNode,
    TaskSpec,
    VerificationReport,
)
from v2.runtime import loop
from v2.runtime.models import (
    BindingBasisMismatch,
    ExecutionResult,
    _measure_basis,
    build_output_statuses,
)

NODE_ID = "cumulative_totals_sql"
EVIDENCE_ID = "sql_exec:rate"


def _task(outputs, requirement_outputs=None, *, task_bases=None,
          requirement_bases=None):
    return TaskSpec(
        goal="cumulative season totals",
        mode="quick",
        deliverable="cumulative season totals",
        requested_outputs=list(outputs),
        expected_bases=task_bases or {},
        requirements=[EvidenceRequirement(
            id="cumulative_totals",
            description="Cumulative season totals",
            capability_options=["sql_exec"],
            requested_outputs=list(
                outputs if requirement_outputs is None else requirement_outputs),
            expected_bases=requirement_bases or {},
        )],
    )


def _envelope(unit):
    return EvidenceEnvelope(
        evidence_id=EVIDENCE_ID,
        capability="sql_exec",
        source="test:warehouse",
        observed_at=datetime.now(UTC),
        season="2024-25",
        rows=[{"PLAYER": "Shai Gilgeous-Alexander", "PTS": 32.7}],
        units={} if unit is None else {"PTS": unit},
    )


def _binding(unit, *, requirement_kind="task", unit_kind="declared"):
    return {
        "requirement_kind": requirement_kind,
        "requirement_id": (None if requirement_kind == "task"
                           else "cumulative_totals"),
        "output_id": "PTS",
        "node_id": NODE_ID,
        "evidence_id": EVIDENCE_ID,
        "selector": "rows[0].PTS",
        "value": {"kind": "float", "value": 32.7},
        "unit": ({"kind": "unitless"} if unit_kind == "unitless"
                 else {"kind": "declared", "value": unit}),
        "domain": "sql_exec",
    }


def _run(task, unit, *, requirement_kind="task", unit_kind="declared"):
    envelope = _envelope(unit)
    execution = ExecutionResult(
        plan=Plan(nodes=[PlanNode(
            id=NODE_ID,
            description="cumulative totals",
            capability_hints=["sql_exec"],
            covers_requirement_ids=["cumulative_totals"],
            status="complete")]),
        evidence_by_node={NODE_ID: envelope},
        attempts={NODE_ID: 1},
    )
    draft = DraftReport(sections=["x"], claims=[Claim(
        text="32.7 points",
        kind="observed",
        evidence_ids=[EVIDENCE_ID],
        output_bindings=[_binding(
            unit, requirement_kind=requirement_kind, unit_kind=unit_kind)])])
    verification = VerificationReport(
        status="pass",
        claim_results=[{"claim_index": 0, "supported": True}])
    admitted, gaps = loop._verified_claims(
        task, execution, draft, verification, {EVIDENCE_ID: envelope})
    statuses = build_output_statuses(task, admitted, gaps)
    return admitted, gaps, statuses


def _status(statuses, kind):
    return next(item.status for item in statuses if item.requirement_kind == kind)


def test_total_request_rejects_per_game_binding():
    task = _task(["PTS"], task_bases={"PTS": MeasureBasis.TOTAL})
    admitted, gaps, statuses = _run(task, "points_per_game")

    assert admitted[0].output_bindings == []
    assert any("basis" in gap.message for gap in gaps)
    assert _status(statuses, "task") == "rejected"
    assert all(item.status != "complete" for item in statuses)


def test_total_request_accepts_count_authority():
    task = _task(["PTS"], task_bases={"PTS": MeasureBasis.TOTAL})
    admitted, gaps, statuses = _run(task, "count")

    assert gaps == []
    assert admitted[0].output_bindings[0].value.value == 32.7
    assert _status(statuses, "task") == "complete"


def test_per_game_request_accepts_per_game_authority():
    task = _task(["PTS"], task_bases={"PTS": MeasureBasis.PER_GAME})
    admitted, gaps, statuses = _run(task, "points_per_game")

    assert gaps == []
    assert _status(statuses, "task") == "complete"


def test_explicit_basis_rejects_unknown_authority():
    task = _task(["PTS"], task_bases={"PTS": MeasureBasis.TOTAL})
    admitted, gaps, statuses = _run(task, None, unit_kind="unitless")

    assert admitted[0].output_bindings == []
    assert any("unknown" in gap.message for gap in gaps)
    assert _status(statuses, "task") == "rejected"


def test_absent_basis_keeps_legacy_completion():
    task = _task(["PTS"])
    admitted, gaps, statuses = _run(task, "points_per_game")

    assert gaps == []
    assert _status(statuses, "task") == "complete"
    assert admitted[0].output_bindings[0].unit.value == "points_per_game"


def test_games_played_unit_has_no_basis_and_is_unaffected():
    assert _measure_basis("games_played") is None
    task = _task(["PTS"])
    envelope = _envelope("games_played")
    envelope.units["GP"] = "games_played"
    envelope.rows[0]["GP"] = 76.0
    execution = ExecutionResult(
        plan=Plan(nodes=[PlanNode(
            id=NODE_ID, description="games played",
            capability_hints=["sql_exec"],
            covers_requirement_ids=["cumulative_totals"],
            status="complete")]),
        evidence_by_node={NODE_ID: envelope},
        attempts={NODE_ID: 1},
    )
    binding = _binding("games_played")
    binding.update({"output_id": "GP", "selector": "rows[0].GP",
                    "value": {"kind": "float", "value": 76.0}})
    draft = DraftReport(sections=["x"], claims=[Claim(
        text="76 games", kind="observed", evidence_ids=[EVIDENCE_ID],
        output_bindings=[binding])])
    verification = VerificationReport(
        status="pass", claim_results=[{"claim_index": 0, "supported": True}])
    admitted, gaps = loop._verified_claims(
        task.model_copy(update={"requested_outputs": ["GP"]}),
        execution, draft, verification, {EVIDENCE_ID: envelope})

    assert gaps == []
    assert admitted[0].output_bindings[0].output_id == "GP"


def test_requirement_basis_does_not_apply_to_task_scope_binding():
    task = _task(["PTS"], requirement_bases={"PTS": MeasureBasis.TOTAL})
    admitted, gaps, statuses = _run(task, "points_per_game")

    assert gaps == []
    assert _status(statuses, "task") == "complete"
    assert _status(statuses, "evidence") == "missing"


def test_requirement_scope_binding_uses_its_own_basis():
    task = _task(["PTS"], requirement_bases={"PTS": MeasureBasis.TOTAL})
    admitted, gaps, statuses = _run(
        task, "points_per_game", requirement_kind="evidence")

    assert admitted[0].output_bindings == []
    assert any("basis" in gap.message for gap in gaps)
    assert _status(statuses, "evidence") == "rejected"
    assert _status(statuses, "task") == "missing"


def test_task_basis_does_not_apply_to_requirement_scope_binding():
    task = _task(["PTS"], task_bases={"PTS": MeasureBasis.TOTAL})
    admitted, gaps, statuses = _run(
        task, "points_per_game", requirement_kind="evidence")

    assert gaps == []
    assert _status(statuses, "evidence") == "complete"


def test_basis_mismatch_is_a_typed_value_error():
    assert issubclass(BindingBasisMismatch, ValueError)


def test_measure_basis_uses_only_source_backed_units():
    assert _measure_basis("count") is MeasureBasis.TOTAL
    assert _measure_basis("total") is MeasureBasis.TOTAL
    assert _measure_basis("per_game") is MeasureBasis.PER_GAME
    assert _measure_basis("points_per_game") is MeasureBasis.PER_GAME
    assert _measure_basis("minutes") is None
    assert _measure_basis("fraction_0_1") is None
    assert _measure_basis("percent_0_100") is None
    assert _measure_basis("points_per_100_possessions") is None
    assert _measure_basis("points") is None
    assert _measure_basis(None) is None


def test_bad_task_basis_key_is_rejected():
    with pytest.raises(ValidationError, match="expected_bases"):
        _task(["PTS"], task_bases={"REB": MeasureBasis.TOTAL})


def test_bad_requirement_basis_key_is_rejected():
    with pytest.raises(ValidationError, match="expected_bases"):
        EvidenceRequirement(
            id="cumulative_totals",
            description="Cumulative season totals",
            capability_options=["sql_exec"],
            requested_outputs=["PTS"],
            expected_bases={"REB": MeasureBasis.TOTAL})


def test_finalize_preserves_surviving_basis_and_prunes_dropped_output():
    task = TaskSpec(
        goal="points",
        mode="quick",
        deliverable="points",
        requested_outputs=["PTS", "BOGUS_METRIC"],
        expected_bases={"PTS": MeasureBasis.TOTAL,
                        "BOGUS_METRIC": MeasureBasis.PER_GAME},
        requirements=[EvidenceRequirement(
            id="points",
            description="Points",
            capability_options=["qualified_leaders"],
            requested_outputs=["PTS"],
            expected_bases={"PTS": MeasureBasis.TOTAL})])

    finalized = _finalize_requested_outputs(task)

    assert finalized.requested_outputs == ["PTS"]
    assert finalized.expected_bases == {"PTS": MeasureBasis.TOTAL}
    assert finalized.requirements[0].expected_bases == {
        "PTS": MeasureBasis.TOTAL}


def test_expected_bases_reach_the_intake_wire():
    schema = ModelIntake.schema.model_json_schema()

    assert "expected_bases" in schema["properties"]
    assert "expected_bases" in schema["$defs"]["EvidenceRequirement"]["properties"]
    assert schema["$defs"]["MeasureBasis"]["enum"] == ["total", "per_game"]

    task = ModelIntake.schema.model_validate({
        "goal": "cumulative points",
        "mode": "quick",
        "deliverable": "cumulative points",
        "requested_outputs": ["PTS"],
        "expected_bases": {"PTS": "total"},
    })
    assert task.expected_bases == {"PTS": MeasureBasis.TOTAL}


def test_actual_column_semantics_cumulative_units_map_to_total():
    from shared.tools.league import _column_semantics

    declared = {
        "PTS": "total_points",
        "REB": "total_rebounds",
        "AST": "total_assists",
    }
    for column, unit_name in declared.items():
        unit, _ = _column_semantics("silver_leaders_pts", column)
        assert unit == unit_name
        assert _measure_basis(unit) is MeasureBasis.TOTAL
    # A "total_" prefix is not the rule: a real unit with that prefix stays
    # outside the requested-basis vocabulary.
    assert _measure_basis("total_minutes") is None


def test_total_request_accepts_source_backed_total_unit():
    task = _task(["PTS"], task_bases={"PTS": MeasureBasis.TOTAL})
    admitted, gaps, statuses = _run(task, "total_points")

    assert gaps == []
    assert admitted[0].output_bindings[0].unit.value == "total_points"
    assert _status(statuses, "task") == "complete"


def _calculation_task(output_id="TOTAL_POINTS"):
    return TaskSpec(
        goal="total points",
        mode="quick",
        deliverable="total points",
        requested_outputs=[output_id],
        expected_bases={output_id: MeasureBasis.TOTAL},
        requirements=[],
        calculation_requirements=[CalculationRequirement(
            id="total_points",
            description="Total points",
            requested_outputs=[output_id])])


def _run_calculation(task, *, unit, operation="add", result="9534"):
    requirement = task.calculation_requirements[0]
    output_id = requirement.requested_outputs[0]
    evidence = EvidenceEnvelope(
        evidence_id=EVIDENCE_ID,
        capability="sql_exec",
        source="test:warehouse",
        observed_at=datetime.now(UTC),
        season="2024-25",
        rows=[{"PLAYER": "P", "PTS": 9534, "GAMES": 82}],
        units={})
    execution = ExecutionResult(
        plan=Plan(nodes=[PlanNode(
            id=NODE_ID,
            description="cumulative totals",
            capability_hints=["sql_exec"],
            status="complete")]),
        evidence_by_node={NODE_ID: evidence},
        attempts={NODE_ID: 1},
    )
    paths = (["rows[0].PTS"] if operation == "add"
             else ["rows[0].PTS", "rows[0].GAMES"])
    calculation = DeclaredCalculation(
        calculation_id="total_calc",
        requirement_id=requirement.id,
        operation=operation,
        inputs=[DeclaredCalculationInput(
            evidence_id=EVIDENCE_ID, path=path) for path in paths],
        result=result,
        unit=unit)
    binding = CalculationOutputBinding(
        requirement_id=requirement.id,
        output_id=output_id,
        calculation_id="total_calc")
    draft = DraftReport(
        sections=["x"],
        claims=[Claim(
            text="total", kind="derived", evidence_ids=[EVIDENCE_ID],
            calculation_id="total_calc", output_bindings=[binding])],
        calculations=[calculation])
    verification = VerificationReport(
        status="pass", claim_results=[{"claim_index": 0, "supported": True}])
    admitted, gaps = loop._verified_claims(
        task, execution, draft, verification, {EVIDENCE_ID: evidence})
    return admitted, gaps, build_output_statuses(task, admitted, gaps)


def test_calculation_binding_rejects_wrong_basis_for_explicit_total():
    admitted, gaps, statuses = _run_calculation(
        _calculation_task(), unit="points_per_game", operation="divide",
        result="116.26829268292683")

    assert admitted[0].output_bindings == []
    assert any("basis" in gap.message for gap in gaps)
    assert _status(statuses, "calculation") == "rejected"
    assert all(item.status != "complete" for item in statuses)


def test_calculation_binding_accepts_source_backed_total_unit():
    admitted, gaps, statuses = _run_calculation(
        _calculation_task(), unit="total_points")

    assert gaps == []
    assert admitted[0].output_bindings[0].output_id == "TOTAL_POINTS"
    assert _status(statuses, "calculation") == "complete"


def test_requirement_binding_without_basis_cannot_alias_into_task_total():
    from v2.contracts import EntityRef

    task = _task(["PTS"], task_bases={"PTS": MeasureBasis.TOTAL})
    evidence = _envelope("points_per_game")
    evidence = evidence.model_copy(update={
        "entities": [EntityRef(id="1", type="player", display_name="P")],
        "rows": [{"PLAYER": "P", "PLAYER_ID": "1", "PTS": 32.7}]})
    execution = ExecutionResult(
        plan=Plan(nodes=[PlanNode(
            id=NODE_ID,
            description="cumulative totals",
            capability_hints=["sql_exec"],
            covers_requirement_ids=["cumulative_totals"],
            status="complete")]),
        evidence_by_node={NODE_ID: evidence},
        attempts={NODE_ID: 1},
    )
    binding = _binding(
        "points_per_game", requirement_kind="evidence")
    binding.update({
        "subject_entity_type": "player",
        "subject_entity_id": "1",
        "subject_selector": "rows[0].PLAYER_ID",
        "row_selector": "rows[0]"})
    draft = DraftReport(sections=["x"], claims=[Claim(
        text="32.7 points", kind="observed", evidence_ids=[EVIDENCE_ID],
        output_bindings=[binding])])
    verification = VerificationReport(
        status="pass", claim_results=[{"claim_index": 0, "supported": True}])
    admitted, gaps = loop._verified_claims(
        task, execution, draft, verification, {EVIDENCE_ID: evidence})
    statuses = build_output_statuses(task, admitted, gaps)

    assert "basis" not in " ".join(gap.message for gap in gaps)
    assert _status(statuses, "evidence") == "complete"
    assert _status(statuses, "task") == "missing"


def test_finalized_basis_prune_revalidates_under_pydantic():
    task = TaskSpec(
        goal="points",
        mode="quick",
        deliverable="points",
        requested_outputs=["PTS", "BOGUS_METRIC"],
        expected_bases={"PTS": MeasureBasis.TOTAL,
                        "BOGUS_METRIC": MeasureBasis.PER_GAME},
        requirements=[EvidenceRequirement(
            id="points",
            description="Points",
            capability_options=["qualified_leaders"],
            requested_outputs=["PTS"],
            expected_bases={"PTS": MeasureBasis.TOTAL})])

    finalized = _finalize_requested_outputs(task)
    revalidated = TaskSpec.model_validate(finalized.model_dump())

    assert revalidated.requested_outputs == ["PTS"]
    assert set(revalidated.expected_bases) <= set(revalidated.requested_outputs)
    assert all(
        set(item.expected_bases) <= set(item.requested_outputs)
        for item in revalidated.requirements)
    assert "BOGUS_METRIC" not in revalidated.expected_bases
