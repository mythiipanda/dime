import json

import pytest
from openai import AsyncOpenAI
from pydantic import TypeAdapter, ValidationError
from pydantic_ai.models import OutputObjectDefinition
from pydantic_ai.providers.openai import OpenAIProvider
from v2.adapters.models import DimeOpenAIChatModel
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


def _forbidden_paths(value):
    found = []

    def visit(node, path):
        if isinstance(node, dict):
            for key in ("const", "discriminator"):
                if key in node:
                    found.append(f"{path}.{key}")
            for key, child in node.items():
                visit(child, f"{path}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{path}[{index}]")

    visit(value, "$")
    return sorted(found)


class _CapturingWireModel:
    def __init__(self):
        self.wire_schemas = []

    async def generate(self, **call):
        self.wire_schemas.append(
            _wire_schema(
                call["schema"].model_json_schema(), call["schema"].__name__
            )
        )
        return call["schema"].model_validate(
            {"goal": "g", "mode": "quick", "deliverable": "d"}
        )


@pytest.mark.anyio
async def test_understand_wire_schema_holds_no_gemini_rejected_keys():
    from v2.adapters.models import ModelIntake

    model = _CapturingWireModel()
    intake = ModelIntake(
        model,
        provider="stub",
        model_name="stub-model",
        capability_catalog={},
    )
    task = await intake.understand("What is Boston's record?")
    assert task.goal == "g"
    assert len(model.wire_schemas) == 1
    assert _forbidden_paths(model.wire_schemas[0]) == []


def test_const_becomes_single_value_enum_with_shape_preserved():
    schema = {
        "type": "object",
        "properties": {
            "kind": {"const": "bool", "title": "Kind", "type": "string"},
        },
        "required": ["kind"],
    }
    before = json.dumps(schema, sort_keys=True)
    wire = _wire_schema(schema, "Probe")
    assert wire["properties"]["kind"] == {
        "enum": ["bool"],
        "title": "Kind",
        "type": "string",
    }
    assert _forbidden_paths(wire) == []
    assert json.dumps(schema, sort_keys=True) == before


def test_taskspec_wire_turns_kind_consts_into_enums_preserves_oneof():
    schema = TypeAdapter(TaskSpec).json_schema()
    assert schema["$defs"]["BoolArg"]["properties"]["kind"] == {
        "const": "bool",
        "title": "Kind",
        "type": "string",
    }
    before = json.dumps(schema, sort_keys=True)
    wire = _wire_schema(schema, "TaskSpec")
    assert wire["$defs"]["BoolArg"]["properties"]["kind"] == {
        "enum": ["bool"],
        "title": "Kind",
        "type": "string",
    }
    assert _forbidden_paths(wire) == []
    assert len(wire["$defs"]["RequirementArguments"]["properties"]["entries"]["items"]["oneOf"]) == 11
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
