from __future__ import annotations

import pytest

from v2.adapters.capabilities import (
    CAPABILITIES,
    Capability,
    post_evidence_failures,
    preconditions_for_node,
    resolve_metric_column,
)
from v2.contracts import Plan, PlanNode, PreconditionCheck, RunMode, TaskSpec
from v2.runtime import FakeCapability, PlanExecutor

@pytest.fixture
def anyio_backend():
    return "asyncio"

def _task(outputs, capability, requirement_id="ratings"):
    return TaskSpec(
        goal="shape one",
        mode=RunMode.QUICK,
        deliverable="shape one answer",
        season={"value": "2025-26", "source": "user", "confidence": 1.0},
        requirements=[{
            "id": requirement_id,
            "description": "rated board",
            "capability_options": [capability],
            "requested_outputs": list(outputs),
        }],
    )

def _plan(node_id, capability, requirement_id="ratings"):
    return Plan(nodes=[PlanNode(
        id=node_id,
        description="rated board",
        capability_hints=[capability],
        covers_requirement_ids=[requirement_id],
    )])

class _Tracking(FakeCapability):
    def __init__(self, name, rows):
        super().__init__(name, rows)
        self.calls: list[str] = []

    async def execute(self, node, task, evidence):
        self.calls.append(node.id)
        return await super().execute(node, task, evidence)

@pytest.mark.anyio
async def test_unresolvable_numeral_refused_before_execution() -> None:
    capability = _Tracking("team_ratings", {"NET_RATING": 9.6})
    task = _task(["HOME_RUNS"], "team_ratings")
    with pytest.raises(ValueError, match="precondition numeral failed") as caught:
        await PlanExecutor({"team_ratings": capability}).execute(
            task, _plan("board", "team_ratings"))
    message = str(caught.value)
    assert "board" in message
    assert "ratings" in message
    assert "HOME_RUNS" in message
    assert capability.calls == []

@pytest.mark.anyio
async def test_resolvable_preconditions_execute_normally() -> None:
    capability = _Tracking("team_ratings", {"NET_RATING": 9.6})
    task = _task(["NET_RATING"], "team_ratings")
    result = await PlanExecutor({"team_ratings": capability}).execute(
        task, _plan("board", "team_ratings"))
    assert capability.calls == ["board"]
    assert result.plan.nodes[0].status.value == "complete"
    assert result.evidence[0].capability == "team_ratings"

def test_preconditions_derive_from_task_plus_capability() -> None:
    spec = CAPABILITIES["team_ratings"]
    node = _plan("board", "team_ratings").nodes[0]
    first = preconditions_for_node(_task(["NET_RATING"], "team_ratings"), node, spec)
    second_task = _task(["NET_RATING"], "team_ratings").model_copy(update={
        "goal": "an entirely different phrasing about boards",
        "deliverable": "another deliverable phrasing",
        "subquestions": ["what is the net rating order"],
    })
    second = preconditions_for_node(second_task, node, spec)
    assert first == second
    changed_requirement = preconditions_for_node(
        _task(["HOME_RUNS"], "team_ratings"), node, spec)
    assert any(item.check == PreconditionCheck.NUMERAL and not item.resolvable
               for item in changed_requirement)
    assert not any(item.check == PreconditionCheck.NUMERAL and not item.resolvable
                   for item in first)
    other_spec = CAPABILITIES["standings"]
    other_node = _plan("board", "standings").nodes[0]
    other = preconditions_for_node(_task(["WINS"], "standings"), other_node, other_spec)
    assert any(item.column == "WINS" for item in other)
    assert resolve_metric_column(spec, "WINS") is None
    synthetic = Capability(name="future", tool_name="get_future",
                           units={"WOMBAT": "count"}, metric_definitions={})
    synthetic_node = PlanNode(id="board", description="future",
                              capability_hints=["future"],
                              covers_requirement_ids=["ratings"])
    synthetic_task = _task(["TOTAL_WOMBAT"], "future")
    synthetic_task.requirements[0].capability_options = ["future"]
    resolved = preconditions_for_node(synthetic_task, synthetic_node, synthetic)
    assert any(item.column == "WOMBAT" and item.resolvable for item in resolved)
    missing_task = _task(["TOTAL_HOME_RUNS"], "future")
    missing_task.requirements[0].capability_options = ["future"]
    missing = preconditions_for_node(missing_task, synthetic_node, synthetic)
    assert any(not item.resolvable for item in missing
               if item.check == PreconditionCheck.NUMERAL)

def test_post_failures_name_check_node_and_requirement() -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope, precondition_repair_instruction
    spec = CAPABILITIES["team_ratings"]
    node = _plan("board", "team_ratings").nodes[0]
    task = _task(["NET_RATING"], "team_ratings")
    preconditions = preconditions_for_node(task, node, spec)
    assert any(item.check == PreconditionCheck.NUMERAL and item.column == "NET_RATING"
               for item in preconditions)
    empty = EvidenceEnvelope(
        evidence_id="empty", capability="team_ratings", source="fixture",
        observed_at=datetime.now(UTC), season="2025-26",
        rows={"OTHER": 1}, units={},
    )
    failures = post_evidence_failures(preconditions, empty)
    assert len(failures) == 1
    assert "numeral" in failures[0]
    assert "board" in failures[0]
    assert "ratings" in failures[0]
    assert "fix the plan" in failures[0]
    expected = precondition_repair_instruction(
        PreconditionCheck.NUMERAL, "board", "ratings", "detail")
    assert "board" in expected and "ratings" in expected

@pytest.mark.anyio
async def test_team_ratings_shape_against_warehouse() -> None:
    from v2.adapters.core import ToolCapability
    task = _task(["NET_RATING"], "team_ratings")
    result = await PlanExecutor(
        {"team_ratings": ToolCapability("team_ratings")}).execute(
        task, _plan("board", "team_ratings"))
    assert result.plan.nodes[0].status.value == "complete"
    envelope = result.evidence[0]
    assert envelope.season == "2025-26"
    assert isinstance(envelope.rows, list) and envelope.rows
    assert "NET_RATING" in envelope.rows[0]
    assert envelope.units.get("NET_RATING") == "points_per_100_possessions"

@pytest.mark.anyio
async def test_standings_shape_against_warehouse() -> None:
    from v2.adapters.core import ToolCapability
    task = _task(["WINS"], "standings", requirement_id="table")
    result = await PlanExecutor(
        {"standings": ToolCapability("standings")}).execute(
        task, _plan("board", "standings", requirement_id="table"))
    assert result.plan.nodes[0].status.value == "complete"
    envelope = result.evidence[0]
    assert envelope.season == "2025-26"
    assert isinstance(envelope.rows, list) and envelope.rows
    assert "WINS" in envelope.rows[0]
