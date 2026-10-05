from __future__ import annotations

import inspect
import json
import re

import httpx
import pytest
from jsonschema import Draft202012Validator
from openai.types.chat import ChatCompletion
from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent, NativeOutput, PromptedOutput, ToolOutput
from pydantic_ai.capabilities import Hooks
from pydantic_ai.models import OutputObjectDefinition
from pydantic_ai.providers.openai import OpenAIProvider
from v2.adapters.models import (
    DimeOpenAIChatModel,
    ProviderStructuredModel,
    ReasoningContentFallbackClient,
    _promote_reasoning_content,
)
from v2.adapters.structured import (
    CAPABILITY_TABLE_PATH,
    STRICT_SAFE_PATTERNS,
    CapabilityTableError,
    EndpointCapabilities,
    FailureKind,
    OutputStrategy,
    STRATEGY_LADDER,
    SchemaNotPortable,
    capabilities_for,
    classify_failure,
    load_capability_table,
    normalize_endpoint,
    output_type_for,
    repaired_output_payload,
    repair_json_text,
    resolve_strategy,
    sanitize_schema,
    should_retry,
    wire_schema_for,
)
from v2.arguments import PlannerOutputWire, RequirementReviewWire
from v2.contracts import DraftReport, TaskSpec, VerificationReport
from v2.runtime import RequestEnvelope


class Ping(BaseModel):
    answer: str


STAGE_SCHEMAS = (
    ("intake", TaskSpec),
    ("plan", PlannerOutputWire),
    ("requirement_review", RequirementReviewWire),
    ("synthesizer", DraftReport),
    ("verifier", VerificationReport),
)

STANDARD_KEYWORDS = frozenset({
    "$anchor", "$comment", "$defs", "$dynamicAnchor", "$dynamicRef", "$id",
    "$ref", "$schema", "$vocabulary", "additionalProperties", "allOf", "anyOf",
    "const", "contains", "contentEncoding", "contentMediaType",
    "contentSchema", "default", "dependentRequired", "dependentSchemas",
    "deprecated", "description", "discriminator", "else", "enum",
    "examples", "exclusiveMaximum", "exclusiveMinimum", "format", "if",
    "items", "maxContains", "maxItems", "maxLength", "maxProperties",
    "maximum", "minContains", "minItems", "minLength", "minProperties",
    "minimum", "multipleOf", "not", "oneOf", "pattern", "patternProperties",
    "prefixItems", "properties", "propertyNames", "readOnly", "required",
    "then", "title", "type", "unevaluatedItems", "unevaluatedProperties",
    "uniqueItems", "writeOnly",
})
UNCOMPILABLE_KEYWORDS = frozenset({"const", "discriminator"})
LOOKAROUND = re.compile(r"\(\?(?:=|!|<=|<!)")
LADDER = (
    (OutputStrategy.STRICT_SCHEMA, True, True, True),
    (OutputStrategy.TOOL_CALL, False, True, False),
    (OutputStrategy.PROMPTED_JSON, False, False, False),
)


def _capabilities(strict=True, tools=True, strict_tools=True):
    return EndpointCapabilities(
        endpoint="https://probe.invalid/v1",
        strict_json_schema=strict, tool_calling=tools,
        strict_tool_definitions=strict_tools)


def _completion(content=None, tool_arguments=None, finish_reason="stop"):
    message: dict = {"role": "assistant", "content": content}
    if tool_arguments is not None:
        message["tool_calls"] = [{
            "id": "call-1", "type": "function",
            "function": {"name": "final_result", "arguments": tool_arguments}}]
    return {"id": "completion-1", "created": 1, "model": "probe-model",
            "object": "chat.completion",
            "choices": [{"index": 0, "finish_reason": finish_reason,
                         "message": message}]}


class Wire:
    def __init__(self, bodies):
        self._bodies = list(bodies)
        self.sent: list[dict] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.sent.append(json.loads(request.content))
            body = self._bodies[min(len(self.sent) - 1, len(self._bodies) - 1)]
            return httpx.Response(200, json=body)
        return httpx.MockTransport(handler)

    @property
    def body(self) -> dict:
        assert self.sent, "no request reached the transport"
        return self.sent[0]


def _model(capabilities, wire: Wire) -> DimeOpenAIChatModel:
    client = ReasoningContentFallbackClient(
        api_key="placeholder",
        http_client=httpx.AsyncClient(transport=wire.transport()))
    return DimeOpenAIChatModel(
        "probe-model", provider=OpenAIProvider(openai_client=client),
        capabilities=capabilities)


async def _run(capabilities, schema, wire: Wire, retries: int = 2):
    model = _model(capabilities, wire)
    agent = Agent(
        model, instructions="stage instructions",
        output_type=output_type_for(model.strategy, schema, capabilities),
        retries=retries,
        capabilities=[Hooks(before_output_validate=repaired_output_payload)])
    return await agent.run("{}")


def _envelope(route: str = "intake") -> RequestEnvelope:
    return RequestEnvelope.freeze(
        provider="probe", model="probe-model", route=route, prompt="p",
        context={}, tool_schemas={}, planner_version="v2")


def _strict_grammar_accepts(schema) -> None:
    Draft202012Validator.check_schema(schema)
    _assert_strict_subset(schema)


def _assert_strict_subset(schema, path="$") -> None:
    if isinstance(schema, list):
        for index, item in enumerate(schema):
            _assert_strict_subset(item, f"{path}[{index}]")
        return
    if not isinstance(schema, dict):
        return
    for keyword, value in schema.items():
        assert keyword in STANDARD_KEYWORDS, f"{path}.{keyword}"
        assert keyword not in UNCOMPILABLE_KEYWORDS, f"{path}.{keyword}"
        if keyword == "pattern":
            assert LOOKAROUND.search(value) is None, f"{path}.{keyword}={value!r}"
        if keyword in {"enum", "default", "const", "properties",
                       "$defs"}:
            continue
        _assert_strict_subset(value, f"{path}.{keyword}")
    for name, definition in schema.get("$defs", {}).items():
        _assert_strict_subset(definition, f"{path}.$defs.{name}")
    for name, definition in schema.get("properties", {}).items():
        _assert_strict_subset(definition, f"{path}.properties.{name}")


def test_ladder_picks_the_highest_strategy_an_endpoint_supports():
    assert resolve_strategy(_capabilities()) is OutputStrategy.STRICT_SCHEMA


def test_ladder_falls_to_tool_calling_when_strict_schemas_are_refused():
    assert resolve_strategy(_capabilities(strict=False)) is OutputStrategy.TOOL_CALL


def test_ladder_falls_to_the_prompt_and_repair_floor_when_neither_is_offered():
    capabilities = _capabilities(strict=False, tools=False)
    assert resolve_strategy(capabilities) is OutputStrategy.PROMPTED_JSON


def test_the_ladder_is_ordered_by_descending_preference():
    assert STRATEGY_LADDER == (
        OutputStrategy.STRICT_SCHEMA, OutputStrategy.TOOL_CALL,
        OutputStrategy.PROMPTED_JSON)


def test_each_strategy_selects_its_own_output_mechanism():
    assert output_type_for(OutputStrategy.STRICT_SCHEMA, Ping,
                           _capabilities()).__class__ is NativeOutput
    assert output_type_for(OutputStrategy.TOOL_CALL, Ping,
                           _capabilities(strict=False)).__class__ is ToolOutput
    assert output_type_for(OutputStrategy.PROMPTED_JSON, Ping,
                           _capabilities(strict=False, tools=False)).__class__ is (
                               PromptedOutput)


def test_the_capability_table_is_data_and_rejects_a_malformed_row(tmp_path):
    table = load_capability_table()
    assert table, "the shipped table must declare at least one endpoint"
    assert CAPABILITY_TABLE_PATH.exists()
    for entry in table.values():
        assert entry.endpoint == normalize_endpoint(entry.endpoint)
    assert capabilities_for(
        "https://api.groq.com/openai/v1").strict_json_schema is False
    unknown = capabilities_for("https://never-probed.invalid/v1")
    assert unknown.supports(OutputStrategy.PROMPTED_JSON) is True
    assert unknown.supports(OutputStrategy.STRICT_SCHEMA) is False
    assert unknown.supports(OutputStrategy.TOOL_CALL) is False

    path = tmp_path / "table.json"
    path.write_text(json.dumps({"endpoints": [
        {"base_url": "https://a.invalid/v1", "strict_json_schema": True}]}))
    with pytest.raises(CapabilityTableError):
        load_capability_table(path)
    path.write_text(json.dumps({"endpoints": [
        {"base_url": "https://a.invalid/v1", "strict_json_schema": "yes",
         "tool_calling": True, "strict_tool_definitions": True}]}))
    with pytest.raises(CapabilityTableError):
        load_capability_table(path)
    path.write_text(json.dumps({"endpoints": [
        {"base_url": "http://a.invalid/v1", "strict_json_schema": True,
         "tool_calling": True, "strict_tool_definitions": True}]}))
    with pytest.raises(CapabilityTableError):
        load_capability_table(path)
    path.write_text(json.dumps({"endpoints": [
        {"base_url": "https://a.invalid/v1", "strict_json_schema": True,
         "tool_calling": True, "strict_tool_definitions": True},
        {"base_url": "https://a.invalid/v1/", "strict_json_schema": False,
         "tool_calling": False, "strict_tool_definitions": False}]}))
    with pytest.raises(CapabilityTableError):
        load_capability_table(path)


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_the_strict_tier_sends_response_format_and_no_tools():
    wire = Wire([_completion(content='{"answer": "a"}')])
    await _run(_capabilities(), Ping, wire)
    body = wire.body
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert "tools" not in body


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_the_tool_tier_sends_tools_and_never_a_response_format():
    wire = Wire([_completion(tool_arguments='{"answer": "a"}',
                             finish_reason="tool_calls")])
    await _run(_capabilities(strict=False), Ping, wire)
    body = wire.body
    assert "response_format" not in body
    assert [tool["function"]["name"] for tool in body["tools"]] == ["final_result"]
    assert body["tool_choice"] in ("required", "auto")


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_strict_tool_definitions_reach_the_tool_wire_as_data():
    relaxed = Wire([_completion(tool_arguments='{"answer": "a"}',
                                finish_reason="tool_calls")])
    await _run(_capabilities(strict=False, strict_tools=False), Ping, relaxed)
    assert "strict" not in relaxed.body["tools"][0]["function"]
    enforced = Wire([_completion(tool_arguments='{"answer": "a"}',
                                 finish_reason="tool_calls")])
    await _run(_capabilities(strict=False, strict_tools=True), Ping, enforced)
    assert enforced.body["tools"][0]["function"]["strict"] is True


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_the_prompt_floor_recovers_fenced_trailing_comma_json():
    wire = Wire([_completion(content='```json\n{"answer": "a",}\n```')])
    result = await _run(_capabilities(strict=False, tools=False), Ping, wire)
    assert result.output == Ping(answer="a")
    body = wire.body
    assert body.get("response_format", {}).get("type") != "json_schema"
    assert "tools" not in body
    system = "\n".join(str(message["content"]) for message in body["messages"])
    assert '"answer"' in system
    assert "JSON" in system


def test_every_stage_reaches_the_wire_through_the_same_strategy():
    for stage, schema in STAGE_SCHEMAS:
        for strategy, strict, tools, strict_tools in LADDER:
            capabilities = _capabilities(strict, tools, strict_tools)
            model = _model(capabilities, Wire([]))
            assert model.strategy is strategy, stage
            assert resolve_strategy(capabilities) is strategy, stage
            object_definition = OutputObjectDefinition(
                json_schema=schema.model_json_schema(), name=stage,
                strict=True)
            sent = model._map_json_schema(object_definition)
            assert sent["json_schema"]["schema"] == wire_schema_for(
                strategy, schema.model_json_schema()).schema, stage


def test_no_stage_or_provider_name_decides_the_wire_shape():
    source = inspect.getsource(DimeOpenAIChatModel).casefold()
    for forbidden in ("taskspec", "drafterport", "verificationreport",
                      "planneroutputwire", "requirementreviewwire", "gemma",
                      "gemini", "groq", "openrouter", "mistral", "nvidia",
                      "inception"):
        assert forbidden not in source


def test_a_rate_limit_is_transient_and_is_retried():
    kind = classify_failure(status_code=429, detail="429 Too Many Requests")
    assert kind is FailureKind.TRANSIENT
    assert should_retry(kind) is True


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_a_server_error_is_transient_and_is_retried(code):
    assert should_retry(
        classify_failure(status_code=code, detail="upstream")) is True


def test_a_timeout_and_a_connection_reset_are_transient():
    assert should_retry(classify_failure(
        status_code=None, detail="TimeoutError timed out")) is True
    assert should_retry(classify_failure(
        status_code=None, detail="Connection reset by peer")) is True


def test_a_grammar_refusal_inside_a_500_is_a_schema_rejection():
    detail = (
        "Upstream error from Nvidia: ValueError: Grammar error: regex parse "
        "error: ^(?!^[-+.]*$)[+-]?0*[0-9]*\\.?[0-9]*$ error: look-around, "
        "including look-ahead and look-behind, is not supported while "
        "processing json-schema:///#/$defs/DeclaredCalculation")
    kind = classify_failure(status_code=500, detail=detail)
    assert kind is FailureKind.SCHEMA_REJECTED
    assert should_retry(kind) is False


def test_a_schema_refusal_wrapped_in_a_200_is_a_schema_rejection():
    detail = ("Upstream error: json_schema is not supported, response_format "
              "was rejected")
    assert should_retry(classify_failure(status_code=200,
                                         detail=detail)) is False


def test_a_400_schema_complaint_is_a_schema_rejection():
    assert should_retry(classify_failure(
        status_code=400, detail="invalid schema for response_format")) is False


def test_a_validation_failure_is_a_schema_rejection_and_is_not_retried():
    kind = classify_failure(
        status_code=None, detail="1 validation error for TaskSpec",
        exception_names=frozenset({"ValidationError"}))
    assert kind is FailureKind.SCHEMA_REJECTED
    assert should_retry(kind) is False


def test_authentication_and_a_daily_quota_wall_fail_without_retry():
    assert should_retry(classify_failure(
        status_code=401, detail="invalid api key")) is False
    assert should_retry(classify_failure(
        status_code=None,
        detail="429 RESOURCE_EXHAUSTED (PerDay, 500/day) quota reset")) is False


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_generate_retries_a_429_then_succeeds(monkeypatch):
    calls: list[int] = []

    class RateLimited:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self, prompt):
            calls.append(1)
            if len(calls) == 1:
                error = RuntimeError("429 Too Many Requests")
                error.status_code = 429
                raise error
            return type("R", (), {"output": Ping(answer="a")})()

    async def no_sleep(value):
        return None

    monkeypatch.setattr("v2.adapters.models.Agent", RateLimited)
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", no_sleep)
    monkeypatch.setattr("v2.adapters.models.random.uniform", lambda a, b: 0)
    model = ProviderStructuredModel("inception", "probe-model")
    monkeypatch.setattr(
        model, "_models",
        lambda: [("inception", _model(_capabilities(), Wire([])))])
    result = await model.generate(schema=Ping, prompt="p", payload={},
                                  envelope=_envelope())
    assert result.answer == "a"
    assert len(calls) == 2
    assert [failure["message_class"]
            for failure in model.last_failures] == ["rate_limit"]


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_generate_reports_a_schema_rejection_and_never_retries_it(
        monkeypatch):
    calls: list[int] = []

    class SchemaRefused:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self, prompt):
            calls.append(1)
            raise TaskSpec.model_validate({"goal": ""})

    monkeypatch.setattr("v2.adapters.models.Agent", SchemaRefused)
    model = ProviderStructuredModel("inception", "probe-model")
    monkeypatch.setattr(
        model, "_models",
        lambda: [("inception", _model(_capabilities(), Wire([])))])
    with pytest.raises(RuntimeError,
                       match="all structured-output providers failed"):
        await model.generate(schema=TaskSpec, prompt="p", payload={},
                             envelope=_envelope())
    assert calls == [1]
    assert [failure["message_class"]
            for failure in model.last_failures] == ["schema_rejected"]


def test_repair_recovers_markdown_fenced_json():
    assert repair_json_text('```json\n{"answer": "a"}\n```') == '{"answer": "a"}'


def test_repair_recovers_prose_wrapped_fenced_json():
    assert repair_json_text(
        'Here you go:\n```\n{"answer": "a"}\n```\nHope that helps.') == (
            '{"answer": "a"}')


def test_repair_removes_trailing_commas_at_every_depth():
    assert json.loads(repair_json_text(
        '{"a": [1, 2, ], "b": {"c": 3, },}')) == {"a": [1, 2],
                                                   "b": {"c": 3}}


def test_repair_never_invents_a_value_for_truncated_output():
    truncated = '{"nodes": [{"id": "a"}, {"id": "b"}'
    assert repair_json_text(truncated) == truncated
    with pytest.raises(ValueError):
        json.loads(repair_json_text(truncated))


def test_repair_leaves_clean_json_untouched():
    payload = '{"answer": "a", "n": 1}'
    assert repair_json_text(payload) == payload


def test_the_repair_hook_passes_a_decoded_payload_through():
    payload = {"answer": "a"}
    assert repaired_output_payload(None, output=payload) is payload


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_the_floor_re_asks_the_model_when_repair_cannot_validate():
    wire = Wire([_completion(content='{"answer": 7}'),
                 _completion(content='{"answer": "a"}')])
    result = await _run(_capabilities(strict=False, tools=False), Ping, wire)
    assert result.output == Ping(answer="a")
    assert len(wire.sent) == 2
    assert "answer" in wire.sent[1]["messages"][-1]["content"]


def test_declared_calculation_result_is_decimal_text_not_a_decimal():
    from v2.contracts import DeclaredCalculation

    schema = DeclaredCalculation.model_json_schema()
    assert schema["properties"]["result"]["type"] == "string"
    assert LOOKAROUND.search(
        schema["properties"]["result"]["pattern"]) is None
    calculation = DeclaredCalculation.model_validate({
        "calculation_id": "c", "operation": "add",
        "inputs": [{"evidence_id": "e", "path": "rows.a"}],
        "result": "150.2500"})
    assert calculation.result == "150.2500"
    with pytest.raises(ValidationError):
        DeclaredCalculation.model_validate({
            "calculation_id": "c", "operation": "add",
            "inputs": [{"evidence_id": "e", "path": "rows.a"}],
            "result": "NaN"})


def test_a_decimal_derived_pattern_is_rewritten_to_an_equivalent_strict_pattern():
    source, replacement = next(iter(STRICT_SAFE_PATTERNS.items()))
    sanitized = sanitize_schema({"type": "string", "pattern": source})
    assert sanitized.schema["pattern"] == replacement
    assert sanitized.rewrites == ("$.pattern-rewritten",)
    candidates = ("1", "-1", "0.5", ".5", "5.", "+7", "00.5", "1e3", "0",
                  "NaN", "Infinity", "", "-", ".", "+", "--1", "1.2.3", "1 2")
    for candidate in candidates:
        assert (re.fullmatch(source, candidate) is not None) == (
            re.fullmatch(replacement, candidate) is not None), candidate


def test_an_untranslatable_look_around_pattern_fails_loudly():
    with pytest.raises(SchemaNotPortable) as caught:
        sanitize_schema({"type": "string", "pattern": r"^(?!x)y$"})
    assert caught.value.construct == "pattern"
    assert caught.value.path == "$"


def test_sanitization_records_every_rewrite_and_drops_no_data():
    source = {
        "type": "object",
        "properties": {
            "kind": {"const": "bool", "type": "string"},
            "items": {"type": "array", "minItems": 1, "maxItems": 8,
                      "items": {"type": "string"}},
            "value": {"anyOf": [{"type": "string"}, {"type": "null"}],
                      "default": None},
            "nested": {"discriminator": {"propertyName": "kind"},
                       "oneOf": [{"type": "object"}]},
        },
        "required": ["kind", "items"],
    }
    sanitized = sanitize_schema(source)
    assert sanitized.schema["properties"]["kind"] == {"enum": ["bool"],
                                                      "type": "string"}
    assert sanitized.schema["properties"]["items"] == {
        "type": "array", "items": {"type": "string"}}
    assert sanitized.schema["properties"]["value"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
    assert "discriminator" not in sanitized.schema["properties"]["nested"]
    assert sanitized.schema["properties"]["nested"]["oneOf"] == [{"type": "object"}]
    assert sorted(sanitized.rewrites) == sorted([
        "$.properties.items.maxItems-dropped",
        "$.properties.items.minItems-dropped",
        "$.properties.kind.const-to-enum",
        "$.properties.nested.discriminator-dropped",
    ])
    assert source["properties"]["items"]["maxItems"] == 8


def test_every_stage_wire_schema_satisfies_a_strict_grammar():
    for strategy in (OutputStrategy.STRICT_SCHEMA, OutputStrategy.TOOL_CALL):
        for stage, schema in STAGE_SCHEMAS:
            sanitized = wire_schema_for(strategy, schema.model_json_schema())
            assert sanitized.schema, (stage, strategy)
            _strict_grammar_accepts(sanitized.schema)
            assert LOOKAROUND.search(json.dumps(sanitized.schema)) is None


def test_the_prompt_floor_sends_no_schema_on_the_wire():
    assert wire_schema_for(
        OutputStrategy.PROMPTED_JSON,
        TaskSpec.model_json_schema()).schema == {}


def test_a_free_form_object_records_the_strict_compatibility_skip():
    intake = wire_schema_for(OutputStrategy.STRICT_SCHEMA,
                             TaskSpec.model_json_schema())
    assert any(rewrite.endswith("free-form-not-strict-compatible")
               for rewrite in intake.rewrites)
    verifier = wire_schema_for(OutputStrategy.STRICT_SCHEMA,
                               VerificationReport.model_json_schema())
    assert not any(rewrite.endswith("free-form-not-strict-compatible")
                   for rewrite in verifier.rewrites)


def test_sanitization_does_not_mutate_the_source_schema():
    source = DraftReport.model_json_schema()
    before = json.dumps(source, sort_keys=True)
    wire_schema_for(OutputStrategy.STRICT_SCHEMA, source)
    assert json.dumps(source, sort_keys=True) == before


def test_null_choices_do_not_raise_and_keep_the_upstream_body():
    response = ChatCompletion.model_construct(
        id="x", choices=None, created=1, model="m",
        object="chat.completion")
    promoted, promotions = _promote_reasoning_content(response)
    assert promotions == []
    assert promoted.choices is None
