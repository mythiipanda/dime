import logging

import pytest

from v2.adapters.models import ModelIntake
from v2.contracts import ConversationTurn, IntakeAdmissionReview, TaskSpec


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


def _manifest(payload):
    return list(payload["expected_subjects"])


def _missing_binding_all(payload, subjects=None):
    return {
        "target": payload["target"],
        "decision": "block",
        "expected_subjects": payload["expected_subjects"],
        "findings": [
            {
                "code": "missing_binding",
                "affected_subjects": (
                    subjects if subjects is not None
                    else payload["expected_subjects"]
                ),
                "explanation": "No bindings were provided.",
            }
        ],
    }


def _sloppy_echo_missing_binding(payload):
    body = _missing_binding_all(payload)
    body["expected_subjects"] = _manifest(payload)[:-1]
    return body


def _bad_target_missing_binding(payload):
    body = _missing_binding_all(payload)
    target = dict(payload["target"])
    target["task_sha256"] = "d" * 64
    body["target"] = target
    return body


def _same_length_wrong_text_unresolved(payload):
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
                    "text": "XXXXXXX",
                },
            }
        ],
    }


def _shifted_offsets_unresolved(payload):
    text = "assists"
    start = payload["question"].index(text) + 1
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


def _subject_mismatch_sloppy_echo(payload):
    body = {
        "target": payload["target"],
        "decision": "block",
        "expected_subjects": payload["expected_subjects"],
        "findings": [
            {
                "code": "subject_mismatch",
                "affected_subjects": [_manifest(payload)[1]],
            }
        ],
    }
    body["expected_subjects"] = _manifest(payload)[:-1]
    return body


def _hallucinated_finding_only(payload):
    return {
        "target": payload["target"],
        "decision": "block",
        "expected_subjects": payload["expected_subjects"],
        "findings": [
            {
                "code": "subject_mismatch",
                "affected_subjects": [
                    {
                        "kind": "entity",
                        "entity_id": "invented-1",
                        "entity_type": "player",
                    }
                ],
            }
        ],
    }


def _valid_unresolved(payload):
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


def _substantiated_mismatch(payload):
    return {
        "target": payload["target"],
        "decision": "block",
        "expected_subjects": payload["expected_subjects"],
        "findings": [
            {
                "code": "subject_mismatch",
                "affected_subjects": [_manifest(payload)[1]],
            }
        ],
    }


@pytest.mark.anyio
async def test_sloppy_expected_subjects_echo_with_sound_judgment_is_advisory(caplog):
    model = _Model(_sloppy_echo_missing_binding)
    with caplog.at_level(logging.WARNING):
        task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert [call for call in model.calls] == ["intake", "intake_admission"]
    assert task.open_questions == []
    assert task.season is not None and task.season.value == "2025-26"
    assert task.metric_ids == ["AST"]
    assert task.requirements and task.requirements[0].id == "leader"
    assert any("expected subjects mismatch" in record.message for record in caplog.records)


@pytest.mark.anyio
async def test_stale_target_with_sound_judgment_is_advisory(caplog):
    model = _Model(_bad_target_missing_binding)
    with caplog.at_level(logging.WARNING):
        task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert task.open_questions == []
    assert task.season is not None and task.season.value == "2025-26"
    assert task.requirements and task.requirements[0].id == "leader"
    assert any("target mismatch" in record.message for record in caplog.records)


@pytest.mark.anyio
async def test_same_length_wrong_text_unresolved_is_advisory(caplog):
    model = _Model(_same_length_wrong_text_unresolved)
    with caplog.at_level(logging.WARNING):
        task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert task.open_questions == []
    assert task.season is not None and task.season.value == "2025-26"
    assert task.requirements and task.requirements[0].id == "leader"
    assert any("locator" in record.message for record in caplog.records)


@pytest.mark.anyio
async def test_shifted_offsets_unresolved_is_advisory():
    model = _Model(_shifted_offsets_unresolved)
    task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert task.open_questions == []
    assert task.season is not None and task.season.value == "2025-26"
    assert task.requirements and task.requirements[0].id == "leader"


@pytest.mark.anyio
async def test_out_of_range_context_turn_unresolved_is_advisory():
    context = (
        ConversationTurn(role="user", content="Tell me about assists leaders."),
    )

    def factory(payload):
        return {
            "target": payload["target"],
            "decision": "block",
            "expected_subjects": payload["expected_subjects"],
            "unresolved_references": [
                {
                    "kind": "entity",
                    "locator": {
                        "source": "context",
                        "context_turn": 7,
                        "start": 0,
                        "end": 3,
                        "text": "foo",
                    },
                }
            ],
        }

    model = _Model(factory)
    task = await ModelIntake(model, **_kwargs()).understand(REQUEST, context=context)
    assert task.open_questions == []
    assert task.season is not None and task.season.value == "2025-26"


@pytest.mark.anyio
async def test_hallucinated_finding_subjects_are_advisory():
    model = _Model(_hallucinated_finding_only)
    task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert task.open_questions == []
    assert task.season is not None and task.season.value == "2025-26"
    assert task.requirements and task.requirements[0].id == "leader"


@pytest.mark.anyio
async def test_locator_valid_unresolved_reference_still_blocks():
    model = _Model(_valid_unresolved)
    task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert task.open_questions == ["The request contains an unresolved reference."]
    assert task.season is None
    assert task.requirements == []


@pytest.mark.anyio
async def test_substantiated_subject_mismatch_still_blocks():
    model = _Model(_substantiated_mismatch)
    task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert task.open_questions == ["subject_mismatch"]
    assert task.season is None
    assert task.requirements == []


@pytest.mark.anyio
async def test_sloppy_echo_with_substantiated_mismatch_still_blocks_without_error_leak():
    model = _Model(_subject_mismatch_sloppy_echo)
    task = await ModelIntake(model, **_kwargs()).understand(REQUEST)
    assert task.open_questions == ["subject_mismatch"]
    assert task.season is None
    assert task.requirements == []


def _task_and_review(review_body, request=REQUEST, context=()):
    task = TaskSpec.model_validate(INTAKE_TASK)
    review = IntakeAdmissionReview.model_validate(review_body)
    return task, review, request, context


def test_apply_review_admit_with_sloppy_echo_still_blocks():
    task = TaskSpec.model_validate(INTAKE_TASK)
    subjects = [item.model_dump(mode="json")
                for item in ModelIntake._expected_admission_subjects(task)]
    review = IntakeAdmissionReview.model_validate({
        "target": ModelIntake._review_target(REQUEST, (), task).model_dump(mode="json"),
        "decision": "admit",
        "expected_subjects": subjects[:-1],
        "bindings": [
            {
                "subject": subject,
                "locator": {
                    "source": "request",
                    "context_turn": None,
                    "start": 0,
                    "end": len(REQUEST),
                    "text": REQUEST,
                },
            }
            for subject in subjects[:-1]
        ],
    })
    blocked = ModelIntake._apply_review(review, REQUEST, (), task)
    assert blocked.open_questions == [
        "review expected subjects do not match proposed task"
    ]
    assert blocked.season is None
    assert blocked.requirements == []


def test_apply_review_valid_unresolved_with_sloppy_echo_blocks_without_error_leak():
    task = TaskSpec.model_validate(INTAKE_TASK)
    subjects = [item.model_dump(mode="json")
                for item in ModelIntake._expected_admission_subjects(task)]
    text = "assists"
    start = REQUEST.index(text)
    review = IntakeAdmissionReview.model_validate({
        "target": ModelIntake._review_target(REQUEST, (), task).model_dump(mode="json"),
        "decision": "block",
        "expected_subjects": subjects[:-1],
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
    })
    blocked = ModelIntake._apply_review(review, REQUEST, (), task)
    assert blocked.open_questions == ["The request contains an unresolved reference."]
    assert blocked.season is None
