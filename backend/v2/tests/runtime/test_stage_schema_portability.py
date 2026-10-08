from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field
from pydantic_ai.providers.openai import OpenAIProvider
from v2.adapters.models import (
    MODEL_ROUTES,
    DimeOpenAIChatModel,
    ModelIntake,
    ModelPlanner,
    ModelRepairer,
    ModelSemanticVerifier,
    ModelStage,
    ModelSynthesizer,
    ProviderStructuredModel,
    ReasoningContentFallbackClient,
    strict_output_json_schema,
)
from v2.adapters.structured import (
    EndpointCapabilities,
    OutputStrategy,
    SchemaNotPortable,
    Support,
    strict_subset_violations,
    value_space_widened,
    wire_schema_for,
)
from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    EvidenceEnvelope,
    TaskSpec,
    VerificationReport,
)
from v2.runtime import RequestEnvelope

CAPABILITIES = {
    "qualified_leaders": {
        "arguments": {"type": "object", "additionalProperties": False,
                      "properties": {}, "required": []},
        "description": "Qualified statistical leaders for one season.",
    },
}
LADDER = (
    (OutputStrategy.STRICT_SCHEMA, Support.MEASURED, Support.MEASURED,
     Support.MEASURED),
    (OutputStrategy.TOOL_CALL, Support.REFUSED, Support.MEASURED,
     Support.REFUSED),
)

class StageBoundary(BaseException):
    pass

class RecordingStructuredModel:
    def __init__(self) -> None:
        self.schemas: dict[str, type[BaseModel]] = {}

    async def generate(self, *, schema, prompt, payload, envelope,
                       decode=None) -> Any:
        self.schemas.setdefault(envelope.route, schema)
        raise StageBoundary(envelope.route)

def _task() -> TaskSpec:
    return TaskSpec.model_validate({
        "goal": "Report the 2024-25 assists leader.",
        "mode": "quick",
        "deliverable": "The assists leader with games played.",
        "required_evidence": ["qualified_leaders"],
    })

def _draft() -> DraftReport:
    return DraftReport.model_validate({
        "sections": ["Assists leader"],
        "claims": [Claim(text="The assists leader led the league.",
                         kind=ClaimKind.OBSERVED, evidence_ids=["evidence:n1"])],
    })

def _verification() -> VerificationReport:
    return VerificationReport.model_validate({"status": "pass"})

def _representative_payload(schema: type[BaseModel]) -> Any:
    if issubclass(schema, DraftReport):
        return {"sections": ["Assists leader"], "claims": [], "calculations": [],
                "blocked_calculation_requirement_ids": [], "gaps": []}
    if issubclass(schema, VerificationReport):
        return {"status": "pass", "claim_results": [], "missing_branches": [],
                "contradictions": [], "repair_instructions": []}
    return {}

def _evidence(task: TaskSpec) -> dict[str, EvidenceEnvelope]:
    return {"evidence:n1": EvidenceEnvelope(
        evidence_id="evidence:n1", capability="qualified_leaders",
        source="fake", observed_at=datetime.now(UTC),
        season=task.season.value if task.season else None, rows=[])}

def _stages() -> tuple[RecordingStructuredModel, dict[str, ModelStage]]:
    model = RecordingStructuredModel()
    return model, {
        "intake": ModelIntake(model, provider="probe", model_name="probe-model",
                              capability_catalog=CAPABILITIES),
        "planner": ModelPlanner(model, provider="probe",
                                model_name="probe-model",
                                capability_catalog=CAPABILITIES),
        "synthesizer": ModelSynthesizer(model, provider="probe",
                                       model_name="probe-model"),
        "repair": ModelRepairer(model, provider="probe",
                                model_name="probe-model"),
        "semantic_verifier": ModelSemanticVerifier(model, provider="probe",
                                                   model_name="probe-model"),
    }

async def stage_schemas() -> dict[str, type[BaseModel]]:
    recorded, stages = _stages()
    task, draft, evidence = _task(), _draft(), _evidence(_task())
    question = "who led the league in assists in 2024-25?"
    for call in (
        lambda: stages["intake"].understand(question),
        lambda: stages["intake"]._review_requirements(question, task),
        lambda: stages["planner"].plan(task),
        lambda: stages["synthesizer"].synthesize(task, list(evidence.values())),
        lambda: stages["repair"].repair(task, draft, evidence, _verification()),
        lambda: stages["semantic_verifier"].verify(task, draft, evidence),
    ):
        with pytest.raises(StageBoundary):
            await call()
    assert set(recorded.schemas) == set(MODEL_ROUTES), recorded.schemas
    return recorded.schemas

def _capabilities(strict: Support, tools: Support,
                  strict_tools: Support | None = None) -> EndpointCapabilities:
    return EndpointCapabilities(
        endpoint="https://probe.invalid/v1", strict_json_schema=strict,
        tool_calling=tools,
        strict_tool_definitions=tools if strict_tools is None else strict_tools)

def _completion(payload: Any) -> dict[str, Any]:
    return {"id": "completion-1", "created": 1, "model": "probe-model",
            "object": "chat.completion",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant",
                                     "content": json.dumps(payload)}}]}

async def sent_wire_schemas(
        schema: type[BaseModel], payload: Any,
        strict: Support = Support.MEASURED,
        tools: Support = Support.MEASURED,
        strict_tools: Support | None = None) -> dict[OutputStrategy, Any]:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=_completion(payload))

    chat_model = DimeOpenAIChatModel(
        "probe-model",
        provider=OpenAIProvider(openai_client=ReasoningContentFallbackClient(
            api_key="placeholder", max_retries=0,
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(handler)))),
        capabilities=_capabilities(strict, tools, strict_tools))
    model = ProviderStructuredModel("probe", "probe-model")
    model._models = lambda: [("probe", chat_model)]
    envelope = RequestEnvelope.freeze(
        provider="probe", model="probe-model", route="synthesizer", prompt="p",
        context={}, tool_schemas=schema.model_json_schema(),
        planner_version="v2")
    try:
        await model.generate(schema=schema, prompt="p", payload={},
                             envelope=envelope)
    except RuntimeError:
        assert sent, "no request reached the transport"
    body = sent[0]
    if body.get("tools"):
        return {OutputStrategy.TOOL_CALL:
                body["tools"][0]["function"]["parameters"]}
    response_format = body["response_format"]["json_schema"]
    return {OutputStrategy.STRICT_SCHEMA: response_format["schema"]}

def assert_portable(wire: dict[str, Any], contract: type[BaseModel],
                    label: str) -> None:
    Draft202012Validator.check_schema(wire)
    assert strict_subset_violations(wire) == (), label
    assert value_space_widened(contract.model_json_schema(), wire) == (), label

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_the_guard_reads_every_model_route_from_the_running_code():
    schemas = await stage_schemas()
    assert set(schemas) == set(MODEL_ROUTES)
    assert schemas["synthesizer"] is DraftReport
    assert schemas["semantic_verifier"] is VerificationReport

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize("strategy,strict,tools,strict_tools", LADDER)
async def test_the_schema_each_stage_sends_is_portable(
        strategy, strict, tools, strict_tools):
    for route, schema in (await stage_schemas()).items():
        payload = _representative_payload(schema)
        sent = await sent_wire_schemas(schema, payload, strict, tools,
                                       strict_tools)
        assert set(sent) == {strategy}, route
        assert_portable(sent[strategy], schema, route)

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize("strategy,strict,tools,strict_tools", LADDER)
async def test_the_schema_each_stage_probe_sends_is_portable(
        strategy, strict, tools, strict_tools):
    for route, schema in (await stage_schemas()).items():
        sanitized = wire_schema_for(strategy, schema.model_json_schema())
        assert_portable(sanitized.schema, schema, route)

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_the_wire_is_the_sanitized_production_schema():
    for route, schema in (await stage_schemas()).items():
        sent = await sent_wire_schemas(schema, _representative_payload(schema))
        assert sent[OutputStrategy.STRICT_SCHEMA] == wire_schema_for(
            OutputStrategy.STRICT_SCHEMA,
            strict_output_json_schema(schema)).schema, route

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_no_value_the_contract_refuses_is_reachable_through_the_wire():
    declared = DraftReport.model_json_schema()
    wire = wire_schema_for(OutputStrategy.STRICT_SCHEMA, declared).schema
    base = {"sections": ["Assists leader"], "claims": [], "calculations": [],
            "blocked_calculation_requirement_ids": [], "gaps": [],
            "artifacts": []}
    assert Draft202012Validator(wire).is_valid(base)
    for field in ("gaps", "calculations", "blocked_calculation_requirement_ids",
                 "artifacts"):
        instance = {**base, field: None}
        assert not Draft202012Validator(wire).is_valid(instance), field
        with pytest.raises(ValueError):
            DraftReport.model_validate(instance)

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_the_guard_catches_an_unportable_field_added_to_a_stage(
        monkeypatch):
    class UnportableDraft(DraftReport):
        share: Decimal = Decimal("0.5")
        note: str = Field(json_schema_extra={"pattern": r"^(?!x)y$"})

    monkeypatch.setattr(ModelSynthesizer, "schema", UnportableDraft)
    with pytest.raises(SchemaNotPortable) as caught:
        wire_schema_for(OutputStrategy.STRICT_SCHEMA,
                        UnportableDraft.model_json_schema())
    assert caught.value.construct == "pattern"
    assert caught.value.path == "$.properties.note"
    assert str(caught.value) == (
        "pattern at $.properties.note has no portable form: "
        r"look-around cannot be compiled: '^(?!x)y$'")

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_the_guard_names_the_route_of_the_stage_that_broke(monkeypatch):
    class UnportableVerifier(VerificationReport):
        verdict: str = Field(json_schema_extra={"pattern": r"^(?!x)pass$"})

    monkeypatch.setattr(ModelSemanticVerifier, "schema", UnportableVerifier)
    reported = {}
    for route, schema in (await stage_schemas()).items():
        try:
            wire_schema_for(OutputStrategy.STRICT_SCHEMA,
                            schema.model_json_schema())
        except SchemaNotPortable as exc:
            reported[route] = exc.path
    assert reported == {"semantic_verifier": "$.properties.verdict"}

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_an_untranslatable_pattern_raises_instead_of_degrading():
    class LookaheadDraft(DraftReport):
        note: str = Field(json_schema_extra={"pattern": r"^(?!x)y$"})

    with pytest.raises(SchemaNotPortable) as caught:
        wire_schema_for(OutputStrategy.STRICT_SCHEMA,
                        LookaheadDraft.model_json_schema())
    assert caught.value.construct == "pattern"
    assert caught.value.path == "$.properties.note"
    assert str(caught.value) == (
        "pattern at $.properties.note has no portable form: "
        r"look-around cannot be compiled: '^(?!x)y$'")
    strict_rung = wire_schema_for(
        OutputStrategy.STRICT_SCHEMA,
        strict_output_json_schema(LookaheadDraft)).schema
    assert strict_rung["properties"]["note"] == {"type": "string"}

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_a_derived_decimal_still_travels_as_text(monkeypatch):
    class DecimalDraft(DraftReport):
        share: Decimal = Decimal("0.5")

    monkeypatch.setattr(ModelSynthesizer, "schema", DecimalDraft)
    sanitized = wire_schema_for(OutputStrategy.STRICT_SCHEMA,
                                DecimalDraft.model_json_schema())
    share = sanitized.schema["properties"]["share"]
    assert strict_subset_violations(sanitized.schema) == ()
    assert share["anyOf"][0] == {"type": "number"}
    assert share["anyOf"][1]["type"] == "string"
    assert share["anyOf"][1]["pattern"] == (
        r"^[+-]?(?:0*\d+(?:\.\d*)?|0*\.\d+)$")
    assert DecimalDraft.model_validate({**_representative_payload(
        DecimalDraft), "share": "0.5"}).share == Decimal("0.5")