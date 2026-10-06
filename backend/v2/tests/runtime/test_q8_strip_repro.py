import pytest
from v2.adapters.models import ModelPlanner
from v2.contracts import TaskSpec
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

@pytest.mark.anyio
async def test_q8_planner_refills_player_from_task_entity():
    task = TaskSpec(
        goal="Jayson Tatum PPG 2024-25", mode="quick", deliverable="text",
        season={"value": "2024-25", "source": "user", "confidence": 1.0},
        entities=[{"id": "tatum", "type": "player", "display_name": "Jayson Tatum"}],
        requirements=[{
            "id": "r1", "description": "Tatum PPG",
            "capability_options": ["player_report"],
            "capability_arguments": {"player": "Jayson Tatum", "season": "2024-25"}}],
        required_evidence=["player_report"],
    )
    omitted = {"nodes": [{
        "id": "tatum_report_2024_25", "description": "report",
        "capability_hints": ["player_report"],
        "covers_requirement_ids": ["r1"],
        "arguments": {"season": "2024-25"}}]}
    stub = StubModel([omitted, omitted])
    planner = ModelPlanner(stub, provider="stub", model_name="stub",
                           capability_catalog=_catalog())
    plan = await planner.plan(task)
    by_id = {node.id: node for node in plan.nodes}
    assert by_id["tatum_report_2024_25"].arguments.get("player") == "Jayson Tatum"
    resolvers = [node for node in plan.nodes if "entity_resolution" in node.capability_hints]
    assert len(resolvers) == 1
    assert resolvers[0].arguments.get("query") == "Jayson Tatum"
    assert resolvers[0].id in by_id["tatum_report_2024_25"].depends_on

@pytest.mark.anyio
async def test_q8_planner_strips_injected_player_despite_trusted_entity():
    task = TaskSpec(
        goal="Jayson Tatum PPG 2024-25", mode="quick", deliverable="text",
        season={"value": "2024-25", "source": "user", "confidence": 1.0},
        entities=[{"id": "tatum", "type": "player", "display_name": "Jayson Tatum"}],
        requirements=[{
            "id": "r1", "description": "Tatum PPG",
            "capability_options": ["player_report"],
            "capability_arguments": {"player": "Jayson Tatum", "season": "2024-25"}}],
        required_evidence=["player_report"],
    )
    injected = {"nodes": [{
        "id": "report", "description": "report",
        "capability_hints": ["player_report"],
        "covers_requirement_ids": ["r1"],
        "arguments": {"player": "Evil Joueur", "season": "2024-25"}}]}
    stub = StubModel([injected, injected])
    planner = ModelPlanner(stub, provider="stub", model_name="stub",
                           capability_catalog=_catalog())
    plan = await planner.plan(task)
    by_id = {node.id: node for node in plan.nodes}
    assert by_id["report"].arguments.get("player") != "Evil Joueur"
    assert "Evil Joueur" not in list(by_id["report"].arguments.values())

@pytest.mark.anyio
async def test_q8_planner_leaves_missing_player_without_usable_entity():
    task = TaskSpec(
        goal="PPG 2024-25", mode="quick", deliverable="text",
        season={"value": "2024-25", "source": "user", "confidence": 1.0},
        entities=[],
        requirements=[{
            "id": "r1", "description": "PPG",
            "capability_options": ["player_report"],
            "capability_arguments": {"season": "2024-25"}}],
        required_evidence=["player_report"],
    )
    omitted = {"nodes": [{
        "id": "report", "description": "report",
        "capability_hints": ["player_report"],
        "covers_requirement_ids": ["r1"],
        "arguments": {"season": "2024-25"}}]}
    stub = StubModel([omitted, omitted])
    planner = ModelPlanner(stub, provider="stub", model_name="stub",
                           capability_catalog=_catalog())
    plan = await planner.plan(task)
    by_id = {node.id: node for node in plan.nodes}
    assert by_id["report"].arguments.get("player") is None
    assert by_id["report"].depends_on == []
    feedback = stub.calls[1]["payload"].get("coverage_feedback")
    assert feedback["missing_required_arguments"] == {"report": ["player"]}
