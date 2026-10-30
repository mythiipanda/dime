import json

import pytest
from openai import AsyncOpenAI
from pydantic import TypeAdapter, ValidationError
from v2.arguments import PlannerOutputWire
from v2.contracts import EvidenceRequirement, TaskSpec

UNION_LITERAL = {
    "type": "object",
    "properties": {
        "subjects": {
            "type": "array",
            "minItems": 1,
            "maxItems": 128,
            "items": {
                "discriminator": {
                    "propertyName": "kind",
                    "mapping": {
                        "task": "#/$defs/TaskSubject",
                        "entity": "#/$defs/EntitySubject",
                    },
                },
                "oneOf": [
                    {"$ref": "#/$defs/TaskSubject"},
                    {"$ref": "#/$defs/EntitySubject"},
                ],
            },
        },
        "tags": {
            "type": "array",
            "maxItems": 16,
            "items": {"type": "string"},
        },
    },
    "required": ["subjects", "tags"],
}

STRIPPED_LITERAL = {
    "type": "object",
    "properties": {
        "subjects": {
            "type": "array",
            "items": {
                "oneOf": [
                    {"$ref": "#/$defs/TaskSubject"},
                    {"$ref": "#/$defs/EntitySubject"},
                ],
            },
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["subjects", "tags"],
}


def test_pydantic_rejects_too_many_skills():
    with pytest.raises(ValidationError) as exc_info:
        TypeAdapter(TaskSpec).validate_python(
            {
                "goal": "g",
                "mode": "quick",
                "deliverable": "d",
                "skills": [f"s{i}" for i in range(17)],
            }
        )
    assert ("skills",) in [
        tuple(error["loc"])
        for error in exc_info.value.errors(include_url=False)
        if error["type"] == "too_long"
    ]

def test_pydantic_rejects_empty_capability_options():
    with pytest.raises(ValidationError) as exc_info:
        TypeAdapter(EvidenceRequirement).validate_python(
            {"id": "a1", "description": "d", "capability_options": []}
        )
    assert ("capability_options",) in [
        tuple(error["loc"])
        for error in exc_info.value.errors(include_url=False)
        if error["type"] == "too_short"
    ]
