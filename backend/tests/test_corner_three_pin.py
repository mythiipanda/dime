import asyncio

from app.graph import _triage_seed


def drain(question):
    async def go():
        state = {"question": question, "history": [], "tool_results": [],
                 "calls_made": [], "round": 0}
        async for _ in _triage_seed(question, "primary", "model", state):
            pass
        return state
    return asyncio.run(go())


def test_corner_three_leader_is_pinned_to_zone_share_tool():
    state = drain("Which team leads the league in corner threes this season?")
    assert [call.split(":", 1)[0] for call in state["calls_made"]] == [
        "get_team_shot_zones"]
    answer = state["tool_results"][0]["meta"]["deterministic_answer"]
    assert "15.6%" in answer
    assert "+3.1 percentage points" in answer
    assert "3.1%" not in answer
