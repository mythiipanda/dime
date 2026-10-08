from __future__ import annotations

import pytest

from v2.adapters.capabilities import (
    CAPABILITIES,
    preconditions_for_node,
    resolve_metric_column,
    servable_names_for,
)
from v2.adapters.models import (
    _drop_unresolvable_requested_outputs,
    servable_output_names,
)
from v2.contracts import (
    EvidenceRequirement,
    Plan,
    PlanNode,
    PreconditionCheck,
    RunMode,
    TaskSpec,
)
from v2.runtime import FakeCapability, PlanExecutor

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