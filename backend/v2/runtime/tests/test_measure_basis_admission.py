"""Requested measure basis at the evidence admission boundary.

Fixture C from R500: the task asks for cumulative points while the source
serves points per game. Before this check the binding was admitted and the
output reported ``complete``. The basis is now carried by TaskSpec /
EvidenceRequirement ``expected_bases`` and compared at admission against the
evidence/catalog authoritative unit, never against the model's binding unit.
"""
import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

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
from v2.runtime.interfaces import freeze_task
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


def test_frozen_views_carry_sorted_expected_bases_as_maps():
    task = _task(
        ["PTS", "REB"],
        task_bases={"REB": MeasureBasis.PER_GAME,
                    "PTS": MeasureBasis.TOTAL},
        requirement_bases={"REB": MeasureBasis.TOTAL,
                           "PTS": MeasureBasis.PER_GAME})
    view = freeze_task(task)

    assert view.expected_bases == (("PTS", "total"), ("REB", "per_game"))
    assert view.model_dump()["expected_bases"] == {
        "PTS": "total", "REB": "per_game"}
    requirement = view.requirements[0]
    assert requirement.expected_bases == (
        ("PTS", "per_game"), ("REB", "total"))
    assert requirement.model_dump()["expected_bases"] == {
        "PTS": "per_game", "REB": "total"}
    assert json.loads(json.dumps(view.model_dump()))["expected_bases"] == {
        "PTS": "total", "REB": "per_game"}


def test_frozen_views_default_expected_bases_to_empty_maps():
    task = _task(["PTS"])
    view = freeze_task(task)

    assert view.expected_bases == ()
    assert view.model_dump()["expected_bases"] == {}
    assert view.requirements[0].expected_bases == ()
    assert view.requirements[0].model_dump()["expected_bases"] == {}


def test_frozen_expected_bases_do_not_alias_or_mutate_with_task_spec():
    task = _task(
        ["PTS"],
        task_bases={"PTS": MeasureBasis.TOTAL},
        requirement_bases={"PTS": MeasureBasis.PER_GAME})
    view = freeze_task(task)

    task.expected_bases["PTS"] = MeasureBasis.PER_GAME
    task.requirements[0].expected_bases["PTS"] = MeasureBasis.TOTAL

    assert view.expected_bases == (("PTS", "total"),)
    assert view.requirements[0].expected_bases == (("PTS", "per_game"),)
    assert view.model_dump()["expected_bases"] == {"PTS": "total"}
    assert view.requirements[0].model_dump()["expected_bases"] == {
        "PTS": "per_game"}
    with pytest.raises(FrozenInstanceError):
        view.expected_bases = ()
    with pytest.raises(FrozenInstanceError):
        view.requirements[0].expected_bases = ()
