import json

import pytest
from openai import AsyncOpenAI
from pydantic import TypeAdapter, ValidationError
from pydantic_ai.models import OutputObjectDefinition
from pydantic_ai.providers.openai import OpenAIProvider
from v2.adapters.models import DimeOpenAIChatModel
from v2.arguments import PlannerOutputWire
from v2.contracts import EvidenceRequirement, IntakeAdmissionReview, TaskSpec


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
            "items": {"type": "string"},
        },
    },
    "required": ["subjects", "tags"],
}


def _make_model():
    return DimeOpenAIChatModel(
        "t",
        provider=OpenAIProvider(
            openai_client=AsyncOpenAI(api_key="x", base_url="http://127.0.0.1:1")
        ),
    )


def _wire_schema(schema, name):
    return _make_model()._map_json_schema(
        OutputObjectDefinition(
            json_schema=schema, name=name, strict=True
        )
    )["json_schema"]["schema"]


def _bound_paths(value):
    found = []

    def visit(node, path):
        if isinstance(node, dict):
            if "minItems" in node or "maxItems" in node:
                found.append(path)
            for key, child in node.items():
                visit(child, f"{path}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{path}[{index}]")

    visit(value, "$")
    return sorted(found)


def test_union_item_array_bounds_dropped_with_shape_preserved():
    assert _wire_schema(UNION_LITERAL, "Probe") == STRIPPED_LITERAL


def test_plain_string_array_bounds_dropped_with_shape_preserved():
    wire = _wire_schema(UNION_LITERAL, "Probe")
    assert wire["properties"]["tags"] == {"type": "array", "items": {"type": "string"}}


def test_wire_schema_holds_no_bounds_anywhere():
    assert _bound_paths(_wire_schema(UNION_LITERAL, "Probe")) == []


def test_intake_review_wire_drops_union_bounds_preserves_oneof():
    schema = TypeAdapter(IntakeAdmissionReview).json_schema()
    node = schema["properties"]["expected_subjects"]
    assert node["minItems"] == 1
    assert node["maxItems"] == 128
    assert len(node["items"]["oneOf"]) == 6
    before = json.dumps(schema, sort_keys=True)
    wire = _wire_schema(schema, "IntakeAdmissionReview")
    wired = wire["properties"]["expected_subjects"]
    assert wired == {
        "type": "array",
        "title": node["title"],
        "items": node["items"],
    }
    assert _bound_paths(wire) == []
    assert json.dumps(schema, sort_keys=True) == before


def test_taskspec_wire_drops_plain_array_bound_preserves_items():
    schema = TypeAdapter(TaskSpec).json_schema()
    assert schema["properties"]["skills"]["maxItems"] == 16
    before = json.dumps(schema, sort_keys=True)
    wire = _wire_schema(schema, "TaskSpec")
    assert wire["properties"]["skills"] == {
        "type": "array",
        "title": "Skills",
        "items": {"type": "string"},
    }
    assert _bound_paths(wire) == []
    assert json.dumps(schema, sort_keys=True) == before


def test_planner_wire_path_drops_bounds():
    schema = TypeAdapter(PlannerOutputWire).json_schema()
    assert _bound_paths(schema) != []
    before = json.dumps(schema, sort_keys=True)
    wire = _wire_schema(schema, "PlannerOutputWire")
    assert _bound_paths(wire) == []
    assert "nodes" in wire["properties"]
    assert json.dumps(schema, sort_keys=True) == before


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
