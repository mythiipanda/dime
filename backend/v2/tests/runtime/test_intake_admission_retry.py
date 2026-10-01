import logging

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
        "intake_admission": True,
    }


class _Model:
    def __init__(self, intake_task, admission_factories):
        self.intake_task = intake_task
        self.admission_factories = list(admission_factories)
        self.calls = []

    async def generate(self, **call):
        route = call["envelope"].route
        self.calls.append(route)
        if route == "intake":
            return call["schema"].model_validate(self.intake_task)
        if route == "intake_admission":
            factory = self.admission_factories.pop(0)
            return call["schema"].model_validate(factory(call["payload"]))
        raise AssertionError(route)


def _phantom_unresolved(payload):
    text = "assists"
    start = payload["question"].index(text)
    return {
        "target": payload["target"],
        "decision": "block",
        "expected_subjects": payload["expected_subjects"],
        "unresolved_references": [
            {
                "kind": "unknown",
                "locator": {
                    "source": "request",
                    "context_turn": None,
                    "start": start,
                    "end": start + len(text),
                    "text": text,
                },
            }
        ],
    }


def _missing_binding_only(payload):
    return {
        "target": payload["target"],
        "decision": "block",
        "expected_subjects": payload["expected_subjects"],
        "findings": [
            {
                "code": "missing_binding",
                "affected_subjects": payload["expected_subjects"],
                "explanation": "No bindings were provided.",
            }
        ],
    }


@pytest.mark.anyio
async def test_phantom_block_then_clean_resample_admits(caplog):
    model = _Model(INTAKE_TASK, [_phantom_unresolved, _missing_binding_only])
    with caplog.at_level(logging.WARNING):
        task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert model.calls == ["intake", "intake_admission", "intake_admission"]
    assert task.open_questions == []
    assert task.season is not None and task.season.value == "2025-26"
    assert task.metric_ids == ["AST"]
    assert task.requirements and task.requirements[0].id == "leader"
    assert any("resampling" in record.message for record in caplog.records)


@pytest.mark.anyio
async def test_repeated_block_still_blocks():
    model = _Model(INTAKE_TASK, [_phantom_unresolved, _phantom_unresolved])
    task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert model.calls == ["intake", "intake_admission", "intake_admission"]
    assert task.open_questions == ["The request contains an unresolved reference."]
    assert task.season is None
    assert task.requirements == []


@pytest.mark.anyio
async def test_no_resample_when_intake_itself_uncertain():
    intake_task = {**INTAKE_TASK, "open_questions": ["Which season should be used instead?"]}
    model = _Model(intake_task, [_missing_binding_only])
    task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert model.calls == ["intake", "intake_admission"]
    assert task.open_questions == ["Which season should be used instead?"]
