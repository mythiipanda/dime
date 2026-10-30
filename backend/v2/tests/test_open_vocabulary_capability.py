from __future__ import annotations

import pytest

from v2.adapters.capabilities import (
    CAPABILITIES,
    preconditions_for_node,
    resolve_metric_column,
    servable_names_for,
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
from v2.runtime.models import build_output_statuses


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


_SEASON = {"value": "2024-25", "source": "user", "confidence": 1.0}


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


@pytest.fixture
def anyio_backend():
    return "asyncio"
