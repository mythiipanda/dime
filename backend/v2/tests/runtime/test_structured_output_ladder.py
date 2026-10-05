from __future__ import annotations

import inspect
import json
import re
from collections.abc import Mapping
from typing import Any

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
    LOOKAROUND_PATTERN,
    STRICT_SAFE_PATTERNS,
    CapabilityMeasurement,
    CapabilityTableError,
    EndpointCapabilities,
    FailureKind,
    LadderAttempt,
    OutputStrategy,
    STRATEGY_LADDER,
    SchemaNotPortable,
    StrategyLadder,
    Support,
    capabilities_for,
    classify_failure,
    load_capability_table,
    normalize_endpoint,
    output_type_for,
    repaired_output_payload,
    repair_json_text,
    resolve_strategy,
    sanitize_schema,
    strict_subset_violations,
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

LADDER = (
    (OutputStrategy.STRICT_SCHEMA, True, True, True),
    (OutputStrategy.TOOL_CALL, False, True, False),
    (OutputStrategy.PROMPTED_JSON, False, False, False),
)
_SUPPORT_FLAGS = ("strict_json_schema", "tool_calling",
                  "strict_tool_definitions")
MEASUREMENT_JSON = {"probe": "test-probe", "measured_at": "2026-10-05",
                    "models": ["probe-model"]}
MEASUREMENT = CapabilityMeasurement(
    probe=MEASUREMENT_JSON["probe"], measured_at=MEASUREMENT_JSON["measured_at"],
    models=tuple(MEASUREMENT_JSON["models"]))


def _write_table(path, *, base_url="https://a.invalid/v1",
                 strict_json_schema="unmeasured", tool_calling="unmeasured",
                 strict_tool_definitions="unmeasured", measurement=None,
                 extra_key=False) -> None:
    entry = {"base_url": base_url, "strict_json_schema": strict_json_schema,
             "tool_calling": tool_calling,
             "strict_tool_definitions": strict_tool_definitions}
    if measurement is not None:
        entry["measurement"] = measurement
    if extra_key:
        entry["assumed"] = True
    path.write_text(json.dumps({"endpoints": [entry]}))


def _capabilities(strict=True, tools=True, strict_tools=True):
    return EndpointCapabilities(
        endpoint="https://probe.invalid/v1",
        strict_json_schema=Support.MEASURED if strict else Support.REFUSED,
        tool_calling=Support.MEASURED if tools else Support.REFUSED,
        strict_tool_definitions=(Support.MEASURED if strict_tools
                                 else Support.REFUSED),
        measurement=MEASUREMENT)


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


REFUSALS = {
    "refused": (400, "invalid schema for response_format"),
    "server_error": (500, "Internal Server Error"),
    "unauthorized": (401, "invalid api key"),
}


def rung_of(body: Mapping[str, Any]) -> OutputStrategy:
    if body.get("response_format", {}).get("type") == "json_schema":
        return OutputStrategy.STRICT_SCHEMA
    if body.get("tools"):
        return OutputStrategy.TOOL_CALL
    return OutputStrategy.PROMPTED_JSON


class LadderEndpoint:
    """Fake endpoint that answers, or refuses, per rung of the ladder."""

    def __init__(self, *, strict="ok", tools="ok", floor="ok"):
        self.behavior = {OutputStrategy.STRICT_SCHEMA: strict,
                         OutputStrategy.TOOL_CALL: tools,
                         OutputStrategy.PROMPTED_JSON: floor}
        self.sent: list[dict] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            self.sent.append(body)
            rung = rung_of(body)
            behavior = self.behavior[rung]
            if behavior == "ok":
                return httpx.Response(
                    200, json=(_completion(tool_arguments='{"answer": "a"}',
                                           finish_reason="tool_calls")
                              if rung is OutputStrategy.TOOL_CALL
                              else _completion(content='{"answer": "a"}')))
            status, message = REFUSALS[behavior]
            return httpx.Response(status, json={"error": {
                "message": message, "type": "invalid_request_error"}})
        return httpx.MockTransport(handler)

    @property
    def rungs(self) -> list[OutputStrategy]:
        return [rung_of(body) for body in self.sent]


def _stage_model(endpoint: LadderEndpoint,
                 capabilities) -> ProviderStructuredModel:
    client = httpx.AsyncClient(transport=endpoint.transport())
    chat_model = DimeOpenAIChatModel(
        "probe-model",
        provider=OpenAIProvider(openai_client=ReasoningContentFallbackClient(
            api_key="placeholder", max_retries=0, http_client=client)),
        capabilities=capabilities)
    model = ProviderStructuredModel("inception", "probe-model")
    model._models = lambda: [("inception", chat_model)]
    return model


async def _no_backoff(monkeypatch) -> None:
    async def no_sleep(value: float) -> None:
        return None

    monkeypatch.setattr("v2.adapters.models.anyio.sleep", no_sleep)
    monkeypatch.setattr("v2.adapters.models.random.uniform", lambda a, b: 0)


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
    assert strict_subset_violations(schema) == ()


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
        "https://api.groq.com/openai/v1").supports(
            OutputStrategy.STRICT_SCHEMA) is False
    unknown = capabilities_for("https://never-probed.invalid/v1")
    assert unknown.supports(OutputStrategy.PROMPTED_JSON) is True
    assert unknown.supports(OutputStrategy.STRICT_SCHEMA) is False
    assert unknown.supports(OutputStrategy.TOOL_CALL) is False

    path = tmp_path / "table.json"
    _write_table(path, strict_json_schema=True, tool_calling=True,
                 strict_tool_definitions=True)
    with pytest.raises(CapabilityTableError, match="measured or refused"):
        load_capability_table(path)
    _write_table(path, strict_json_schema="assumed", tool_calling=True,
                 strict_tool_definitions=True)
    with pytest.raises(CapabilityTableError, match="measured or refused"):
        load_capability_table(path)
    _write_table(path, strict_json_schema="measured")
    with pytest.raises(CapabilityTableError, match="without a measurement"):
        load_capability_table(path)
    _write_table(path, strict_json_schema="measured", measurement=MEASUREMENT_JSON)
    assert load_capability_table(path)["https://a.invalid/v1"] == (
        EndpointCapabilities(
            endpoint="https://a.invalid/v1", strict_json_schema="measured",
            tool_calling="unmeasured", strict_tool_definitions="unmeasured",
            measurement=MEASUREMENT))
    _write_table(path, strict_json_schema="refused", tool_calling="refused",
                 strict_tool_definitions="refused")
    with pytest.raises(CapabilityTableError):
        load_capability_table(path)
    _write_table(path, strict_json_schema="measured", measurement=MEASUREMENT_JSON,
                 extra_key=True)
    with pytest.raises(CapabilityTableError):
        load_capability_table(path)
    _write_table(path, strict_json_schema="measured", measurement=MEASUREMENT_JSON,
                 base_url="http://a.invalid/v1")
    with pytest.raises(CapabilityTableError):
        load_capability_table(path)
    unmeasured = {"base_url": "https://a.invalid/v1",
                  **{flag: "unmeasured" for flag in _SUPPORT_FLAGS}}
    path.write_text(json.dumps({"endpoints": [
        unmeasured, {**unmeasured, "base_url": "https://a.invalid/v1/"}]}))
    with pytest.raises(CapabilityTableError, match="duplicate"):
        load_capability_table(path)


def test_the_shipped_table_records_where_each_outcome_came_from():
    table = load_capability_table()
    measured = {endpoint: entry for endpoint, entry in table.items()
                if entry.measurement is not None}
    assert measured, "no endpoint row carries a measurement"
    for endpoint, entry in measured.items():
        assert entry.measurement.probe and entry.measurement.measured_at
        assert entry.measurement.models
        assert any(getattr(entry, flag) is not Support.UNMEASURED
                   for flag in _SUPPORT_FLAGS), endpoint
    for endpoint, entry in table.items():
        if entry.measurement is None:
            assert all(getattr(entry, flag) is Support.UNMEASURED
                       for flag in _SUPPORT_FLAGS), endpoint


def test_only_a_measured_observation_reads_as_support():
    assert Support.MEASURED.supported is True
    assert Support.REFUSED.supported is False
    assert Support.UNMEASURED.supported is False
    for flag in ("strict_json_schema", "tool_calling"):
        strategy = OutputStrategy.STRICT_SCHEMA if flag == "strict_json_schema" \
            else OutputStrategy.TOOL_CALL
        unmeasured = EndpointCapabilities(endpoint="https://a.invalid/v1")
        refused = EndpointCapabilities(endpoint="https://a.invalid/v1",
                                       **{flag: Support.REFUSED})
        for capabilities in (unmeasured, refused):
            assert capabilities.supports(strategy) is False
        assert EndpointCapabilities(
            endpoint="https://a.invalid/v1", **{flag: Support.MEASURED}
        ).supports(strategy) is True


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


def descends(kind: FailureKind) -> bool:
    return StrategyLadder(_capabilities()).descend(kind) is not None


def test_a_rate_limit_is_transient_and_descends():
    kind = classify_failure(status_code=429, detail="429 Too Many Requests")
    assert kind is FailureKind.TRANSIENT
    assert descends(kind) is True


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_a_server_error_is_transient_and_descends(code):
    assert descends(classify_failure(
        status_code=code, detail="upstream")) is True


def test_a_timeout_and_a_connection_reset_are_transient():
    assert descends(classify_failure(
        status_code=None, detail="TimeoutError timed out")) is True
    assert descends(classify_failure(
        status_code=None, detail="Connection reset by peer")) is True


def test_a_grammar_refusal_inside_a_500_is_a_schema_rejection():
    detail = (
        "Upstream error from Nvidia: ValueError: Grammar error: regex parse "
        "error: ^(?!^[-+.]*$)[+-]?0*[0-9]*\\.?[0-9]*$ error: look-around, "
        "including look-ahead and look-behind, is not supported while "
        "processing json-schema:///#/$defs/DeclaredCalculation")
    assert classify_failure(status_code=500, detail=detail) is (
        FailureKind.SCHEMA_REJECTED)
    assert descends(FailureKind.SCHEMA_REJECTED) is True


def test_a_schema_refusal_wrapped_in_a_200_is_a_schema_rejection():
    detail = ("Upstream error: json_schema is not supported, response_format "
              "was rejected")
    kind = classify_failure(status_code=200, detail=detail)
    assert kind is FailureKind.SCHEMA_REJECTED
    assert descends(kind) is True


def test_a_400_schema_complaint_is_a_schema_rejection():
    assert classify_failure(
        status_code=400, detail="invalid schema for response_format") is (
            FailureKind.SCHEMA_REJECTED)


def test_a_validation_failure_is_a_schema_rejection():
    assert classify_failure(
        status_code=None, detail="1 validation error for TaskSpec",
        exception_names=frozenset({"ValidationError"})) is (
            FailureKind.SCHEMA_REJECTED)


def test_authentication_and_a_daily_quota_wall_do_not_descend():
    assert descends(classify_failure(
        status_code=401, detail="invalid api key")) is False
    assert descends(classify_failure(
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
async def test_generate_classifies_a_validation_failure_and_walks_the_ladder(
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
    assert calls == [1, 1, 1]
    assert [failure["message_class"]
            for failure in model.last_failures] == ["schema_rejected"] * 3


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_a_stage_refused_on_the_strict_rung_succeeds_on_the_tool_rung(
        monkeypatch):
    await _no_backoff(monkeypatch)
    endpoint = LadderEndpoint(strict="refused")
    model = _stage_model(endpoint, _capabilities())
    result = await model.generate(schema=Ping, prompt="p", payload={},
                                  envelope=_envelope())
    assert result.answer == "a"
    assert endpoint.rungs == [OutputStrategy.STRICT_SCHEMA,
                              OutputStrategy.TOOL_CALL]
    assert model.last_output_strategy is OutputStrategy.TOOL_CALL
    assert [(failure["attempt_number"], failure["output_strategy"])
            for failure in model.last_failures] == [(1, "strict_schema")]


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_a_stage_refused_on_the_tool_rung_succeeds_on_the_prompt_floor(
        monkeypatch):
    await _no_backoff(monkeypatch)
    endpoint = LadderEndpoint(strict="refused", tools="refused")
    model = _stage_model(endpoint, _capabilities())
    result = await model.generate(schema=Ping, prompt="p", payload={},
                                  envelope=_envelope())
    assert result.answer == "a"
    assert endpoint.rungs == list(STRATEGY_LADDER)
    assert model.last_output_strategy is OutputStrategy.PROMPTED_JSON
    assert [failure["output_strategy"] for failure in model.last_failures] == [
        "strict_schema", "tool_call"]


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_a_transport_failure_on_the_strict_rung_descends(monkeypatch):
    await _no_backoff(monkeypatch)
    endpoint = LadderEndpoint(strict="server_error")
    model = _stage_model(endpoint, _capabilities())
    result = await model.generate(schema=Ping, prompt="p", payload={},
                                  envelope=_envelope())
    assert result.answer == "a"
    assert endpoint.rungs == [OutputStrategy.STRICT_SCHEMA,
                              OutputStrategy.TOOL_CALL]
    assert [(failure["output_strategy"], failure["message_class"])
            for failure in model.last_failures] == [
                ("strict_schema", "server_error")]


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_the_prompt_floor_is_terminal_and_its_failure_is_a_failure(
        monkeypatch):
    await _no_backoff(monkeypatch)
    endpoint = LadderEndpoint(strict="refused", tools="refused", floor="refused")
    model = _stage_model(endpoint, _capabilities())
    with pytest.raises(RuntimeError,
                       match="all structured-output providers failed"):
        await model.generate(schema=Ping, prompt="p", payload={},
                             envelope=_envelope())
    assert endpoint.rungs == list(STRATEGY_LADDER)
    assert [failure["output_strategy"] for failure in model.last_failures] == [
        "strict_schema", "tool_call", "prompted_json"]


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_a_permanent_failure_does_not_descend_or_retry(monkeypatch):
    await _no_backoff(monkeypatch)
    endpoint = LadderEndpoint(strict="unauthorized")
    model = _stage_model(endpoint, _capabilities())
    with pytest.raises(RuntimeError,
                       match="all structured-output providers failed"):
        await model.generate(schema=Ping, prompt="p", payload={},
                             envelope=_envelope())
    assert endpoint.rungs == [OutputStrategy.STRICT_SCHEMA]
    assert [failure["message_class"]
            for failure in model.last_failures] == ["authentication"]


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_a_stage_that_descends_does_not_move_the_next_stage_down(
        monkeypatch):
    await _no_backoff(monkeypatch)
    endpoint = LadderEndpoint(strict="refused")
    model = _stage_model(endpoint, _capabilities())
    first = await model.generate(schema=Ping, prompt="p", payload={},
                                 envelope=_envelope())
    second = await model.generate(schema=Ping, prompt="p", payload={},
                                  envelope=_envelope("requirement_review"))
    assert (first.answer, second.answer) == ("a", "a")
    assert endpoint.rungs == [
        OutputStrategy.STRICT_SCHEMA, OutputStrategy.TOOL_CALL,
        OutputStrategy.STRICT_SCHEMA, OutputStrategy.TOOL_CALL]
    assert [(failure["route"], failure["output_strategy"])
            for failure in model.last_failures] == [
                ("requirement_review", "strict_schema")]


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_the_ledger_records_the_accepted_rung_and_every_failed_rung(
        monkeypatch):
    from v2.adapters.models import RecordedStructuredModel
    from v2.runtime import RunLedger

    await _no_backoff(monkeypatch)
    endpoint = LadderEndpoint(strict="server_error", tools="refused")
    model = _stage_model(endpoint, _capabilities())
    ledger = RunLedger("run")
    recorded = RecordedStructuredModel(model, ledger, turn_id="turn")
    result = await recorded.generate(schema=Ping, prompt="p", payload={},
                                     envelope=_envelope())
    assert result.answer == "a"
    attempt = ledger.entries[-1].data
    assert attempt["status"] == "accepted"
    assert attempt["output_strategy"] == "prompted_json"
    assert [(item["output_strategy"], item["attempt_number"])
            for item in attempt["provider_attempts"]] == [
                ("strict_schema", 1), ("tool_call", 2)]


def test_the_ladder_is_ordered_so_the_floor_is_the_terminal_strategy():
    assert STRATEGY_LADDER[-1] is OutputStrategy.PROMPTED_JSON
    ladder = StrategyLadder(_capabilities())
    assert [ladder.rung] * 1 == [OutputStrategy.STRICT_SCHEMA]
    assert ladder.descend(FailureKind.SCHEMA_REJECTED) is OutputStrategy.STRICT_SCHEMA
    assert ladder.descend(FailureKind.TRANSIENT) is OutputStrategy.TOOL_CALL
    assert ladder.at_floor is True
    assert ladder.descend(FailureKind.TRANSIENT) is None
    assert ladder.descend(FailureKind.SCHEMA_REJECTED) is None
    assert ladder.rung is OutputStrategy.PROMPTED_JSON


def test_a_permanent_failure_never_descends_the_ladder():
    ladder = StrategyLadder(_capabilities())
    assert ladder.descend(FailureKind.PERMANENT) is None
    assert ladder.rung is OutputStrategy.STRICT_SCHEMA


def test_a_ladder_that_starts_on_the_floor_cannot_move():
    ladder = StrategyLadder(_capabilities(strict=False, tools=False))
    assert ladder.rung is OutputStrategy.PROMPTED_JSON
    assert ladder.descend(FailureKind.TRANSIENT) is None


def test_a_ladder_records_every_attempt_it_served():
    ladder = StrategyLadder(_capabilities())
    ladder.record(attempt_number=1, failure_kind=FailureKind.TRANSIENT)
    ladder.descend(FailureKind.TRANSIENT)
    ladder.record(attempt_number=2, failure_kind=None)
    assert ladder.attempts == (
        LadderAttempt(OutputStrategy.STRICT_SCHEMA, 1, FailureKind.TRANSIENT),
        LadderAttempt(OutputStrategy.TOOL_CALL, 2, None))


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
    assert LOOKAROUND_PATTERN.search(
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
            assert LOOKAROUND_PATTERN.search(json.dumps(sanitized.schema)) is None


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
