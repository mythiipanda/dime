import pytest
from v2.adapters.models import ModelPlanner
from v2.contracts import TaskSpec
from v2.arguments import PlannerOutputWire, SLOTS
from v2.tests.runtime.test_model_stages import StubModel


def _catalog():
    return {
        "entity_resolution": {
            "description": "resolve",
            "arguments": {"type": "object", "properties": {"query": {"type": "string"}}},
            "dependent_entity_arguments": {},
        },
        "player_report": {
            "description": "report",
            "arguments": {"type": "object", "properties": {
                "player": {"type": "string"}, "season": {"type": "string"}},
                "required": ["player"], "additionalProperties": False},
            "dependent_entity_arguments": {"player": "player"},
        },
    }


@pytest.mark.anyio
async def test_planner_strips_dependent_injected_player():
    stub = StubModel([{"nodes": [{
        "id": "report", "description": "report", "capability": "player_report",
        "arguments": {"player": "Alex Example", "season": "2025-26"}}]}])
    planner = ModelPlanner(stub, provider="stub", model_name="stub",
                           capability_catalog=_catalog())
    plan = await planner.plan(TaskSpec(goal="report", mode="quick", deliverable="text"))
    by_id = {node.id: node for node in plan.nodes}
    assert "report" in by_id
    assert "player" not in by_id["report"].arguments
    assert by_id["report"].arguments.get("season") == "2025-26"
    resolvers = [node for node in plan.nodes if "entity_resolution" in node.capability_hints]
    assert len(resolvers) == 1
    assert resolvers[0].arguments.get("query") == "Alex Example"
    assert resolvers[0].id in by_id["report"].depends_on
