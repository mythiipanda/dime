from datetime import UTC, datetime

import pytest

from v2.adapters.core import ToolCapability
from v2.contracts import PlanNode, SeasonRef, TaskSpec


@pytest.mark.anyio
async def test_tool_capability_uses_planned_arguments_and_scoped_season():
    seen = {}

    class Tool:
        async def ainvoke(self, arguments):
            seen.update(arguments)
            return {"ok": True, "rows": [{"TEAM": "Boston"}],
                    "meta": {"source": "fixture"}}

    node = PlanNode(
        id="standings", description="record", capability_hints=["standings"],
        arguments={"team_id": "1610612738"}, completion_test="one row")
    task = TaskSpec(
        goal="Boston record", mode="quick", deliverable="record",
        season=SeasonRef(value="2025-26", source="user", confidence=1))
    result = await ToolCapability(
        "standings", tools={"get_standings": Tool()}).execute(node, task, [])

    assert seen == {"team_id": "1610612738", "season": "2025-26"}
    assert result.capability == "standings"


@pytest.mark.anyio
async def test_seasonless_capability_does_not_receive_season():
    seen = {}

    class Tool:
        async def ainvoke(self, arguments):
            seen.update(arguments)
            return {"ok": True, "rows": {"players": [], "teams": []},
                    "meta": {"source": "fixture"}}

    node = PlanNode(
        id="resolve", description="resolve", capability_hints=["entity_resolution"],
        arguments={"query": "Boston"}, completion_test="one team")
    task = TaskSpec(
        goal="Boston record", mode="quick", deliverable="record",
        season=SeasonRef(value="2025-26", source="default", confidence=.8))
    await ToolCapability(
        "entity_resolution", tools={"resolve_entity": Tool()}).execute(node, task, [])
    assert seen == {"query": "Boston"}
