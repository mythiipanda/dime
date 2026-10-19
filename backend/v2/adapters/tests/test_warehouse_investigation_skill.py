import pytest

from v2.adapters.models import ModelIntake, ModelPlanner
from v2.contracts import Plan, RunMode, TaskSpec
from v2.skills import SkillLibrary, skill_hashes

SKILL = "warehouse-investigation"

class InvestigationModel:
    def __init__(self):
        self.calls = []

    async def generate(self, *, schema, prompt, payload, envelope, decode=None):
        self.calls.append((schema, payload, envelope))
        if schema is TaskSpec:
            return TaskSpec(goal="investigate", mode=RunMode.QUICK,
                            deliverable="answer", skills=[SKILL])
        return Plan(nodes=[])

def test_warehouse_investigation_skill_is_discoverable_metadata_only():
    library = SkillLibrary()
    catalog = library.catalog()
    entry = next(item for item in catalog if item["name"] == SKILL)
    assert set(entry) == {"name", "description"}
    assert entry["description"]
    assert "instructions" not in str(catalog)

def test_warehouse_investigation_activation_body_hash_and_resources():
    library = SkillLibrary()
    skill = library.skills[SKILL]
    activated = library.activate([SKILL])
    assert len(activated) == 1
    context = activated[0]
    assert context["name"] == SKILL
    assert context["instructions"] == skill.body
    assert len(context["content_hash"]) == 64
    assert context["resources"] == []
    assert skill_hashes(activated) == {SKILL: context["content_hash"]}

@pytest.mark.anyio
async def test_warehouse_investigation_reaches_intake_and_planner_requests():
    model = InvestigationModel()
    intake = ModelIntake(model, provider="test", model_name="test",
                         capability_catalog={})
    task = await intake.understand("line up the evidence for this roster decision")
    assert SKILL in {item["name"] for item in model.calls[0][1]["skill_catalog"]}

    planner = ModelPlanner(model, provider="test", model_name="test",
                           capability_catalog={})
    await planner.plan(task)
    activated = model.calls[1][1]["skills"]
    assert [item["name"] for item in activated] == [SKILL]
    assert "Cite issued evidence" in activated[0]["instructions"]
    assert model.calls[1][2].skill_hashes[SKILL] == activated[0]["content_hash"]
