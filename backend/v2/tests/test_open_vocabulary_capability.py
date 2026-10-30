from __future__ import annotations

import pytest

from v2.adapters.capabilities import (
    CAPABILITIES,
    preconditions_for_node,
    resolve_metric_column,
    servable_names_for,
)
from v2.adapters.models import (
    _align_requirement_requested_outputs,
    _drop_unresolvable_requested_outputs,
    _finalize_requested_outputs,
    servable_output_names,
)
from v2.contracts import (
    EntityRef,
    EvidenceRequirement,
    Plan,
    PlanNode,
    PreconditionCheck,
    RunMode,
    TaskSpec,
)
from v2.runtime import FakeCapability, PlanExecutor
from v2.runtime.models import build_output_statuses

@pytest.fixture
def anyio_backend():
    return "asyncio"

def _task(outputs, capability, requirement_id="query"):
    return TaskSpec(
        goal="which ten players lead on true shooting in 2024-25",
        mode=RunMode.QUICK,
        deliverable="ten names with their true shooting percentage",
        season={"value": "2024-25", "source": "user", "confidence": 1.0},
        requirements=[{
            "id": requirement_id,
            "description": "agent-written true shooting ranking",
            "capability_options": [capability],
            "requested_outputs": list(outputs),
        }],
    )

def _plan(node_id, capability, requirement_id="query"):
    return Plan(nodes=[PlanNode(
        id=node_id,
        description="agent-written true shooting ranking",
        capability_hints=[capability],
        covers_requirement_ids=[requirement_id],
    )])

def test_an_agent_named_column_resolves_to_itself():
    spec = CAPABILITIES["sql_exec"]
    assert resolve_metric_column(spec, "TS_PCT") == "TS_PCT"
    assert resolve_metric_column(spec, "PTS_PER_100_POSS") == "PTS_PER_100_POSS"

def test_a_closed_capability_still_rejects_an_undeclared_column():
    spec = CAPABILITIES["award_results"]
    assert resolve_metric_column(spec, "HOME_RUNS") is None
    preconditions = preconditions_for_node(
        _task(["HOME_RUNS"], "award_results", requirement_id="ballot"),
        _plan("ballot", "award_results", requirement_id="ballot").nodes[0],
        spec)
    numerals = [item for item in preconditions
                if item.check == PreconditionCheck.NUMERAL]
    assert [item.resolvable for item in numerals] == [False]
    assert "HOME_RUNS" in numerals[0].detail
    assert "AWARD_SHARE" in numerals[0].detail

def test_an_open_capability_declares_no_unit_precondition():
    preconditions = preconditions_for_node(
        _task(["TS_PCT"], "sql_exec"), _plan("query", "sql_exec").nodes[0],
        CAPABILITIES["sql_exec"])
    numerals = [item for item in preconditions
                if item.check == PreconditionCheck.NUMERAL]
    assert [(item.output_id, item.column, item.resolvable)
            for item in numerals] == [("TS_PCT", "TS_PCT", True)]
    assert [item for item in preconditions
            if item.check == PreconditionCheck.UNIT] == []

def test_a_closed_capability_still_declares_its_unit_precondition():
    preconditions = preconditions_for_node(
        _task(["AWARD_SHARE"], "award_results", requirement_id="ballot"),
        _plan("ballot", "award_results", requirement_id="ballot").nodes[0],
        CAPABILITIES["award_results"])
    units = [item for item in preconditions
             if item.check == PreconditionCheck.UNIT]
    assert [(item.output_id, item.column, item.expected_unit)
            for item in units] == [("AWARD_SHARE", "award_share", "fraction_0_1")]

def test_an_identity_output_still_resolves_to_a_subject_row():
    preconditions = preconditions_for_node(
        _task(["PLAYER_NAME"], "sql_exec"), _plan("query", "sql_exec").nodes[0],
        CAPABILITIES["sql_exec"])
    assert [item.check for item in preconditions
            if item.output_id == "PLAYER_NAME"] == [PreconditionCheck.ENTITY]

def test_an_open_capability_publishes_no_fixed_servable_list():
    assert servable_names_for(CAPABILITIES["sql_exec"]) == []
    assert servable_output_names("sql_exec") == []
    closed = servable_names_for(CAPABILITIES["award_results"])
    assert closed == servable_output_names("award_results")
    assert "AWARD_SHARE" in closed

@pytest.mark.anyio
async def test_an_agent_named_column_runs_through_the_executor():
    capability = FakeCapability("sql_exec", [
        {"PLAYER_NAME": "Player One", "TS_PCT": 0.614},
        {"PLAYER_NAME": "Player Two", "TS_PCT": 0.608},
    ])
    result = await PlanExecutor({"sql_exec": capability}).execute(
        _task(["TS_PCT"], "sql_exec"), _plan("query", "sql_exec"))
    assert capability.name == "sql_exec"
    assert result.plan.nodes[0].status.value == "complete"
    assert result.evidence[0].capability == "sql_exec"
    assert result.evidence[0].rows[0]["TS_PCT"] == 0.614

@pytest.mark.anyio
async def test_an_undeclared_column_still_refuses_a_closed_node_before_execution():
    calls: list[str] = []

    class _Tracked(FakeCapability):
        async def execute(self, node, task, evidence):
            calls.append(node.id)
            return await FakeCapability.execute(self, node, task, evidence)

    capability = _Tracked("award_results", [{"PLAYER_NAME": "Player One"}])
    with pytest.raises(ValueError, match="precondition numeral failed"):
        await PlanExecutor({"award_results": capability}).execute(
            _task(["HOME_RUNS"], "award_results", requirement_id="ballot"),
            _plan("ballot", "award_results", requirement_id="ballot"))
    assert calls == []

def _rail_task(options):
    return TaskSpec(
        goal="which ten players lead on true shooting in 2024-25",
        mode="quick",
        deliverable="ten names with their true shooting percentage",
        requested_outputs=["TS_PCT"],
        requirements=[EvidenceRequirement(
            id="query",
            description="agent-written true shooting ranking",
            capability_options=list(options),
            requested_outputs=["TS_PCT"])],
    )

def test_an_agent_named_column_survives_the_output_drop_alongside_a_rail():
    task = _rail_task(["award_results", "sql_exec"])
    repaired = _drop_unresolvable_requested_outputs(task)
    assert repaired.requested_outputs == ["TS_PCT"]
    assert repaired.requirements[0].requested_outputs == ["TS_PCT"]

def test_a_closed_only_requirement_still_drops_an_unresolvable_column():
    task = _rail_task(["award_results"])
    repaired = _drop_unresolvable_requested_outputs(task)
    assert repaired.requested_outputs == []
    assert repaired.requirements[0].requested_outputs == []

_SEASON = {"value": "2024-25", "source": "user", "confidence": 1.0}

def _two_source_task():
    return TaskSpec(
        goal="compare a per-game measure with a season total for one subject",
        mode="quick",
        deliverable="the per-game measure and the season total",
        requested_outputs=["PER_GAME_MEASURE", "SEASON_TOTAL"],
        season=_SEASON,
        entities=[EntityRef(id="Example Subject", type="player",
                            display_name="Example Subject")],
        requirements=[
            EvidenceRequirement(
                id="per_game_source",
                description="per-game measure from the season summary source",
                capability_options=["sql_exec"]),
            EvidenceRequirement(
                id="total_source",
                description="season total from the history source",
                capability_options=["sql_exec"]),
        ],
    )

def _two_source_plan():
    return Plan(nodes=[
        PlanNode(
            id="per_game_node", description="per-game measure",
            capability_hints=["sql_exec"],
            covers_requirement_ids=["per_game_source"],
            arguments={"sql": "SELECT subject, per_game_measure FROM summary_source"}),
        PlanNode(
            id="total_node", description="season total",
            capability_hints=["sql_exec"],
            covers_requirement_ids=["total_source"],
            arguments={"sql": "SELECT subject, season_total FROM history_source"}),
    ])

def _two_source_rows(node):
    if node.id == "per_game_node":
        return [{"PLAYER": "Example Subject", "PER_GAME_MEASURE": 1.5}]
    return [{"PLAYER": "Example Subject", "SEASON_TOTAL": 42}]

def test_inferred_task_outputs_stay_out_of_open_vocabulary_requirements():
    finalized = _finalize_requested_outputs(_two_source_task())
    assert finalized.requested_outputs == ["PER_GAME_MEASURE", "SEASON_TOTAL"]
    assert [list(item.requested_outputs)
            for item in finalized.requirements] == [[], []]

@pytest.mark.anyio
async def test_a_two_source_plan_completes_through_the_executor():
    task = _finalize_requested_outputs(_two_source_task())
    capability = FakeCapability("sql_exec", _two_source_rows)
    result = await PlanExecutor(
        {"sql_exec": capability}, max_concurrency=1, max_failures=1,
    ).execute(task, _two_source_plan())
    assert [node.status.value for node in result.plan.nodes] == [
        "complete", "complete"]
    assert result.errors == {}

@pytest.mark.anyio
async def test_an_explicit_requirement_output_missing_from_sql_still_fails():
    task = _finalize_requested_outputs(TaskSpec(
        goal="per-game measure for one subject",
        mode="quick",
        deliverable="the per-game measure",
        requested_outputs=["PER_GAME_MEASURE"],
        season=_SEASON,
        entities=[EntityRef(id="Example Subject", type="player",
                            display_name="Example Subject")],
        requirements=[EvidenceRequirement(
            id="per_game_source",
            description="per-game measure from the season summary source",
            capability_options=["sql_exec"],
            requested_outputs=["PER_GAME_MEASURE"])],
    ))
    plan = Plan(nodes=[PlanNode(
        id="per_game_node", description="per-game measure",
        capability_hints=["sql_exec"],
        covers_requirement_ids=["per_game_source"],
        arguments={"sql": "SELECT subject FROM summary_source"})])
    capability = FakeCapability("sql_exec", [{"PLAYER": "Example Subject"}])
    result = await PlanExecutor({"sql_exec": capability}).execute(task, plan)
    assert result.plan.nodes[0].status.value == "failed"
    assert any("PER_GAME_MEASURE" in error
               for error in result.errors["per_game_node"])

def test_closed_vocabulary_requirement_alignment_is_preserved():
    task = TaskSpec(
        goal="who won the award and with what share",
        mode="quick",
        deliverable="winner and share",
        requested_outputs=["AWARD_SHARE"],
        season=_SEASON,
        requirements=[EvidenceRequirement(
            id="ballot",
            description="official award result",
            capability_options=["award_results"])],
    )
    aligned = _align_requirement_requested_outputs(task)
    assert aligned.requirements[0].requested_outputs == ["AWARD_SHARE"]

def test_unbound_task_outputs_are_still_reported_missing():
    finalized = _finalize_requested_outputs(_two_source_task())
    statuses = build_output_statuses(finalized, [], [])
    task_statuses = {item.output_id: item.status for item in statuses
                     if item.requirement_kind == "task"}
    assert task_statuses == {"PER_GAME_MEASURE": "missing",
                             "SEASON_TOTAL": "missing"}

@pytest.mark.parametrize("requested_output,passes", [
    ("MEASURE_RATE", True),
    ("REPORT_SECTION", False),
])
def test_explicit_sql_alias_matches_requirement_column_contract(requested_output, passes):
    from datetime import UTC, datetime
    import duckdb
    from v2.adapters.capabilities import post_evidence_failures
    from v2.contracts import EvidenceEnvelope

    sql = "SELECT source_rate AS MEASURE_RATE FROM (VALUES (1.5)) AS owned(source_rate)"
    with duckdb.connect(":memory:") as fixture:
        result = fixture.execute(sql)
        columns = [item[0] for item in result.description]
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    task = TaskSpec(goal="requested measure", mode="quick", deliverable="measure",
        requested_outputs=[requested_output], requirements=[EvidenceRequirement(
            id="measure", description="requested measure", capability_options=["sql_exec"],
            metric_ids=["MEASURE_RATE"], requested_outputs=[requested_output])])
    node = PlanNode(id="measure", description="read", capability_hints=["sql_exec"],
        covers_requirement_ids=["measure"], arguments={"sql": sql})
    evidence = EvidenceEnvelope(evidence_id="owned", capability="sql_exec",
        source="fixture", observed_at=datetime.now(UTC), rows=rows)
    failures = post_evidence_failures(
        preconditions_for_node(task, node, CAPABILITIES["sql_exec"]), evidence)
    assert rows == [{"MEASURE_RATE": 1.5}]
    if passes:
        assert failures == []
    else:
        assert len(failures) == 1
        assert requested_output in failures[0]
