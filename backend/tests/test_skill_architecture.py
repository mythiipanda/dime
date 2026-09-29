
import asyncio
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph as graph_module  # noqa: E402
from app.graph import build_planner_prompt, select_skills  # noqa: E402
from app.skills import catalog, load_skill  # noqa: E402


class _FakeLLM:
    def __init__(self, text):
        self._text = text
        self.seen = None

    async def ainvoke(self, msgs):
        self.seen = msgs
        class _R:
            pass
        r = _R()
        r.content = self._text
        return r


class _FailingLLM:
    async def ainvoke(self, msgs):
        raise RuntimeError("llm down")


def test_select_skills_returns_expected():
    llm = _FakeLLM('["leaders_read", "compare_players"]')
    out = asyncio.run(select_skills("Who leads the league in scoring?", llm))
    assert out == ["leaders_read", "compare_players"]


def test_select_skills_filters_unknown_names():
    llm = _FakeLLM('["leaders_read", "not_a_skill"]')
    out = asyncio.run(select_skills("Who leads the league?", llm))
    assert out == ["leaders_read"]


def test_select_skills_returns_empty_on_failure():
    assert asyncio.run(select_skills("anything", _FailingLLM())) == []


def test_select_skills_returns_empty_on_bad_json():
    llm = _FakeLLM("no json here")
    assert asyncio.run(select_skills("anything", llm)) == []


def test_no_keyword_routing():
    assert not hasattr(graph_module, "SKILL_KEYWORDS")
    assert not hasattr(graph_module, "match_skills")


def test_build_planner_prompt_accepts_selected_skills():
    sig = inspect.signature(build_planner_prompt)
    assert "selected_skills" in sig.parameters
    prompt = build_planner_prompt("Who leads the league in scoring?",
                                  ["leaders_read"])
    assert "never multiply a per-game average" in prompt.lower()
    assert "rows.record over ALL matches" not in prompt


def test_build_planner_prompt_empty_selection_carries_no_bodies():
    prompt = build_planner_prompt("How tall is Victor Wembanyama?", [])
    assert "Pitfalls" not in catalog()
    assert "Pitfalls" not in prompt
    for name in ("compare_players", "leaders_read", "record_when_plays",
                 "historical_leaders", "impact_check"):
        assert load_skill(name) not in prompt
