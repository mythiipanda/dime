import pytest

from v2.adapters.models import ModelIntake, ModelPlanner
from v2.contracts import Plan, RunMode, TaskSpec
from v2.runtime.ledger import RequestEnvelope


class SelectionModel:
    def __init__(self, skill):
        self.skill = skill
        self.calls = []

    async def generate(self, *, schema, prompt, payload, envelope):
        self.calls.append((schema, payload, envelope))
        if schema is TaskSpec:
            return TaskSpec(goal="test", mode=RunMode.QUICK,
                            deliverable="answer", skills=[self.skill] if self.skill else [])
        return Plan(nodes=[])


@pytest.mark.parametrize("question,expected", [
    ("Would Brown for Paul George make sense for both teams?", "trade-analysis"),
    ("How much does Tatum's absence change Boston?", "injury-impact"),
    ("Compare Brown and Paul George as second options", "player-comparison"),
])
@pytest.mark.anyio
async def test_should_trigger_selected_skill_is_loaded_for_planning(question, expected):
    model = SelectionModel(expected)
    intake = ModelIntake(model, provider="test", model_name="test",
                         capability_catalog={})
    task = await intake.understand(question)
    catalog = model.calls[0][1]["skill_catalog"]
    assert expected in {item["name"] for item in catalog}
    assert "instructions" not in str(catalog)

    planner = ModelPlanner(model, provider="test", model_name="test",
                           capability_catalog={})
    await planner.plan(task)
    activated = model.calls[1][1]["skills"]
    assert [item["name"] for item in activated] == [expected]
    assert model.calls[1][2].skill_hashes[expected] == activated[0]["content_hash"]


@pytest.mark.anyio
async def test_should_not_trigger_general_fact_question_loads_no_skill():
    model = SelectionModel(None)
    intake = ModelIntake(model, provider="test", model_name="test",
                         capability_catalog={})
    task = await intake.understand("What was Boston's record?")
    planner = ModelPlanner(model, provider="test", model_name="test",
                           capability_catalog={})
    await planner.plan(task)
    assert model.calls[1][1]["skills"] == []
    assert model.calls[1][2].skill_hashes == {}


@pytest.mark.anyio
async def test_hallucinated_selection_fails_before_planning():
    model = SelectionModel("not-installed")
    intake = ModelIntake(model, provider="test", model_name="test",
                         capability_catalog={})
    with pytest.raises(ValueError, match="unknown skills"):
        await intake.understand("anything")
