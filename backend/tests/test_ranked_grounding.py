"""F88 deterministic qualification and named-team ratings routes."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.graph import _triage_seed
from app.tools import get_leaders


def _drain(q):
    async def go():
        state = {"question": q, "history": [], "tool_results": [],
                 "calls_made": [], "round": 0}
        async for _ in _triage_seed(q, "p", "m", state):
            pass
        return state
    return asyncio.run(go())


def test_three_point_percentage_uses_official_makes_floor():
    out = get_leaders.invoke({"stat_category": "FG3_PCT"})
    assert out["ok"] and out["rows"][0]["PLAYER"] == "Luke Kennard"
    assert out["rows"][0]["FG3_PCT"] == 0.478
    assert out["meta"]["qualification"] == "82+ made threes"
    assert "47.8%" in out["meta"]["deterministic_answer"]


def test_three_point_prompt_forces_leader_tool():
    st = _drain("Who leads the league in 3P% this season?")
    assert [c.split(":")[0] for c in st["calls_made"]] == ["get_leaders"]
    assert st["tool_results"][0]["rows"][0]["PLAYER"] == "Luke Kennard"


def test_named_team_ratings_is_one_call():
    st = _drain("Warriors ratings?")
    assert [c.split(":")[0] for c in st["calls_made"]] == ["get_ratings"]
    out = st["tool_results"][0]
    assert len(out["rows"]) == 1
    assert out["rows"][0]["TEAM"] == "GSW"
    assert "113.8 offense" in out["meta"]["deterministic_answer"]
    assert "114.4 defense" in out["meta"]["deterministic_answer"]
