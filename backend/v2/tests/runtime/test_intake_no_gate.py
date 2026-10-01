import pytest

from v2.adapters.models import ModelIntake


REQUEST = "Who led the NBA in assists in the 2025-26 season, and how many?"


INTAKE_TASK = {
    "goal": "assists leader",
    "mode": "quick",
    "deliverable": "leader and value",
    "season": {"value": "2025-26", "source": "user", "confidence": 1.0},
    "metric_ids": ["AST"],
    "requested_outputs": ["AST"],
    "requirements": [
        {
            "id": "leader",
            "description": "assists leader",
            "capability_options": ["standings"],
            "metric_ids": ["AST"],
            "requested_outputs": ["AST"],
        }
    ],
}


def _kwargs():
    return {
        "provider": "stub",
        "model_name": "stub-model",
        "capability_catalog": {"standings": {}},
        "requirement_review": False,
    }


class _Model:
    def __init__(self, task):
        self.task = task
        self.calls = []

    async def generate(self, **call):
        self.calls.append(call["envelope"].route)
        return call["schema"].model_validate(self.task)


@pytest.mark.anyio
async def test_understand_makes_exactly_one_model_call_and_admits():
    model = _Model(INTAKE_TASK)
    task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert model.calls == ["intake"]
    assert task.open_questions == []
    assert task.season is not None and task.season.value == "2025-26"
    assert task.metric_ids == ["AST"]
    assert task.requirements and task.requirements[0].id == "leader"


@pytest.mark.anyio
async def test_empty_task_admits_without_review_second_pass():
    model = _Model({
        "goal": "assists leader",
        "mode": "quick",
        "deliverable": "leader and value",
    })
    task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert model.calls == ["intake"]
    assert task.open_questions == []
    assert task.entities == []
    assert task.requirements == []


def test_intake_admission_flag_is_gone():
    model = _Model(INTAKE_TASK)
    with pytest.raises(TypeError):
        ModelIntake(model, **{**_kwargs(), "intake_admission": True})


@pytest.mark.anyio
async def test_verify_mechanical_still_runs_downstream_unchanged():
    from datetime import UTC, datetime

    from v2.adapters.models import ModelSynthesizer
    from v2.contracts import EvidenceEnvelope
    from v2.domain.calculations import Calculation
    from v2.runtime.verifier import verify_mechanical

    model = _Model({
        "goal": "highest offense",
        "mode": "quick",
        "deliverable": "team and value",
        "requirements": [
            {
                "id": "metric",
                "description": "offensive rating board",
                "capability_options": ["team_ratings"],
                "capability_arguments": {
                    "requested_metric": "OFF_RATING",
                    "ranking_direction": "desc",
                },
            }
        ],
        "calculation_requirements": [
            {
                "id": "top",
                "description": "maximum offensive rating",
                "metric_ids": ["OFF_RATING"],
            }
        ],
    })
    task = await ModelIntake(
        model, provider="stub", model_name="stub-model",
        capability_catalog={"team_ratings": {}},
        requirement_review=False,
    ).understand("Which team had the highest offensive rating in 2025-26?")
    assert model.calls == ["intake"]
    assert task.open_questions == []
    evidence = EvidenceEnvelope(
        evidence_id="ratings", capability="team_ratings", source="fixture",
        observed_at=datetime.now(UTC), season="2025-26",
        qualification="all teams", coverage="full board",
        rows=[
            {"TEAM_NAME": "Cleveland Cavaliers", "OFF_RATING": 121.2},
            {"TEAM_NAME": "Boston Celtics", "OFF_RATING": 119.5},
            {"TEAM_NAME": "Denver Nuggets", "OFF_RATING": 118.0},
        ],
        metric_definitions={"__requested_metric__": "OFF_RATING"})
    draft = await ModelSynthesizer(
        model, provider="stub", model_name="stub").synthesize(task, [evidence])
    assert "Cleveland Cavaliers" in draft.claims[0].text
    assert "121.2" in draft.claims[0].text
    assert draft.calculations[0].result == 1
    calculations = [
        Calculation.model_validate(
            {key: value for key, value in item.model_dump().items()
             if key != "requirement_id"})
        for item in draft.calculations
    ]
    result = verify_mechanical(task, draft, [evidence], calculations)
    assert result.status.value == "pass"
    assert result.claim_results[0].supported is True
