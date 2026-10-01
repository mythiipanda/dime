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
    def __init__(self, admission_factory):
        self.admission_factory = admission_factory
        self.calls = []

    async def generate(self, **call):
        route = call["envelope"].route
        self.calls.append(route)
        if route == "intake":
            return call["schema"].model_validate(INTAKE_TASK)
        if route == "intake_admission":
            return call["schema"].model_validate(
                self.admission_factory(call["payload"])
            )
        raise AssertionError(route)


def _missing_binding_block(payload):
    return {
        "target": payload["target"],
        "decision": "block",
        "expected_subjects": payload["expected_subjects"],
        "bindings": [],
        "findings": [
            {
                "code": "missing_binding",
                "affected_subjects": payload["expected_subjects"],
                "explanation": (
                    "No bindings were provided for the expected subjects."
                ),
            }
        ],
    }


def _unresolved_block(payload):
    body = payload["question"]
    text = "assists"
    start = body.index(text)
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


@pytest.mark.anyio
async def test_missing_binding_only_block_is_advisory(caplog):
    model = _Model(_missing_binding_block)
    with caplog.at_level(logging.WARNING):
        task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert [call for call in model.calls] == ["intake", "intake_admission"]
    assert task.open_questions == []
    assert task.season is not None and task.season.value == "2025-26"
    assert task.metric_ids == ["AST"]
    assert task.requirements and task.requirements[0].id == "leader"
    assert any(
        "missing_binding" in record.message for record in caplog.records
    )


@pytest.mark.anyio
async def test_unresolved_reference_block_still_clears_task():
    model = _Model(_unresolved_block)
    task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert task.season is None
    assert task.requirements == []
    assert task.open_questions and any(
        "unresolved reference" in question.casefold()
        for question in task.open_questions
    )
