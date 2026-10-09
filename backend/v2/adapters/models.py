from __future__ import annotations

import anyio
import httpx
import json
import hashlib
import random
import re
import time
import marshal
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any, Final, Protocol, TypeVar

from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, RateLimitError
from openai.resources.chat import AsyncChat
from openai.resources.chat.completions import AsyncCompletions
from openai.types.chat import ChatCompletion
from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_ai import Agent
from pydantic_ai.capabilities import Hooks
from pydantic_ai.exceptions import ContentFilterError, ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIJsonSchemaTransformer
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.tools import GenerateToolJsonSchema

from shared.config import settings
from shared.tools.rating_metrics import RANKING_DIRECTIONS, TEAM_RATING_METRICS
from shared.providers import (
    CEREBRAS_DEFAULT,
    GEMINI_BASE_URL,
    GROQ_DEFAULT,
    NVIDIA_NIM_BASE_URL,
    INCEPTION_DEFAULT,
    ProviderName,
    _cerebras_model,
    _gemini_model,
    _groq_free_model, _mistral_free_model,
    _nvidia_nim_model,
    _openrouter_free_model,
    is_free_model,
)
from v2.contracts import (
    ConversationTurn,
    Claim,
    DraftReport,
    EvidenceEnvelope,
    Plan,
    PlanNode,
    RequirementReview,
    TaskSpec,
    VerificationReport,
)
from v2.prompts import load_prompt
from v2.runtime.ledger import RequestEnvelope, exception_text
from v2.runtime.budget import RUN_MODEL_DEADLINE
from v2.skills import SkillLibrary, skill_hashes
from v2.arguments import RequirementReviewWire, PlannerOutputWire, provider_to_source
from v2.adapters.structured import (
    STRATEGY_LADDER,
    EndpointCapabilities,
    FailureKind,
    OutputStrategy,
    StrategyLadder,
    capabilities_for,
    classify_exception,
    output_type_for,
    repaired_output_payload,
    wire_schema_for,
)
from .capabilities import CAPABILITIES

T = TypeVar("T", bound=BaseModel)

def _imported_module_code_sha256() -> str:
    code = __loader__.get_code(__name__) if __loader__ is not None else None
    if code is None:
        raise RuntimeError("provider models module has no loader code identity")
    return hashlib.sha256(marshal.dumps(code)).hexdigest()

_LOADED_MODULE_CODE_SHA256 = _imported_module_code_sha256()

NIM_THINKING_OFF_EXTRA_BODY: dict[str, Any] = {
    "chat_template_kwargs": {"enable_thinking": False},
}

def strict_output_json_schema(schema: type[BaseModel], *,
                              strict: bool = True) -> dict[str, Any]:
    generated = TypeAdapter(schema).json_schema(
        schema_generator=GenerateToolJsonSchema)
    return OpenAIJsonSchemaTransformer(generated, strict=strict).walk()

def _with_thinking_off(kwargs: dict[str, Any]) -> dict[str, Any]:
    merged = dict(kwargs)
    extra_body = dict(merged.get("extra_body") or {})
    template = dict(extra_body.get("chat_template_kwargs") or {})
    template.update(NIM_THINKING_OFF_EXTRA_BODY["chat_template_kwargs"])
    extra_body["chat_template_kwargs"] = template
    merged["extra_body"] = extra_body
    return merged

def _promote_reasoning_content(
    response: ChatCompletion,
) -> tuple[ChatCompletion, list[dict[str, Any]]]:
    promotions: list[dict[str, Any]] = []
    for index, choice in enumerate(response.choices or ()):
        message = choice.message
        if (choice.finish_reason == "stop" and not message.content
                and getattr(message, "reasoning_content", None)):
            message.content = message.reasoning_content
            promotions.append({
                "choice_index": index,
                "finish_reason": choice.finish_reason,
                "reasoning_content_chars": len(message.reasoning_content),
            })
    return response, promotions

class _ReasoningContentCompletions(AsyncCompletions):

    async def create(self, *args: Any, **kwargs: Any) -> Any:
        if getattr(self._client, "thinking_off", False):
            kwargs = _with_thinking_off(kwargs)
        response = await super().create(*args, **kwargs)
        if isinstance(response, ChatCompletion):
            promoted, promotions = _promote_reasoning_content(response)
            self._client.reasoning_content_promotions.extend(promotions)
            return promoted
        return response

class _ReasoningContentChat(AsyncChat):
    @cached_property
    def completions(self) -> _ReasoningContentCompletions:
        return _ReasoningContentCompletions(self._client)

class ReasoningContentFallbackClient(AsyncOpenAI):

    def __init__(
        self, *args: Any, thinking_off: bool = False, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.reasoning_content_promotions: list[dict[str, Any]] = []
        self.thinking_off = thinking_off

    @cached_property
    def chat(self) -> _ReasoningContentChat:
        return _ReasoningContentChat(self)

class StructuredModel(Protocol):
    async def generate(
        self,
        *,
        schema: type[T],
        prompt: str,
        payload: Mapping[str, Any],
        envelope: RequestEnvelope,
        decode: Callable[[Any], dict[str, Any] | None] | None = None,
    ) -> T: ...

RETRY_INITIAL_S = 1.0
RETRY_MULTIPLIER = 2.0
RETRY_MAX_S = 60.0

MODEL_BUDGETS_PATH: Final[Path] = Path(__file__).with_name("model_budgets.json")
ROUTE_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {"attempt_timeout_s", "total_budget_s"})

@dataclass(frozen=True)
class RoutePolicy:

    attempt_timeout_s: float | None = None
    total_budget_s: float | None = None

@dataclass(frozen=True)
class ModelBudgets:
    transport_timeout_s: float
    defaults: RoutePolicy = RoutePolicy()
    routes: Mapping[str, RoutePolicy] = field(default_factory=dict)

    def policy_for(self, route: str) -> RoutePolicy:
        return self.routes.get(route, self.defaults)

def _seconds(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or value <= 0):
        raise ValueError(f"{field_name} must be a positive number or null")
    return float(value)

def _policy(entry: Any) -> RoutePolicy:
    if not isinstance(entry, Mapping) or set(entry) - ROUTE_POLICY_KEYS:
        raise ValueError(
            f"route policy needs only {sorted(ROUTE_POLICY_KEYS)}: {entry!r}")
    return RoutePolicy(
        **{name: _seconds(entry.get(name), name) for name in ROUTE_POLICY_KEYS})

def load_model_budgets(path: Path | None = None) -> ModelBudgets:
    document = json.loads((path or MODEL_BUDGETS_PATH).read_text())
    if not isinstance(document, Mapping) or set(document) - {
            "transport_timeout_s", "default", "routes"}:
        raise ValueError("model budgets need transport_timeout_s, "
                         "default and routes")
    transport = _seconds(document.get("transport_timeout_s"),
                         "transport_timeout_s")
    if transport is None:
        raise ValueError("transport_timeout_s must bound a socket read")
    routes = document.get("routes", {})
    if not isinstance(routes, Mapping) or not all(
            isinstance(route, str) for route in routes):
        raise ValueError("routes must map a route name to its policy")
    return ModelBudgets(
        transport_timeout_s=transport,
        defaults=_policy(document.get("default", {})),
        routes={route: _policy(entry) for route, entry in routes.items()})

@lru_cache(maxsize=1)
def _shipped_model_budgets() -> ModelBudgets:
    return load_model_budgets()

def route_budgets(budgets: ModelBudgets | None, route: str) -> RoutePolicy:
    return (budgets or _shipped_model_budgets()).policy_for(route)

async def _within(awaitable: Any, timeout_s: float | None) -> Any:
    if timeout_s is None:
        return await awaitable
    with anyio.fail_after(timeout_s):
        return await awaitable

SAFE_FAILURE_EXCEPTION_CLASSES = frozenset({
    "UnexpectedModelBehavior", "ToolRetryError", "ValidationError",
    "ContentFilterError", "ExceptionGroup", "BaseExceptionGroup",
    "TimeoutError", "APITimeoutError", "APIConnectionError",
    "RateLimitError", "ModelHTTPError", "ConnectError", "NetworkError",
    "RuntimeError", "ValueError", "TypeError", "JSONDecodeError",
})
SAFE_FAILURE_PHASES = frozenset({"content_filter", "no_tool_or_empty",
    "json_or_schema_validation", "http", "transport", "timeout", "unknown"})
SAFE_PYDANTIC_ERROR_TYPES = frozenset({
    "extra_forbidden", "json_invalid", "literal_error", "missing",
    "model_type", "string_type", "int_type", "int_parsing", "bool_type",
    "list_type", "dict_type", "greater_than_equal", "too_long",
    "too_short", "value_error",
    "claim_unsupported_missing_reason", "claim_supported_has_reasons",
    "verification_duplicate_claim_index", "verification_finding_empty",
    "verification_finding_duplicate", "verification_pass_with_findings",
    "verification_repair_without_findings",
})
SAFE_FAILURE_VALIDATION_SUBTYPES = frozenset({
    "unsupported_claim_missing_reason", "supported_claim_has_reasons",
    "pass_with_findings", "repair_without_findings", "duplicate_claim_index",
    "duplicate_or_empty_finding", "other_contract_invariant",
    "not_applicable",
})
_VALIDATION_SUBTYPE_BY_ERROR_TYPE = {
    "claim_unsupported_missing_reason": "unsupported_claim_missing_reason",
    "claim_supported_has_reasons": "supported_claim_has_reasons",
    "verification_pass_with_findings": "pass_with_findings",
    "verification_repair_without_findings": "repair_without_findings",
    "verification_duplicate_claim_index": "duplicate_claim_index",
    "verification_finding_empty": "duplicate_or_empty_finding",
    "verification_finding_duplicate": "duplicate_or_empty_finding",
}

def _safe_exception_name(value: type[BaseException] | str) -> str:
    name = value if isinstance(value, str) else value.__name__
    return name if name in SAFE_FAILURE_EXCEPTION_CLASSES else "<unknown-exception>"

def _safe_pydantic_error_type(value: object) -> str:
    name = str(value)
    return name if name in SAFE_PYDANTIC_ERROR_TYPES else "<unknown-error-type>"

USAGE_UNKNOWN_REASON = "usage_unknown"
USAGE_UNKNOWN_REASONS = frozenset({USAGE_UNKNOWN_REASON})

def _read_usage_requests(result: Any) -> tuple[int | None, str | None]:
    usage = getattr(result, "usage", None)
    if callable(usage):
        try:
            usage = usage()
        except Exception:
            return None, USAGE_UNKNOWN_REASON
    requests = getattr(usage, "requests", None)
    if requests is None:
        return None, USAGE_UNKNOWN_REASON
    try:
        return int(requests), None
    except (TypeError, ValueError):
        return None, USAGE_UNKNOWN_REASON

class DimeOpenAIChatModel(OpenAIChatModel):
    def __init__(self, model_name: str, *, provider: Any,
                 capabilities: EndpointCapabilities,
                 ladder: StrategyLadder | None = None) -> None:
        super().__init__(model_name, provider=provider)
        self.capabilities = capabilities
        self.ladder = ladder or StrategyLadder(capabilities)

    @property
    def strategy(self) -> OutputStrategy:
        return self.ladder.rung

    def on_ladder(self, ladder: StrategyLadder) -> DimeOpenAIChatModel:
        return DimeOpenAIChatModel(
            self.model_name, provider=self._provider,
            capabilities=self.capabilities, ladder=ladder)

    def _wire_schema(self, schema: Mapping[str, Any]) -> dict[str, Any]:
        return wire_schema_for(self.strategy, schema).schema

    def _map_json_schema(self, output_object):
        from dataclasses import replace
        return super()._map_json_schema(replace(
            output_object,
            json_schema=self._wire_schema(output_object.json_schema)))

    def _map_tool_definition(self, tool_def, model_settings):
        mapped = super()._map_tool_definition(tool_def, model_settings)
        if self.strategy is not OutputStrategy.TOOL_CALL:
            return mapped
        function = dict(mapped["function"])
        function["parameters"] = self._wire_schema(function["parameters"])
        return {**mapped, "function": function}

def _map_wire_response_format(json_schema: Mapping[str, Any], *,
                              name: str, strict: bool = True
                              ) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name, "strict": strict,
            "schema": wire_schema_for(
                OutputStrategy.STRICT_SCHEMA, json_schema).schema},
    }

class ProviderStructuredModel:
    def __init__(self, provider: ProviderName, model: str, *,
                 capabilities: Mapping[str, EndpointCapabilities] | None = None,
                 model_budgets: ModelBudgets | None = None,
                 http_client: httpx.AsyncClient | None = None) -> None:
        self.provider = provider
        self.model = model
        self._capabilities = capabilities
        self._budgets = model_budgets
        self._http_client = http_client
        self.last_provider: ProviderName | None = None
        self.last_model: str | None = None
        self.last_output_strategy: OutputStrategy | None = None
        self.last_failures: list[dict[str, Any]] = []
        self.last_request_count: int | None = None
        self.last_usage_unknown: str | None = None
        self.last_promotions: list[dict[str, Any]] = []

    @staticmethod
    def _reasoning_content_promotions(
        models: Sequence[tuple[ProviderName, Any]],
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for provider, model in models:
            client = getattr(model, "client", None)
            events = getattr(client, "reasoning_content_promotions", None) or []
            for event in events:
                records.append({"provider": provider, **event})
        return records

    @staticmethod
    def _retry_after_s(exc: BaseException) -> float | None:
        hint = getattr(exc, "retry_after", None)
        if isinstance(hint, bool):
            hint = None
        if isinstance(hint, (int, float)) and hint >= 0:
            return min(float(hint), RETRY_MAX_S)
        headers = getattr(getattr(exc, "response", None), "headers", None)
        if headers is not None:
            get = getattr(headers, "get", None)
            if callable(get):
                for key in ("retry-after", "Retry-After",
                            "retry-after-ms", "Retry-After-Ms"):
                    raw = get(key, None)
                    if raw is None:
                        continue
                    try:
                        value = float(str(raw).strip())
                    except (TypeError, ValueError):
                        continue
                    if "ms" in key.casefold():
                        value = value / 1000.0
                    if value >= 0:
                        return min(value, RETRY_MAX_S)
        text = str(exc)
        match = re.search(r'"retryDelay"\s*:\s*"([\d.]+)s"', text)
        if match is None:
            match = re.search(r"retry in ([\d.]+)s", text.casefold())
        if match is not None:
            try:
                value = float(match.group(1))
            except (TypeError, ValueError):
                return None
            if value >= 0:
                return min(value, RETRY_MAX_S)
        return None

    @staticmethod
    def _backoff_delay_s(retry_index: int,
                         retry_after_s: float | None = None) -> float:
        capped = min(RETRY_INITIAL_S * (RETRY_MULTIPLIER ** retry_index),
                     RETRY_MAX_S)
        floor = capped / 2.0
        delay = floor + random.uniform(0, floor)
        if retry_after_s is not None:
            delay = max(delay, min(retry_after_s, RETRY_MAX_S))
        return delay

    @staticmethod
    def _failure_chain_walk(exc: BaseException) -> tuple[list, list, list]:
        names: list = []
        details: list = []
        codes: list = []
        seen: set = set()
        pending: list = [exc]
        while pending and len(names) < 8:
            item = pending.pop(0)
            if id(item) in seen or not isinstance(item, BaseException):
                continue
            seen.add(id(item))
            names.append(type(item).__name__.casefold())
            details.append(str(item)[:2000].casefold())
            code = getattr(item, "status_code", None)
            if isinstance(code, bool) or not isinstance(code, int):
                response = getattr(item, "response", None)
                code = getattr(response, "status_code", None)
            if isinstance(code, int) and not isinstance(code, bool):
                codes.append(code)
            cause = item.__cause__
            context = item.__context__
            if isinstance(cause, BaseException):
                pending.append(cause)
            if isinstance(context, BaseException) and context is not cause:
                pending.append(context)
        return names, details, codes

    @staticmethod
    def _failure_class(exc: BaseException) -> str:
        names, details, codes = ProviderStructuredModel._failure_chain_walk(exc)
        name = " ".join(names)
        detail = " ".join(details)
        detail = detail + " " + detail.replace("_", " ")
        if "timeout" in name or "timed out" in detail or re.search(r"\b408\b", detail):
            return "timeout"
        if ("quota exhausted" in detail or "quota_exceeded" in detail or "perday" in detail
                or "per_day" in detail or "/day" in detail
                or "daily quota" in detail or "quota reset" in detail):
            return "quota_exhausted"
        if "rate" in name or "429" in detail or "rate limit" in detail:
            return "rate_limit"
        for code in codes:
            if code == 429:
                return "rate_limit"
            if 500 <= code <= 599:
                return "server_error"
            if code in (401, 403):
                return "authentication"
            if code in (400, 404):
                return "client_error"
        if any(code in detail for code in ("500", "502", "503", "504")):
            return "server_error"
        if "server_error" in detail or "server error" in detail:
            return "server_error"
        if "auth" in name or "401" in detail or "403" in detail:
            return "authentication"
        if (re.search(r"\b400\b", detail) or re.search(r"\b404\b", detail)):
            return "client_error"
        if ("validation" in name or "schema" in detail
                or "structured" in detail or "json" in detail):
            return "structured_output"
        if "context" in detail or "token" in detail and "limit" in detail:
            return "context_limit"
        if "filter" in name:
            return "content_filter"
        if "connect" in name or "network" in detail:
            return "network"
        return "provider_error"

    @staticmethod
    def _failure_phase(exc: BaseException, names: set) -> str:
        if isinstance(exc, ContentFilterError) or "ContentFilterError" in names:
            return "content_filter"
        if isinstance(exc, (TimeoutError, APITimeoutError)) or names & {
                "TimeoutError", "APITimeoutError"}:
            return "timeout"
        if isinstance(exc, (ModelHTTPError, RateLimitError)) or names & {
                "ModelHTTPError", "RateLimitError"}:
            return "http"
        if isinstance(exc, APIConnectionError) or names & {
                "APIConnectionError", "ConnectError", "NetworkError"}:
            return "transport"
        if isinstance(exc, UnexpectedModelBehavior):
            return ("json_or_schema_validation" if "ValidationError" in names
                    else "no_tool_or_empty")
        if "ValidationError" in names:
            return "json_or_schema_validation"
        return "unknown"

    @staticmethod
    def _validation_error_chain(exc: BaseException) -> tuple[list, list]:
        classes: list[str] = []
        validation_errors: list[dict[str, Any]] = []
        pending: list[BaseException] = [exc]
        seen: set[int] = set()
        while pending and len(classes) < 12:
            item = pending.pop(0)
            if id(item) in seen:
                continue
            seen.add(id(item))
            classes.append(_safe_exception_name(type(item)))
            if isinstance(item, ValidationError):
                validation_errors.extend({
                    "type": _safe_pydantic_error_type(error.get("type", "unknown")),
                    "loc": [str(part)[:120] for part in error.get("loc", ())[:16]],
                } for error in item.errors(
                    include_url=False, include_context=False, include_input=False)[:16])
            cause = item.__cause__
            context = item.__context__
            if isinstance(cause, BaseException):
                pending.append(cause)
            if isinstance(context, BaseException) and context is not cause:
                pending.append(context)
            if isinstance(item, BaseExceptionGroup):
                pending.extend(child for child in item.exceptions
                               if isinstance(child, BaseException))
        return classes, validation_errors

    @staticmethod
    def _mask_validation_error_locs(validation_errors: list[dict[str, Any]], schema_json: dict) -> None:
        known_fields: set[str] = set(schema_json.get("properties", {}))
        for definition in schema_json.get("$defs", {}).values():
            if isinstance(definition, dict):
                known_fields.update(definition.get("properties", {}))
        structural_markers = {"__root__", "union", "list", "dict"}
        for error in validation_errors:
            error["loc"] = [
                part if isinstance(part, int) else
                part if part in known_fields or part in structural_markers else
                "<unknown-field>"
                for part in error["loc"]
            ]

    @staticmethod
    def _validation_subtype(phase: str, validation_errors: list[dict[str, Any]]) -> str:
        validation_subtypes = {
            _VALIDATION_SUBTYPE_BY_ERROR_TYPE[error["type"]]
            for error in validation_errors
            if error["type"] in _VALIDATION_SUBTYPE_BY_ERROR_TYPE
        }
        has_unrecognized_validation_error = any(
            error["type"] not in _VALIDATION_SUBTYPE_BY_ERROR_TYPE
            for error in validation_errors
        )
        if phase != "json_or_schema_validation":
            return "not_applicable"
        if not validation_errors:
            return "other_contract_invariant"
        return (
            next(iter(validation_subtypes))
            if len(validation_subtypes) == 1
            and not has_unrecognized_validation_error
            else "other_contract_invariant"
        )

    @staticmethod
    def _safe_failure_taxonomy(exc: BaseException, *, schema: type[BaseModel],
                               route: str) -> dict[str, Any]:
        classes, validation_errors = ProviderStructuredModel._validation_error_chain(exc)
        phase = ProviderStructuredModel._failure_phase(exc, set(classes))
        schema_json = schema.model_json_schema()
        ProviderStructuredModel._mask_validation_error_locs(validation_errors, schema_json)
        schema_bytes = json.dumps(
            schema_json, sort_keys=True, separators=(",", ":")).encode()
        validation_subtype = ProviderStructuredModel._validation_subtype(phase, validation_errors)
        return {
            "failure_top_class": _safe_exception_name(type(exc)),
            "failure_class_chain": classes,
            "failure_phase": phase,
            "failure_validation_errors": validation_errors,
            "failure_validation_subtype": validation_subtype,
            "failure_schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
            "failure_route": route,
        }

    def _models(self) -> list[tuple[ProviderName, DimeOpenAIChatModel]]:
        configs = {
            "gemini": (GEMINI_BASE_URL, settings.gemini_api_key,
                       _gemini_model()),
            "nvidia": (NVIDIA_NIM_BASE_URL, settings.nvidia_nim_api_key,
                       _nvidia_nim_model()),
            "mistral": ("https://api.mistral.ai/v1", settings.mistral_api_key,
                        _mistral_free_model()),
            "openrouter": ("https://openrouter.ai/api/v1", settings.openrouter_api_key,
                           _openrouter_free_model()),
            "inception": ("https://api.inceptionlabs.ai/v1", settings.inception_api_key,
                          settings.inception_model or INCEPTION_DEFAULT),
            "groq": ("https://api.groq.com/openai/v1", settings.groq_api_key,
                     settings.groq_model or GROQ_DEFAULT),
            "cerebras": ("https://api.cerebras.ai/v1", settings.cerebras_api_key,
                         settings.cerebras_model or CEREBRAS_DEFAULT),
        }
        provider = self.provider
        entry = configs.get(provider)
        if entry is None:
            return []
        base_url, api_key, fallback_model = entry
        if not api_key:
            return []
        headers = ({
            "HTTP-Referer": "https://github.com/mythiipanda/dime",
            "X-Title": "Dime NBA Analyst",
        } if provider == "openrouter" else None)
        if provider == "cerebras":
            headers = {**(headers or {}), "User-Agent": "dime-agent/1.0"}
        requested = self.model
        if provider == "gemini":
            accepted_model = _gemini_model(requested)
        elif provider == "nvidia":
            accepted_model = _nvidia_nim_model(requested)
        elif provider == "openrouter":
            accepted_model = _openrouter_free_model(requested)
        elif provider == "mistral":
            accepted_model = _mistral_free_model()
        elif provider == "groq":
            accepted_model = _groq_free_model(requested)
        elif provider == "cerebras":
            accepted_model = _cerebras_model(requested)
        else:
            accepted_model = settings.inception_model or INCEPTION_DEFAULT
        if (provider != "inception"
                and not is_free_model(provider, accepted_model)):
            return []
        client = ReasoningContentFallbackClient(
            base_url=base_url,
            api_key=api_key,
            timeout=(self._budgets
                     or _shipped_model_budgets()).transport_timeout_s,
            max_retries=0,
            default_headers=headers,
            thinking_off=(provider == "nvidia"),
            http_client=self._http_client,
        )
        return [(provider, DimeOpenAIChatModel(
            accepted_model,
            provider=OpenAIProvider(openai_client=client),
            capabilities=capabilities_for(base_url, self._capabilities),
        ))]

    async def generate(
        self,
        *,
        schema: type[T],
        prompt: str,
        payload: Mapping[str, Any],
        envelope: RequestEnvelope,
        decode: Callable[[Any], dict[str, Any] | None] | None = None,
    ) -> T:
        models = self._models()
        if not models:
            raise RuntimeError("no configured structured-output provider")
        self.last_provider = None
        self.last_model = None
        self.last_output_strategy = None
        self.last_failures = []
        self.last_promotions = []
        self.last_decode_extra = None
        user_prompt = json.dumps(payload, sort_keys=True, default=str)
        provider, model = models[0]
        policy = route_budgets(self._budgets, envelope.route)
        budget_deadline = (None if policy.total_budget_s is None
                           else time.monotonic() + policy.total_budget_s)
        deadlines = [value for value in
                     (budget_deadline, RUN_MODEL_DEADLINE.get())
                     if value is not None]
        deadline = min(deadlines) if deadlines else None
        budget_exhausted = False
        ladder = StrategyLadder(model.capabilities)
        for attempt_number in range(1, len(STRATEGY_LADDER) + 1):
            remaining = (None if deadline is None
                         else deadline - time.monotonic())
            if remaining is not None and remaining <= 0:
                budget_exhausted = True
                break
            rung = ladder.rung
            attempt_model = model.on_ladder(ladder)
            attempt_timeout = policy.attempt_timeout_s
            if attempt_timeout is not None and remaining is not None:
                attempt_timeout = min(attempt_timeout, remaining)
            started = time.perf_counter()
            try:
                agent = Agent(
                    attempt_model,
                    instructions=prompt,
                    output_type=output_type_for(
                        rung, schema, model.capabilities),
                    retries=settings.llm_max_retries,
                    capabilities=[Hooks(
                        before_output_validate=repaired_output_payload)],
                )
                result = await _within(agent.run(user_prompt), attempt_timeout)
                ladder.record(attempt_number=attempt_number, failure_kind=None)
                self.last_output_strategy = rung
                self.last_provider = provider
                self.last_model = (
                    f"mistral_free_limit:{model.model_name}"
                    if provider == "mistral" else model.model_name
                )
                request_count, usage_unknown = _read_usage_requests(result)
                self.last_request_count = request_count
                self.last_usage_unknown = usage_unknown
                self.last_promotions = self._reasoning_content_promotions(models)
                if decode is not None:
                    self.last_decode_extra = decode(result.output)
                return result.output
            except Exception as exc:
                failure_kind = classify_exception(exc)
                ladder.record(
                    attempt_number=attempt_number, failure_kind=failure_kind)
                self.last_failures.append({
                    "route": envelope.route,
                    "provider": provider,
                    "model": (f"mistral_free_limit:{model.model_name}"
                              if provider == "mistral" else model.model_name),
                    "attempt_number": attempt_number,
                    "output_strategy": str(rung),
                    "exception_type": _safe_exception_name(type(exc)),
                    "message_class": (
                        str(FailureKind.SCHEMA_REJECTED)
                        if failure_kind is FailureKind.SCHEMA_REJECTED
                        else self._failure_class(exc)),
                    "latency_ms": max(0, round(
                        (time.perf_counter() - started) * 1000)),
                    **self._safe_failure_taxonomy(
                        exc, schema=schema, route=envelope.route),
                })
                if ladder.descend(failure_kind) is None:
                    break
                wait = self._backoff_delay_s(
                    attempt_number - 1, self._retry_after_s(exc))
                if deadline is not None and wait >= deadline - time.monotonic():
                    budget_exhausted = True
                    break
                await anyio.sleep(wait)
        if budget_exhausted:
            self.last_failures.append({
                "route": envelope.route,
                "provider": envelope.route,
                "model": "deadline",
                "attempt_number": len(self.last_failures) + 1,
                "output_strategy": str(ladder.rung),
                "exception_type": "TimeoutError",
                "message_class": f"{envelope.route}_deadline",
                "latency_ms": 0,
            })
        self.last_promotions = self._reasoning_content_promotions(models)
        summary = ", ".join(
            f"{item['provider']}:{item['exception_type']}:{item['message_class']}"
            for item in self.last_failures
        )
        raise RuntimeError(
            "all structured-output providers failed"
            + (f" [{summary}]" if summary else ""))

_PROVIDER_ROUTE_PROMPT_NAMES = {
    "intake": "intake",
    "requirement_review": "requirement_review_v3",
    "planner": "planner_v3",
    "synthesizer": "synthesizer",
    "repair": "repair_answer",
    "semantic_verifier": "verifier",
}
_PROVIDER_ROUTE_PROMPTS: dict[str, str] | None = None
MODEL_ROUTES = frozenset(_PROVIDER_ROUTE_PROMPT_NAMES)

def bind_provider_route_prompts() -> dict[str, str]:
    global _PROVIDER_ROUTE_PROMPTS
    if _PROVIDER_ROUTE_PROMPTS is None:
        _PROVIDER_ROUTE_PROMPTS = {
            route: load_prompt(name)
            for route, name in _PROVIDER_ROUTE_PROMPT_NAMES.items()
        }
    return dict(_PROVIDER_ROUTE_PROMPTS)

def provider_route_prompt(route: str, prompt_name: str) -> str:
    expected = _PROVIDER_ROUTE_PROMPT_NAMES.get(route)
    if expected != prompt_name:
        raise ValueError("provider route and prompt name are not registered")
    return bind_provider_route_prompts()[route]

class ModelStage:
    prompt_name: str
    route: str
    schema: type[BaseModel]

    def __init__(
        self,
        model: StructuredModel,
        *,
        provider: str,
        model_name: str,
        planner_version: str = "v2",
        budgets: Mapping[str, int | float] | None = None,
        skill_library: SkillLibrary | None = None,
        requirement_review: bool = False,
    ) -> None:
        for name, value in {
            "provider": provider,
            "model_name": model_name,
            "planner_version": planner_version,
        }.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        self._model = model
        self._provider = provider
        self._model_name = model_name
        self._planner_version = planner_version
        self._budgets = dict(budgets or {})
        self._skills = skill_library or SkillLibrary()
        self._requirement_review = requirement_review
        self.last_envelope: RequestEnvelope | None = None

    async def _generate(self, payload: Mapping[str, Any], decode=None) -> Any:
        return await self._generate_as(
            prompt_name=self.prompt_name, route=self.route,
            schema=self.schema, payload=payload, decode=decode,
        )

    async def _generate_as(
        self, *, prompt_name: str, route: str, schema: type[BaseModel],
        payload: Mapping[str, Any], decode=None,
    ) -> Any:
        prompt = provider_route_prompt(route, prompt_name)
        envelope = RequestEnvelope.freeze(
            provider=self._provider, model=self._model_name, route=route,
            prompt=prompt, context=payload,
            tool_schemas=schema.model_json_schema(),
            planner_version=self._planner_version, budgets=self._budgets,
            skill_hashes=skill_hashes(list(payload.get("skills", []))),
        )
        self.last_envelope = envelope
        call = dict(schema=schema, prompt=prompt, payload=payload,
                    envelope=envelope)
        if decode is not None:
            call["decode"] = decode
        return await self._model.generate(**call)

def catalog_for_wire(catalog: Mapping[str, Any]) -> dict[str, Any]:
    return {
        name: (
            {key: value for key, value in entry.items()
             if key != "dependent_entity_arguments" or value}
            if isinstance(entry, Mapping) else entry
        )
        for name, entry in catalog.items()
    }

def capability_arguments_for(requirement, capability_id: str) -> dict[str, Any]:
    if requirement.capability_argument_sets:
        match = next((item for item in requirement.capability_argument_sets
                      if item.capability_id == capability_id), None)
        if match is None:
            raise ValueError(f"requirement {requirement.id} has no arguments for {capability_id}")
        return dict(match.arguments)
    return dict(requirement.capability_arguments)

def _sets_projection(sets) -> dict[str, Any]:
    maps = [dict(item.arguments) for item in sets]
    return maps[0] if maps and all(item == maps[0] for item in maps) else {}

def update_capability_arguments(requirement, capability_id: str,
                                updates: Mapping[str, Any]):
    if not requirement.capability_argument_sets:
        if capability_id not in requirement.capability_options:
            raise ValueError(f"requirement {requirement.id} disallows {capability_id}")
        return requirement.model_copy(update={"capability_arguments": {
            **requirement.capability_arguments, **updates}})
    sets = list(requirement.capability_argument_sets)
    from v2.arguments import RequirementArguments, encode_argument
    rebuilt=[]
    for item in sets:
        if item.capability_id != capability_id:
            rebuilt.append(item); continue
        values={**dict(item.arguments),**updates}
        rebuilt.append(item.model_copy(update={"arguments":RequirementArguments.model_validate(
            {"entries":[encode_argument(k,v) for k,v in values.items()]})}))
    return requirement.model_copy(update={"capability_argument_sets":rebuilt,
        "capability_arguments":_sets_projection(rebuilt)})

def _update_all_existing_argument(requirement, key: str, value: Any):
    targets = [item.capability_id for item in requirement.capability_argument_sets
               if key in item.arguments]
    if not targets and key in requirement.capability_arguments:
        targets = list(requirement.capability_options)
    for capability_id in targets:
        requirement = update_capability_arguments(requirement, capability_id, {key:value})
    return requirement

def narrow_requirement(requirement, capabilities: Sequence[str]):
    capabilities=list(dict.fromkeys(capabilities))
    sets=[item for item in requirement.capability_argument_sets
          if item.capability_id in capabilities]
    return requirement.model_copy(update={"capability_options":capabilities,
        "capability_argument_sets":sets,
        "capability_arguments":(_sets_projection(sets) if sets else
            dict(requirement.capability_arguments))})

def ranked_team_arguments_error(
    capability_id: str, arguments: Mapping[str, Any],
) -> str | None:
    if capability_id != "team_ratings":
        return None
    metric = arguments.get("requested_metric", "")
    direction = arguments.get("ranking_direction", "")
    team = arguments.get("team", "")
    if direction not in ("", *RANKING_DIRECTIONS):
        return ("RANKED_ARGUMENT_CONFLICT: ranked team_ratings ranking_direction "
                "must be one of 'asc', 'desc'")
    if metric == "" and direction != "":
        return ("RANKED_ARGUMENT_CONFLICT: ranked team_ratings ranking_direction "
                "requires requested_metric")
    if metric != "" and team == "" and direction not in RANKING_DIRECTIONS:
        return ("RANKED_DIRECTION_UNSPECIFIED: ranked team_ratings requires "
                "ranking_direction")
    if metric != "" and direction in RANKING_DIRECTIONS:
        expected = TEAM_RATING_METRICS.get(metric, {}).get("direction")
        if expected is not None and direction != expected:
            return ("RANKED_DIRECTION_CONFLICT: ranked team_ratings ranking_direction "
                    f"{direction!r} contradicts {metric} (expected {expected!r})")
    return None

METRIC_AGREEMENT_CAPABILITIES = (
    "team_ratings", "clutch", "on_off", "lineups", "playoff_team_ratings")

def served_capability_metrics(capability_id: str) -> set[str]:
    spec = CAPABILITIES.get(capability_id)
    if spec is None:
        return set()
    names = set(spec.units) | {
        key for key in spec.metric_definitions if not key.startswith("__")}
    return {str(name).upper() for name in names}

class ModelIntake(ModelStage):
    prompt_name = "intake"
    route = "intake"
    schema = TaskSpec

    def __init__(self, *args: Any, capability_catalog: Mapping[str, str],
                 **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._catalog = dict(capability_catalog)
        self._wire_catalog = catalog_for_wire(self._catalog)

    def _catalog_with_declared_schemas(self) -> dict:
        from v2.runtime.assembly import declared_schema_for

        enriched = {}
        for capability_id, entry in self._wire_catalog.items():
            if not isinstance(entry, Mapping):
                enriched[capability_id] = entry
                continue
            schema = declared_schema_for(capability_id)
            enriched[capability_id] = (
                {**entry, "declared_schema": schema}
                if schema is not None else entry)
        return enriched

    @staticmethod
    def _bounded_context(context: Sequence[ConversationTurn]) -> tuple[ConversationTurn, ...]:
        from v2.contracts import MAX_INTAKE_CONTEXT_TURNS
        return tuple(context[-MAX_INTAKE_CONTEXT_TURNS:])

    @classmethod
    def _live_option_available(cls, task: TaskSpec, capability: str) -> bool:
        for requirement in task.requirements:
            options = [str(option)
                       for option in requirement.capability_options]
            if capability not in options:
                continue
            for option in options:
                spec = CAPABILITIES.get(option)
                if spec is not None and spec.live_fallback:
                    return True
        return False

    @classmethod
    def _coverage_table_groups(cls, task: TaskSpec):
        from v2.adapters.coverage import (
            DEFAULT_TABLE,
            table_for_metric,
            task_coverage_groups_labeled,
        )
        labeled = task_coverage_groups_labeled(task)
        if not labeled:
            if list(getattr(task, "required_evidence", None) or []) \
                    and not list(task.metric_ids or []):
                return None
            implied = [table_for_metric(metric) for metric in task.metric_ids]
            if not implied:
                implied = [DEFAULT_TABLE]
            labeled = [(None, frozenset({name}))
                       for name in dict.fromkeys(implied)]
        return labeled

    @classmethod
    def _uncovered_table_split(cls, task: TaskSpec, labeled, covered_groups, sets, requested):
        blocked = []
        live_tables = []
        live_capabilities = []
        for (label, group), covered in zip(labeled, covered_groups):
            if covered:
                continue
            live = (label is not None
                    and cls._live_option_available(task, label))
            for table in sorted(group):
                if requested not in sets.get(table, frozenset()):
                    if live:
                        if table not in live_tables:
                            live_tables.append(table)
                        if label not in live_capabilities:
                            live_capabilities.append(label)
                    elif table not in blocked:
                        blocked.append(table)
        return blocked, live_tables, live_capabilities

    @staticmethod
    def _live_source_note(requested: str, live_tables, live_capabilities) -> str:
        if len(live_capabilities) == 1:
            return (
                f"Requested {requested} season has no rows in "
                f"{', '.join(live_tables)}; "
                f"{live_capabilities[0]} will attempt its live source "
                f"instead."
            )
        return (
            f"Requested {requested} season has no rows in "
            f"{', '.join(live_tables)}; "
            f"{', '.join(live_capabilities)} will attempt their "
            f"live sources instead."
        )

    @staticmethod
    def _season_unavailable_question(requested: str, blocked, known) -> str:
        if known:
            return (
                f"Numbers for the {requested} season are not available "
                f"for {', '.join(blocked)}. "
                f"Available seasons: {', '.join(known)}. "
                "Which season should be used instead?"
            )
        return (
            f"Numbers for the {requested} season are not available "
            f"for {', '.join(blocked)}. "
            "Which season should be used instead?"
        )

    @classmethod
    def _mark_uncovered_season(cls, task: TaskSpec) -> TaskSpec:
        if task.season is None:
            return task
        from v2.adapters.coverage import (
            parse_season_start,
            season_beyond_upper_bound,
            table_seasons,
        )
        labeled = cls._coverage_table_groups(task)
        if labeled is None:
            return task
        groups = [tables for _, tables in labeled]
        names = list(dict.fromkeys(
            table for group in groups for table in sorted(group)))
        requested = task.season.value
        sets = {name: table_seasons(name) for name in names}
        covered_groups = [
            any(requested in sets.get(table, frozenset()) for table in group)
            for group in groups
        ]
        if (
            parse_season_start(requested) is not None
            and all(covered_groups)
            and not season_beyond_upper_bound(requested)
        ):
            return task
        blocked, live_tables, live_capabilities = cls._uncovered_table_split(
            task, labeled, covered_groups, sets, requested)
        assumptions = list(task.assumptions)
        if live_tables:
            assumptions.append(
                cls._live_source_note(requested, live_tables, live_capabilities))
        if not blocked:
            return task.model_copy(update={
                "assumptions": list(dict.fromkeys(assumptions)),
            })
        known = sorted({
            season
            for seasons in sets.values()
            for season in seasons
            if parse_season_start(season) is not None
        })
        question = cls._season_unavailable_question(requested, blocked, known)
        note = (
            f"Requested {requested} season has no rows in "
            f"{', '.join(blocked)}; leaving the request unchanged."
        )
        return task.model_copy(update={
            "open_questions": list(dict.fromkeys(
                [*task.open_questions, question])),
            "assumptions": list(dict.fromkeys(
                [*assumptions, note])),
        })

    def _apply_context_season(self, task: TaskSpec, context: Sequence[ConversationTurn]) -> TaskSpec:
        if (task.season is not None and task.season.source == "default"
                and "trade-analysis" in task.skills):
            context_seasons = [
                season for turn in context
                for season in re.findall(r"\b20\d{2}-\d{2}\b", turn.content)
            ]
            if context_seasons:
                return task.model_copy(update={
                    "season": task.season.model_copy(update={
                        "value": context_seasons[-1], "source": "context",
                        "confidence": 1.0,
                    }),
                    "assumptions": list(dict.fromkeys([
                        *task.assumptions,
                        "Performance uses the prior context season; contracts may use the forward trade window.",
                    ])),
                })
        return task

    def _fold_resolvable_questions(self, task: TaskSpec) -> TaskSpec:
        resolvable_questions = []
        for question in task.open_questions:
            folded = question.casefold()
            evidence_lookup = bool(set(task.required_evidence)) and any(
                token in folded for token in (
                    "team", "contract", "remaining years", "player option",
                    "roster", "role", "availability", "salary",
                ))
            analytical_assumption = any(
                token in folded for token in (
                    "risk tolerance", "front office", "preference",
                    "appetite", "willingness", "trade intent",
                ))
            optional_capability_argument = (
                "game_prediction" in task.required_evidence
                and any(token in folded for token in (
                    "specific upcoming game", "specific game date",
                    "general matchup", "which game", "game date",
                    "specific date", "date of the game",
                ))
            )
            if evidence_lookup or analytical_assumption or optional_capability_argument:
                resolvable_questions.append(question)
        if resolvable_questions:
            return task.model_copy(update={
                "open_questions": [question for question in task.open_questions
                                   if question not in resolvable_questions],
                "assumptions": list(dict.fromkeys([
                    *task.assumptions, *resolvable_questions])),
            })
        return task

    def _adjusted_required_evidence(self, task: TaskSpec, request: str) -> list[str]:
        player_count = sum(entity.type == "player" for entity in task.entities)
        optional_evidence = set()
        if player_count < 2:
            optional_evidence.update({"player_comparison", "trade_value"})
        required_evidence = [
            name for name in task.required_evidence
            if name not in optional_evidence
        ]
        from v2.runtime.subsumption import capability_subsumes
        required_evidence = [
            name for name in required_evidence
            if not any(
                other != name and capability_subsumes(other, name)
                for other in required_evidence
            )
        ]
        if "trade-analysis" in task.skills and player_count >= 2:
            baseline = (
                "player_report", "player_evaluation", "player_comparison",
                "trade_value", "contracts", "trades",
            )
            required_evidence = list(dict.fromkeys([
                *required_evidence,
                *(name for name in baseline if name in self._catalog),
            ]))
        if ("league-ratings" in task.skills
                and "game_prediction" not in required_evidence):
            folded_request = request.casefold()
            baseline = ["team_ratings"]
            if any(token in folded_request for token in (
                    "player", "players", "individual")):
                baseline.append("player_ratings")
            if any(token in folded_request for token in (
                    "playoff", "playoffs", "postseason")):
                baseline.append("playoff_team_ratings")
            required_evidence = list(dict.fromkeys([
                *required_evidence,
                *(name for name in baseline if name in self._catalog),
            ]))
        if ("game_prediction" in self._catalog
                and len([entity for entity in task.entities
                         if entity.type == "team"]) == 2
                and any(token in request.casefold() for token in (
                    "who wins", "who will win", "win probability",
                    "predict", "prediction", "projected score",
                    "projected total", "pre-game", "pregame",
                ))):
            required_evidence = list(dict.fromkeys([
                *required_evidence, "game_prediction",
            ]))
        return required_evidence

    def _ensure_default_season(self, task: TaskSpec) -> TaskSpec:
        if task.season is None:
            from shared.tools._core import last_completed_season
            from v2.contracts import SeasonRef
            _derived_season = last_completed_season()
            if _derived_season is not None:
                task = task.model_copy(update={
                    "season": SeasonRef(
                        value=_derived_season, source="default",
                        confidence=1.0),
                })
        if task.season is not None and task.season.source == "default":
            from shared.tools._core import last_completed_season
            _derived_season = last_completed_season()
            if _derived_season is not None:
                task = task.model_copy(update={
                    "season": task.season.model_copy(
                        update={"value": _derived_season}),
                })
        return task

    async def understand(
        self, request: str, context: Sequence[ConversationTurn] = ()
    ) -> TaskSpec:
        bounded = self._bounded_context(context)
        payload = {
            "question": request,
            "current_date": datetime.now(UTC).date().isoformat(),
            "conversation_context": [turn.model_dump(mode="json")
                                     for turn in bounded],
            "capability_catalog": self._catalog_with_declared_schemas(),
            "skill_catalog": self._skills.catalog(),
        }
        if bounded:
            payload["reference_resolution"] = {
                "instruction": (
                    "Resolve references and omitted subjects from the "
                    "bounded conversation context before leaving a user "
                    "question open. Preserve an open question only when "
                    "the context supports multiple materially different "
                    "referents or supplies none. Return a complete "
                    "replacement TaskSpec."
                ),
            }
        task = await self._generate(payload)
        task = task.model_copy(update={
            "skills": [name for name in task.skills
                       if name in self._skills.skills],
        })
        task = self._apply_context_season(task, context)
        task = self._fold_resolvable_questions(task)
        task = task.model_copy(update={
            "required_evidence": [
                name for name in task.required_evidence
                if name not in set(task.skills)
            ],
        })
        if self._requirement_review and not task.open_questions:
            unknown_requirements = sorted(
                {capability for requirement in task.requirements
                 for capability in requirement.capability_options}
                - self._catalog.keys()
            )
            if unknown_requirements:
                raise ValueError(
                    "requirement review selected unknown capabilities: "
                    f"{unknown_requirements}"
                )
            scope = " ".join([request, task.goal, task.deliverable,
                              *task.subquestions]).casefold()
            task = self._expand_home_away_requirements(task, scope)
            task = task.model_copy(update={
                "skills": [name for name in task.skills
                           if name in self._skills.skills],
            })
        required_evidence = self._adjusted_required_evidence(task, request)
        task = self._ensure_default_season(task)
        task = self._mark_uncovered_season(task)
        task = task.model_copy(update={
            "required_evidence": required_evidence,
        })
        if task.season is not None:
            task = task.model_copy(update={
                "requirements": [
                    _update_all_existing_argument(requirement, "season", task.season.value)
                    for requirement in task.requirements
                ],
            })
        unknown = sorted(set(task.required_evidence) - self._catalog.keys())
        if unknown:
            raise ValueError(f"intake selected unknown capabilities: {unknown}")
        task = _canonicalize_calculation_requirements(task)
        task = _drop_unresolvable_requested_outputs(task)
        task = _align_requirement_requested_outputs(task)
        task = _backfill_open_question_outputs(task)
        task = task.model_copy(update={
            "subject_entity_type": _derive_subject_entity_type(task),
        })
        self._skills.activate(task.skills)
        return task

    def _capability_argument_names(self, capabilities: Sequence[str]) -> set[str] | None:
        accepted: list[set[str]] = []
        for name in capabilities:
            entry = self._catalog.get(name)
            schema = entry.get("arguments") if isinstance(entry, Mapping) else None
            properties = schema.get("properties") if isinstance(schema, Mapping) else None
            if not isinstance(properties, Mapping):
                return None
            accepted.append(set(properties))
        return set.intersection(*accepted) if accepted else set()

    def _project_capability_arguments(
        self, arguments: Mapping[str, Any], capabilities: Sequence[str],
    ) -> dict[str, Any]:
        names = self._capability_argument_names(capabilities)
        if names is None:
            return {}
        return {key: value for key, value in arguments.items() if key in names}

    def _project_legacy_requirement(self, requirement, capabilities: Sequence[str]):
        if requirement.capability_argument_sets:
            return narrow_requirement(requirement, capabilities)
        capabilities = list(dict.fromkeys(capabilities))
        return requirement.model_copy(update={
            "capability_options": capabilities,
            "capability_arguments": self._project_capability_arguments(
                requirement.capability_arguments, capabilities)})

    def _project_mixed_requirement_arguments(
        self, review: RequirementReview,
    ) -> RequirementReview:
        return review.model_copy(update={"requirements": [
            self._project_legacy_requirement(item, item.capability_options)
            for item in review.requirements
        ]})

    def _intake_typed_ranked_arguments(self, task: TaskSpec) -> dict[str, Any]:
        typed: dict[str, Any] = {}
        for item in task.requirements:
            if "team_ratings" not in item.capability_options:
                continue
            for key, value in capability_arguments_for(item, "team_ratings").items():
                if key in ("requested_metric", "ranking_direction", "team") \
                        and value not in (None, "") and key not in typed:
                    typed[key] = value
        return typed

    def _intake_ranked_typed_conflicts(self, task: TaskSpec) -> list[str]:
        seen: dict[str, Any] = {}
        seasons: set[str] = set()
        conflicts: list[str] = []
        for item in task.requirements:
            if "team_ratings" not in item.capability_options:
                continue
            arguments = capability_arguments_for(item, "team_ratings")
            for key in ("requested_metric", "ranking_direction", "team"):
                value = arguments.get(key)
                if value in (None, ""):
                    continue
                if key not in seen:
                    seen[key] = value
                elif seen[key] != value and key not in conflicts:
                    conflicts.append(key)
            season = arguments.get("season")
            if season not in (None, ""):
                seasons.add(season)
        task_season = task.season.value if task.season else None
        if len(seasons) > 1 or (task_season and seasons and seasons != {task_season}):
            conflicts.append("season")
        return conflicts

    @staticmethod
    def _ranked_typed_carries(
        review_arguments: Mapping[str, Any], intake_typed: Mapping[str, Any],
    ) -> dict[str, Any]:
        carried: dict[str, Any] = {}
        for key in ("requested_metric", "ranking_direction", "team"):
            review_value = review_arguments.get(key)
            intake_value = intake_typed.get(key)
            if review_value in (None, "") and intake_value not in (None, ""):
                carried[key] = intake_value
        return carried

    @staticmethod
    def _ranked_typed_conflicts(
        review_arguments: Mapping[str, Any], intake_typed: Mapping[str, Any],
        task_season: str | None,
    ) -> list[str]:
        conflicts: list[str] = []
        for key in ("requested_metric", "ranking_direction", "team"):
            review_value = review_arguments.get(key)
            intake_value = intake_typed.get(key)
            if (review_value not in (None, "") and intake_value not in (None, "")
                    and review_value != intake_value):
                conflicts.append(key)
        season = review_arguments.get("season")
        if season not in (None, "") and task_season and season != task_season:
            conflicts.append("season")
        return conflicts

    def _decode_review_ranked_arguments(
        self, wire: RequirementReviewWire,
    ) -> dict[str, dict[str, Any]]:
        if "team_ratings" not in self._catalog:
            return {}
        schema = self._review_argument_schema("team_ratings")
        decoded: dict[str, dict[str, Any]] = {}
        for requirement in (wire.requirements or []):
            if "team_ratings" not in requirement.capability_options:
                continue
            for option in requirement.capability_argument_sets:
                if option.capability_id != "team_ratings":
                    continue
                decoded[requirement.id] = dict(provider_to_source(
                    option.arguments, "requirement",
                    route="requirement_review", capability_id="team_ratings",
                    argument_schema=schema))
        return decoded

    def _ranked_review_typed_decisions(
        self, task: TaskSpec, arguments_by_id: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        intake_typed = self._intake_typed_ranked_arguments(task)
        task_season = task.season.value if task.season else None
        intake_conflicts = self._intake_ranked_typed_conflicts(task)
        decisions: dict[str, dict[str, Any]] = {}
        for requirement_id, review_arguments in arguments_by_id.items():
            if intake_conflicts:
                decisions[requirement_id] = {
                    "intake_conflicts": intake_conflicts,
                    "review_conflicts": [],
                    "conflict_rows": [
                        {"route": "requirement_review",
                         "capability_id": "team_ratings", "key": key,
                         "rule": "ranked-argument-conflict"}
                        for key in intake_conflicts],
                    "carries": {}}
                continue
            review_conflicts = self._ranked_typed_conflicts(
                review_arguments, intake_typed, task_season)
            decisions[requirement_id] = {
                "intake_conflicts": [],
                "review_conflicts": review_conflicts,
                "conflict_rows": [
                    {"route": "requirement_review",
                     "capability_id": "team_ratings", "key": key,
                     "rule": "ranked-argument-conflict"}
                    for key in review_conflicts],
                "carries": ({}
                            if review_conflicts
                            else self._ranked_typed_carries(
                                review_arguments, intake_typed))}
        return decisions

    def _apply_ranked_carries_to_wire(
        self, task: TaskSpec, wire: RequirementReviewWire,
        ranked_arguments: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> RequirementReviewWire:
        from v2.arguments import ProviderWireArguments, encode_argument, SLOTS
        if wire.requirements is None or "team_ratings" not in self._catalog:
            return wire
        if not ranked_arguments:
            ranked_arguments = self._decode_review_ranked_arguments(wire)
        decisions = self._ranked_review_typed_decisions(task, ranked_arguments)
        if not any(decision["carries"] for decision in decisions.values()):
            return wire
        schema = self._review_argument_schema("team_ratings")
        properties = schema.get("properties", {})
        slot_names = list(dict.fromkeys(SLOTS.values()))

        def wire_entry(key: str, value: Any) -> dict[str, Any]:
            row = encode_argument(key, value, properties.get(key, {}))
            active = "value" if row["kind"] == "null" else f"{row['kind']}_value"
            slots = {name: None for name in slot_names}
            slots[active] = row[active]
            return {"key": key, "kind": row["kind"], **slots}

        carried_requirements = []
        for requirement in wire.requirements:
            if "team_ratings" not in requirement.capability_options:
                carried_requirements.append(requirement)
                continue
            carried = decisions.get(requirement.id, {}).get("carries", {})
            carried_sets = []
            for option in requirement.capability_argument_sets:
                if option.capability_id != "team_ratings" or not carried:
                    carried_sets.append(option)
                    continue
                values = {**ranked_arguments[requirement.id], **carried}
                carried_sets.append(option.model_copy(update={
                    "arguments": ProviderWireArguments.model_validate({
                        "entries": [wire_entry(key, value)
                                    for key, value in values.items()]})}))
            carried_requirements.append(requirement.model_copy(
                update={"capability_argument_sets": carried_sets}))
        return wire.model_copy(update={"requirements": carried_requirements})

    def _reconcile_typed_ranked_arguments(
        self, task: TaskSpec, review: RequirementReview,
    ) -> tuple[RequirementReview, list[dict[str, str]], list[dict[str, str]]]:
        if "team_ratings" not in task.required_evidence:
            return review, [], []
        arguments_by_id = {
            requirement.id: capability_arguments_for(requirement, "team_ratings")
            for requirement in review.requirements
            if "team_ratings" in requirement.capability_options}
        decisions = self._ranked_review_typed_decisions(task, arguments_by_id)
        reconciled: list[EvidenceRequirement] = []
        carried_rows: list[dict[str, str]] = []
        conflict_rows: list[dict[str, str]] = []
        for requirement in review.requirements:
            if "team_ratings" not in requirement.capability_options:
                reconciled.append(requirement)
                continue
            decision = decisions[requirement.id]
            conflict_rows.extend(decision["conflict_rows"])
            if decision["intake_conflicts"] or decision["review_conflicts"]:
                continue
            if decision["carries"]:
                requirement = update_capability_arguments(
                    requirement, "team_ratings", decision["carries"])
                carried_rows.extend(
                    {"route": "requirement_review", "capability_id": "team_ratings",
                     "key": key, "rule": "carried-from-intake"}
                    for key in decision["carries"])
            reconciled.append(requirement)
        return review.model_copy(update={"requirements": reconciled}), carried_rows, conflict_rows

    def _review_argument_schema(self, capability_id: str) -> dict:
        entry = self._catalog.get(capability_id)
        if not isinstance(entry, Mapping): raise ValueError("unknown capability")
        schema = dict(entry.get("arguments", {})); schema.pop("required", None)
        return schema

    def _collect_review_drops(self, wire: RequirementReviewWire) -> dict | None:
        drops: list[dict] = []
        for requirement in wire.requirements or []:
            for option in requirement.capability_argument_sets:
                entry = self._catalog.get(option.capability_id)
                if not isinstance(entry, Mapping): continue
                provider_to_source(option.arguments, "requirement",
                    route="requirement_review", capability_id=option.capability_id,
                    argument_schema=self._review_argument_schema(option.capability_id),
                    drops=drops)
        return {"null_as_omitted_drops": drops} if drops else None

    def _validate_requirement_wire(self, wire: RequirementReviewWire) -> None:
        from jsonschema import Draft202012Validator
        if wire.requirements is None:
            raise ValueError("requirement review requirements may not be null")
        for requirement in wire.requirements:
            if set(requirement.capability_options) != {x.capability_id for x in requirement.capability_argument_sets}:
                raise ValueError("capability argument sets must cover options")
            for option in requirement.capability_argument_sets:
                schema = self._review_argument_schema(option.capability_id)
                arguments = dict(provider_to_source(option.arguments, "requirement",
                    route="requirement_review", capability_id=option.capability_id,
                    argument_schema=schema))
                errors = list(Draft202012Validator(schema).iter_errors(arguments))
                if errors: raise ValueError(f"invalid {option.capability_id} requirement arguments: {errors[0].message}")
                ranked_error = ranked_team_arguments_error(option.capability_id, arguments)
                if ranked_error: raise ValueError(ranked_error)

    def _expand_home_away_requirements(self, review, scope: str):
        expanded = []
        for requirement in review.requirements:
            args = (capability_arguments_for(requirement, "game_logs")
                    if "game_logs" in requirement.capability_options else {})
            if ("game_logs" in requirement.capability_options
                    and "home" in scope and "away" in scope
                    and args.get("home_away") not in {"home", "away"}):
                for split in ("home", "away"):
                    expanded.append(update_capability_arguments(
                        requirement.model_copy(update={
                            "id": f"{requirement.id}_{split}",
                            "description": f"{split.title()} split: {requirement.description}"}),
                        "game_logs", {"home_away": split}))
            else:
                expanded.append(requirement)
        return review.model_copy(update={"requirements": expanded})

    def _close_requirement_options(self, requirement):
        if requirement.capability_argument_sets:
            return requirement
        from v2.runtime.subsumption import capability_subsumes
        return requirement.model_copy(update={"capability_options": list(dict.fromkeys([
            *requirement.capability_options,
            *(["web_fetch"] if "web_search" in requirement.capability_options else []),
            *(candidate for candidate in self._catalog
              if any(capability_subsumes(candidate, narrower)
                     for narrower in requirement.capability_options)),
            *(["player_report"] if "game_logs" in requirement.capability_options
              and requirement.capability_arguments.get("playoffs") is False
              and "player" in requirement.capability_arguments
              and "player_report" in self._catalog else []),
        ]))})

    async def _review_requirements(
        self, request: str, task: TaskSpec,
    ) -> RequirementReview:
        payload = {
            "question": request,
            "draft_task": task.model_dump(mode="json"),
            "capability_catalog": self._wire_catalog,
            "skill_catalog": self._skills.catalog(),
        }
        ranked_arguments: dict[str, dict[str, Any]] = {}

        def _collect_review_metadata(wire: RequirementReviewWire) -> dict | None:
            nonlocal ranked_arguments
            base = self._collect_review_drops(wire)
            drops = base["null_as_omitted_drops"] if base else []
            ranked_arguments = self._decode_review_ranked_arguments(wire)
            decisions = self._ranked_review_typed_decisions(task, ranked_arguments)
            carried_rows = [
                {"route": "requirement_review", "capability_id": "team_ratings",
                 "key": key, "rule": "carried-from-intake"}
                for decision in decisions.values()
                for key in decision["carries"]]
            conflict_rows = [
                row for decision in decisions.values()
                for row in decision["conflict_rows"]]
            metadata = {"null_as_omitted_drops": drops}
            if carried_rows:
                metadata["carried_from_intake"] = carried_rows
            if conflict_rows:
                metadata["ranked_argument_conflicts"] = conflict_rows
            return metadata if (drops or carried_rows or conflict_rows) else None

        wire = await self._generate_as(
            prompt_name="requirement_review_v3", route="requirement_review",
            schema=RequirementReviewWire, payload=payload,
            decode=_collect_review_metadata,
        )
        wire = self._apply_ranked_carries_to_wire(task, wire, ranked_arguments)
        self._validate_requirement_wire(wire)
        requirements = []
        for item in (wire.requirements or []):
            sets = [{"capability_id": option.capability_id,
                     "arguments": provider_to_source(option.arguments, "requirement",
                        route="requirement_review", capability_id=option.capability_id,
                        argument_schema=self._review_argument_schema(option.capability_id))}
                    for option in item.capability_argument_sets]
            maps = [dict(option["arguments"]) for option in sets]
            shared = maps[0] if maps and all(value == maps[0] for value in maps) else {}
            requirements.append({"id": item.id, "description": item.description,
                "capability_options": item.capability_options,
                "capability_argument_sets": sets,
                "capability_arguments": shared,
                "metric_ids": item.metric_ids or [],
                "requested_outputs": item.requested_outputs or []})
        review = RequirementReview.model_validate({
            "requirements": requirements,
            "calculation_requirements": [{**item.model_dump(),
                "metric_ids": item.metric_ids or [],
                "requested_outputs": item.requested_outputs or []}
                for item in (wire.calculation_requirements or [])],
            "missing_subquestions": wire.missing_subquestions or [],
            "missing_skills": wire.missing_skills or []})
        review, _carried_rows, conflict_rows = (
            self._reconcile_typed_ranked_arguments(task, review))
        unknown_evidence = sorted(
            {capability for requirement in review.requirements
             for capability in requirement.capability_options}
            - self._catalog.keys()
        )
        if unknown_evidence:
            raise ValueError(
                f"requirement review selected unknown capabilities: {unknown_evidence}"
            )
        scope = " ".join([request, task.goal, task.deliverable, *task.subquestions]).casefold()
        review = self._expand_home_away_requirements(review, scope)
        requirements = [self._close_requirement_options(requirement)
                        for requirement in review.requirements]
        return review.model_copy(update={
            "requirements": requirements,
            "ranked_argument_conflicts": conflict_rows})

class PlannerArgumentError(ValueError):

    def __init__(self, message: str, *, node_id: str, missing_required: list[str]) -> None:
        super().__init__(message)
        self.node_id = node_id
        self.missing_required = missing_required

class PlanOutputError(ValueError):

    def __init__(self, message: str, *, output_id: str, capability: str,
                 vocabulary: list[str], node_id: str | None = None,
                 requirement_id: str | None = None) -> None:
        super().__init__(message)
        self.output_id = output_id
        self.capability = capability
        self.vocabulary = list(vocabulary)
        self.node_id = node_id
        self.requirement_id = requirement_id

def servable_output_names(capability_id: str) -> list[str]:
    from .capabilities import CAPABILITIES, servable_names_for

    spec = CAPABILITIES.get(capability_id)
    if spec is None:
        return []
    return servable_names_for(spec)

def _is_subject_identity_output(output_id: str) -> bool:
    squashed = "".join(
        character for character in str(output_id).upper() if character.isalnum())
    return squashed.endswith("NAME") or squashed.endswith("ID")

def _validate_plan_output_vocabulary(task, plan) -> None:
    requirements = {item.id: item for item in task.requirements}
    _check_plan_node_outputs(task, plan, requirements)
    _check_plan_task_outputs(task, plan)


def _check_plan_node_outputs(task, plan, requirements) -> None:
    from .capabilities import CAPABILITIES, resolve_metric_column

    for node in plan.nodes:
        selected = [name for name in node.capability_hints if name in CAPABILITIES]
        if len(selected) != 1:
            continue
        capability = selected[0]
        spec = CAPABILITIES.get(capability)
        if spec is None or spec.open_vocabulary:
            continue
        if not servable_output_names(capability):
            continue
        for requirement_id in node.covers_requirement_ids or []:
            requirement = requirements.get(requirement_id)
            if requirement is None:
                continue
            if capability not in requirement.capability_options:
                continue
            for output_id in requirement.requested_outputs or []:
                if _is_subject_identity_output(output_id):
                    continue
                if resolve_metric_column(spec, output_id) is None:
                    vocabulary = servable_output_names(capability)
                    raise PlanOutputError(
                        f"PLAN_OUTPUT_UNRESOLVABLE: requested output {output_id!r} "
                        f"for requirement {requirement_id!r} does not resolve "
                        f"against capability {capability!r} "
                        f"through resolve_metric_column; servable outputs: "
                        f"{', '.join(vocabulary)}; "
                        f"repair by choosing requested outputs only from "
                        f"{', '.join(vocabulary)}",
                        output_id=str(output_id), capability=capability,
                        vocabulary=vocabulary, node_id=node.id,
                        requirement_id=requirement_id)


def _check_plan_task_outputs(task, plan) -> None:
    from .capabilities import CAPABILITIES, resolve_metric_column

    task_outputs = list(task.requested_outputs or [])
    if task_outputs and plan.nodes:
        union: set[str] = set()
        for node in plan.nodes:
            selected = [name for name in node.capability_hints if name in CAPABILITIES]
            if len(selected) != 1:
                continue
            union.update(servable_output_names(selected[0]))
        if union:
            planned = {
                hint for node in plan.nodes for hint in node.capability_hints
                if hint in CAPABILITIES and (servable_output_names(hint)
                                             or CAPABILITIES[hint].open_vocabulary)
            }
            for output_id in task_outputs:
                _check_task_output_resolvable(output_id, union, planned)


def _check_task_output_resolvable(output_id, union, planned) -> None:
    from .capabilities import CAPABILITIES, resolve_metric_column
    if _is_subject_identity_output(output_id):
        return
    if not any(
        resolve_metric_column(CAPABILITIES[name], output_id) is not None
        for name in planned
    ):
        vocabulary = sorted(union)
        raise PlanOutputError(
            f"PLAN_OUTPUT_UNRESOLVABLE: task requested output "
            f"{output_id!r} does not resolve against any planned "
            f"capability through resolve_metric_column; servable "
            f"outputs: {', '.join(vocabulary)}; repair by choosing "
            f"requested outputs only from {', '.join(vocabulary)}",
            output_id=str(output_id), capability="plan",
            vocabulary=vocabulary)


def _team_subject_abbreviation(entity) -> str | None:
    from v2.contracts import canonical_entity_id
    canonical = canonical_entity_id(
        entity.type, entity.id, entity.display_name)
    try:
        from nba_api.stats.static import teams as static_teams
        entries = static_teams.get_teams()
    except Exception:
        return None
    for entry in entries:
        if str(entry.get("id")) == canonical:
            abbreviation = str(entry.get("abbreviation") or "")
            return abbreviation or None
    lowered = canonical.casefold()
    for entry in entries:
        if lowered and lowered == str(
                entry.get("abbreviation") or "").casefold():
            return str(entry.get("abbreviation"))
    return None

class ModelPlanner(ModelStage):
    prompt_name = "planner_v3"
    route = "planner"
    schema = PlannerOutputWire

    def _planner_argument_schema(self, capability: str) -> dict:
        entry = self._catalog.get(capability)
        if not isinstance(entry, Mapping): raise ValueError("planner selected unknown capability")
        schema = dict(entry.get("arguments", {}))
        injected = set(entry.get("dependent_entity_arguments", {}))
        if injected and isinstance(schema.get("required"), list):
            schema["required"] = [name for name in schema["required"] if name not in injected]
        return schema

    def _collect_planner_drops(self, wire: PlannerOutputWire) -> dict | None:
        drops: list[dict] = []
        for node in (wire.nodes or []):
            entry = self._catalog.get(node.capability)
            if not isinstance(entry, Mapping): continue
            provider_to_source(node.arguments, "planner",
                route="planner", capability_id=node.capability,
                argument_schema=self._planner_argument_schema(node.capability),
                drops=drops)
        return {"null_as_omitted_drops": drops} if drops else None

    def _check_ranked_requirement_agreement(
        self, node, arguments: Mapping[str, Any],
        requirements: Mapping[str, Any],
    ) -> None:
        if node.capability not in METRIC_AGREEMENT_CAPABILITIES:
            return
        served = served_capability_metrics(node.capability)
        for requirement_id in node.covers_requirement_ids or []:
            requirement = requirements.get(requirement_id)
            if requirement is None:
                continue
            if node.capability in requirement.capability_options:
                expected = capability_arguments_for(requirement, node.capability)
            else:
                expected = {}
            requested = str(expected.get("requested_metric", "") or "").upper()
            metrics = [requested] if requested else []
            metrics.extend(
                str(item).upper() for item in (requirement.metric_ids or []))
            if node.capability not in requirement.capability_options:
                detail = (f": requested metric {metrics[0]!r} is not coverable "
                          f"by {node.capability}" if metrics else "")
                raise PlannerArgumentError(
                    f"METRIC_IDENTITY_GAP: planner {node.capability} node "
                    f"'{node.id}' cannot cover requirement '{requirement_id}' "
                    f"which disallows {node.capability}{detail}",
                    node_id=node.id, missing_required=[])
            typed = [m for m in metrics if m]
            node_metric = str(arguments.get("requested_metric", "") or "").upper()
            if typed and node_metric and node_metric not in typed:
                raise PlannerArgumentError(
                    f"RANKED_ARGUMENT_CONFLICT: planner {node.capability} node "
                    f"'{node.id}' requested_metric={node_metric!r} is not in the "
                    f"covered requirement's typed metric_ids {typed}",
                    node_id=node.id, missing_required=[])
            if not expected and not typed:
                for key in ("requested_metric", "ranking_direction"):
                    node_value = arguments.get(key, "")
                    expected_value = expected.get(key, "")
                    if node_value != expected_value:
                        raise PlannerArgumentError(
                            f"RANKED_ARGUMENT_CONFLICT: planner {node.capability} node "
                            f"'{node.id}' {key}={node_value!r} does not match "
                            f"covered requirement '{requirement_id}' {key}={expected_value!r}",
                            node_id=node.id, missing_required=[])
            for metric in metrics:
                if metric not in served:
                    raise PlannerArgumentError(
                        f"METRIC_IDENTITY_GAP: planner {node.capability} node "
                        f"'{node.id}' cannot cover requirement '{requirement_id}': "
                        f"requested metric {metric!r} is not served "
                        f"by {node.capability}",
                        node_id=node.id, missing_required=[])

    def _dependent_source_candidate(
        self, task: TaskSpec | None,
        requirements: Mapping[str, Any],
        node: Any, capability: str,
        argument: str, entity_type: str,
    ) -> str | None:
        for requirement_id in node.covers_requirement_ids or []:
            requirement = requirements.get(requirement_id)
            if requirement is None:
                continue
            if capability not in requirement.capability_options:
                continue
            value = capability_arguments_for(requirement, capability).get(argument)
            if value is not None and not (isinstance(value, str) and not value.strip()):
                return value if isinstance(value, str) else str(value)
        if task is not None:
            matches = [entity for entity in task.entities
                       if entity.type == entity_type]
            if len(matches) == 1:
                candidate = matches[0].display_name or matches[0].id
                if candidate is not None and str(candidate).strip():
                    return str(candidate)
        return None

    async def _generate_plan(self, payload, task: TaskSpec | None = None):
        wire = await self._generate(payload, decode=self._collect_planner_drops)
        requirements = {item.id: item for item in task.requirements} if task is not None else {}
        decoded = self._decode_planner_nodes(wire, requirements)
        resolvers, depends_extra = self._collect_entity_resolvers(decoded, task, requirements)
        validated = Plan.model_validate({"nodes": [
            *resolvers,
            *[{
                "id": node.id, "description": node.description,
                "depends_on": list(dict.fromkeys([*(node.depends_on or []), *depends_extra.get(node.id, [])])),
            "capability_hints": [node.capability],
            "covers_requirement_ids": node.covers_requirement_ids or [],
            "arguments": dict(arguments), "max_attempts": node.max_attempts or 1,
            "status": node.status or "pending"} for node, arguments, _ in decoded]]})
        if task is not None:
            _validate_plan_output_vocabulary(task, validated)
        return validated

    def _decode_planner_nodes(self, wire, requirements):
        from jsonschema import Draft202012Validator
        decoded = []
        for node in (wire.nodes or []):
            schema = self._planner_argument_schema(node.capability)
            arguments = provider_to_source(node.arguments, "planner",
                route="planner", capability_id=node.capability,
                argument_schema=schema)
            errors = list(Draft202012Validator(schema).iter_errors(dict(arguments)))
            if errors:
                missing = sorted(
                    name for error in errors if error.validator == "required"
                    for name in error.validator_value if name not in arguments)
                raise PlannerArgumentError(
                    f"invalid {node.capability} planner arguments: {errors[0].message}",
                    node_id=node.id, missing_required=missing)
            ranked_error = ranked_team_arguments_error(node.capability, arguments)
            if ranked_error:
                raise PlannerArgumentError(
                    f"invalid {node.capability} planner arguments: {ranked_error}",
                    node_id=node.id,
                    missing_required=(["ranking_direction"]
                        if ranked_error.startswith("RANKED_DIRECTION_UNSPECIFIED")
                        else []))
            self._check_ranked_requirement_agreement(node, arguments, requirements)
            entry = self._catalog.get(node.capability)
            declarations = entry.get("dependent_entity_arguments", {}) if isinstance(entry, Mapping) else {}
            values = dict(arguments.as_dict() if hasattr(arguments, "as_dict") else arguments)
            stripped: dict[str, Any] = {}
            for key in set(declarations) & set(values):
                stripped[key] = values.pop(key)
            decoded.append((node, values, stripped))
        return decoded

    def _collect_entity_resolvers(self, decoded, task, requirements):
        resolvers: list[dict[str, Any]] = []
        existing = {node.id for node, _, _ in decoded}
        resolver_for: dict[tuple[str, str], str] = {}
        depends_extra: dict[str, list[str]] = {}
        if "entity_resolution" not in self._catalog:
            return resolvers, depends_extra
        self._resolvers_from_stripped(decoded, existing, resolver_for, depends_extra, resolvers)
        self._resolvers_from_sources(decoded, task, requirements, existing, resolver_for, depends_extra, resolvers)
        return resolvers, depends_extra

    def _add_entity_resolver(self, entity_type, query, node_id, *, existing, resolver_for, depends_extra, resolvers, dedupe):
        fold = (str(entity_type), str(query).strip().casefold())
        resolver_id = resolver_for.get(fold)
        if resolver_id is None:
            base = f"resolve_{str(entity_type).replace('-', '_')}"
            resolver_id = base
            suffix = 2
            while resolver_id in existing:
                resolver_id = f"{base}_{suffix}"
                suffix += 1
            existing.add(resolver_id)
            resolver_for[fold] = resolver_id
            resolvers.append({
                "id": resolver_id, "description": f"Resolve {entity_type} identity for dependent tools",
                "depends_on": [], "capability_hints": ["entity_resolution"],
                "covers_requirement_ids": [],
                "arguments": {"query": query}, "max_attempts": 1,
                "status": "pending"})
        if dedupe:
            if resolver_id not in depends_extra.get(node_id, []):
                depends_extra.setdefault(node_id, []).append(resolver_id)
        else:
            depends_extra.setdefault(node_id, []).append(resolver_id)
        return resolver_id

    def _resolvers_from_stripped(self, decoded, existing, resolver_for, depends_extra, resolvers):
        for node, _, stripped in decoded:
            entry = self._catalog.get(node.capability)
            declarations = entry.get("dependent_entity_arguments", {}) if isinstance(entry, Mapping) else {}
            for key, value in stripped.items():
                if value is None or (isinstance(value, str) and not value.strip()):
                    continue
                entity_type = declarations.get(key)
                if not isinstance(entity_type, str) or not entity_type:
                    continue
                self._add_entity_resolver(entity_type, value, node.id, existing=existing,
                                          resolver_for=resolver_for, depends_extra=depends_extra,
                                          resolvers=resolvers, dedupe=False)

    def _resolvers_from_sources(self, decoded, task, requirements, existing, resolver_for, depends_extra, resolvers):
        for node, values, stripped in decoded:
            entry = self._catalog.get(node.capability)
            declarations = entry.get("dependent_entity_arguments", {}) if isinstance(entry, Mapping) else {}
            for key, entity_type in declarations.items():
                current = values.get(key)
                if current is not None and not (isinstance(current, str) and not current.strip()):
                    continue
                if not isinstance(entity_type, str) or not entity_type:
                    continue
                candidate = self._dependent_source_candidate(
                    task, requirements, node, node.capability, key, entity_type)
                if candidate is None or not candidate.strip():
                    continue
                values[key] = candidate
                self._add_entity_resolver(entity_type, candidate, node.id, existing=existing,
                                          resolver_for=resolver_for, depends_extra=depends_extra,
                                          resolvers=resolvers, dedupe=True)

    def __init__(self, *args: Any, capability_catalog: Mapping[str, str], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._catalog = dict(capability_catalog)
        self._wire_catalog = catalog_for_wire(self._catalog)

    def _catalog_for(self, task: TaskSpec) -> dict:
        from v2.runtime.assembly import declared_schema_for

        relevant = set(task.required_evidence)
        for requirement in task.requirements:
            relevant.update(requirement.capability_options)
        trimmed = {}
        for capability_id, entry in self._wire_catalog.items():
            if capability_id not in relevant or not isinstance(entry, Mapping):
                trimmed[capability_id] = entry
                continue
            schema = declared_schema_for(capability_id)
            trimmed[capability_id] = (
                {**entry, "declared_schema": schema}
                if schema is not None else entry)
        return trimmed

    async def plan(self, task: TaskSpec, failure_context: dict | None = None) -> Plan:
        payload = {
            "task": task.model_dump(mode="json"),
            "capability_catalog": self._catalog_for(task),
            "skills": self._skills.activate(task.skills),
        }
        if failure_context is not None:
            payload["failure_context"] = failure_context
        try:
            plan = await self._generate_plan(payload, task)
        except PlannerArgumentError as exc:
            if not exc.missing_required:
                raise
            plan = await self._generate_plan({
                **payload,
                "coverage_feedback": {
                    "missing_required_arguments": {exc.node_id: exc.missing_required},
                    "instruction": "Return a complete replacement plan.",
                },
            }, task)
        plan = self._normalize_plan(
            task, self._normalize_requirement_coverage(task, plan))
        feedback = self._coverage_feedback(task, plan)
        if not feedback:
            return plan
        replacement = await self._generate_plan({
            **payload,
            "coverage_feedback": {
                **feedback, "instruction": "Return a complete replacement plan.",
            },
        }, task)
        replacement = self._normalize_plan(
            task, self._normalize_requirement_coverage(task, replacement))
        remaining = self._coverage_feedback(task, replacement)
        if remaining:
            original_remaining = self._coverage_feedback(task, plan)
            if not original_remaining:
                return plan
            def issue_count(feedback: Mapping[str, Any]) -> int:
                return sum(
                    len(value) if isinstance(value, (list, dict)) else 1
                    for value in feedback.values()
                )
            return replacement if issue_count(remaining) <= issue_count(original_remaining) else plan
        return replacement

    def _normalize_plan(self, task: TaskSpec, plan: Plan) -> Plan:
        requirements = {item.id: item for item in task.requirements}
        if "entity_resolution" in self._catalog:
            plan = self._inject_entity_resolvers(task, plan, requirements)
        plan = self._join_resolver_queries(plan)
        plan = self._downgrade_game_logs(plan, requirements)
        plan = self._absorb_subsumed_nodes(plan, requirements)
        kept = self._dedupe_plan_nodes(plan)
        kept = self._abbreviate_team_argument(task, kept)
        return plan.model_copy(update={"nodes": kept})

    def _inject_entity_resolvers(self, task, plan, requirements):
        existing = {node.id for node in plan.nodes}
        added = []
        normalized_nodes = []
        resolver_for: dict[tuple[str, str], str] = {}
        for node in plan.nodes:
            normalized_nodes.append(self._attach_resolvers_to_node(
                task, plan, node, requirements, existing, resolver_for, added))
        if added:
            plan = plan.model_copy(update={"nodes": [*added, *normalized_nodes]})
        return plan

    def _attach_resolvers_to_node(self, task, plan, node, requirements, existing, resolver_for, added):
        selected_name = next((name for name in node.capability_hints
                              if name in self._catalog), None)
        entry = self._catalog.get(selected_name, {}) if selected_name else {}
        declarations = (entry.get("dependent_entity_arguments", {})
                        if isinstance(entry, Mapping) else {})
        dependencies = list(node.depends_on)
        updated_arguments: dict[str, Any] | None = None
        for argument, entity_type in declarations.items():
            value = (updated_arguments.get(argument, node.arguments.get(argument))
                     if updated_arguments is not None else node.arguments.get(argument))
            if value is None or (isinstance(value, str) and not value.strip()):
                candidate = self._dependent_source_candidate(
                    task, requirements, node,
                    selected_name or "", argument, entity_type)
                if candidate is not None and candidate.strip():
                    if updated_arguments is None:
                        updated_arguments = dict(node.arguments)
                    updated_arguments[argument] = candidate
                    value = candidate
                else:
                    continue
            if self._node_has_resolver(plan, existing, dependencies):
                continue
            key = (str(entity_type), str(value).strip().casefold())
            resolver_id = resolver_for.get(key)
            if resolver_id is None:
                base = f"resolve_{str(entity_type).replace('-', '_')}"
                resolver_id = base
                suffix = 2
                while resolver_id in existing:
                    resolver_id = f"{base}_{suffix}"
                    suffix += 1
                existing.add(resolver_id)
                resolver_for[key] = resolver_id
                added.append(PlanNode(
                    id=resolver_id,
                    description=f"Resolve {entity_type} identity for dependent tools",
                    capability_hints=["entity_resolution"],
                    arguments={"query": value},
                ))
            dependencies.append(resolver_id)
        update: dict[str, Any] = {
            "depends_on": list(dict.fromkeys(dependencies))}
        if updated_arguments is not None:
            update["arguments"] = updated_arguments
        return node.model_copy(update=update)

    def _node_has_resolver(self, plan, existing, dependencies) -> bool:
        return any(
            parent in existing and any(
                candidate.id == parent
                and "entity_resolution" in candidate.capability_hints
                for candidate in plan.nodes)
            for parent in dependencies)

    def _join_resolver_queries(self, plan):
        return plan.model_copy(update={"nodes": [
            node.model_copy(update={
                "arguments": {**node.arguments, "query": ", ".join(
                    str(value) for value in node.arguments["query"])}
            })
            if ("entity_resolution" in node.capability_hints
                and isinstance(node.arguments.get("query"), list))
            else node
            for node in plan.nodes
        ]})

    def _downgrade_game_logs(self, plan, requirements):
        return plan.model_copy(update={"nodes": [
            node.model_copy(update={
                "capability_hints": ["player_report"],
                "arguments": {
                    key: value for key, value in node.arguments.items()
                    if key in {"player", "season"}
                },
            })
            if ("game_logs" in node.capability_hints
                and node.arguments.get("playoffs") is False
                and node.arguments.get("player") is not None
                and "player_report" in self._catalog
                and any(
                    requirement_id in requirements
                    and "player_report" in requirements[requirement_id].capability_options
                    for requirement_id in node.covers_requirement_ids
                ))
            else node
            for node in plan.nodes
        ]})

    def _absorb_subsumed_nodes(self, plan, requirements):
        subsumed = self._find_subsumed_nodes(plan, requirements)
        if not subsumed:
            return plan
        kept_nodes = []
        for node in plan.nodes:
            if node.id in subsumed:
                continue
            absorbed = [
                item for item in plan.nodes
                if subsumed.get(item.id) == node.id
            ]
            kept_nodes.append(node.model_copy(update={
                "covers_requirement_ids": list(dict.fromkeys([
                    *node.covers_requirement_ids,
                    *(requirement_id for item in absorbed
                      for requirement_id in item.covers_requirement_ids),
                ])),
                "depends_on": list(dict.fromkeys(
                    subsumed.get(parent, parent) for parent in node.depends_on
                    if subsumed.get(parent, parent) != node.id
                )),
            }))
        return plan.model_copy(update={"nodes": [
            node.model_copy(update={
                "depends_on": list(dict.fromkeys(
                    subsumed.get(parent, parent) for parent in node.depends_on
                    if subsumed.get(parent, parent) != node.id
                ))
            }) for node in kept_nodes
        ]})

    def _find_subsumed_nodes(self, plan, requirements):
        from v2.runtime.subsumption import (
            arguments_share_subject, capability_subsumes,
        )
        selected = {
            node.id: next((name for name in node.capability_hints
                           if name in self._catalog), None)
            for node in plan.nodes
        }
        subsumed: dict[str, str] = {}
        for narrower in plan.nodes:
            narrow_name = selected[narrower.id]
            if narrow_name is None:
                continue
            for broader in plan.nodes:
                broad_name = selected[broader.id]
                if (broader.id == narrower.id or broad_name is None
                        or not capability_subsumes(broad_name, narrow_name)
                        or not arguments_share_subject(
                            broader.arguments, narrower.arguments)):
                    continue
                transferable = all(
                    requirement_id in requirements
                    and broad_name in requirements[requirement_id].capability_options
                    for requirement_id in narrower.covers_requirement_ids
                )
                if transferable:
                    subsumed[narrower.id] = broader.id
                    break
        return subsumed

    def _dedupe_plan_nodes(self, plan):
        import json
        canonical: dict[tuple[str, str, tuple[str, ...]], PlanNode] = {}
        aliases: dict[str, str] = {}
        kept: list[PlanNode] = []
        for node in plan.nodes:
            selected = tuple(sorted(
                name for name in node.capability_hints if name in self._catalog))
            dependencies = tuple(aliases.get(parent, parent)
                                 for parent in node.depends_on)
            key = ("|".join(selected), json.dumps(
                node.arguments, sort_keys=True, separators=(",", ":"),
                default=str), dependencies)
            previous = canonical.get(key)
            if previous is None:
                normalized = node.model_copy(update={"depends_on": list(dependencies)})
                canonical[key] = normalized
                kept.append(normalized)
                continue
            aliases[node.id] = previous.id
            merged = list(dict.fromkeys([
                *previous.covers_requirement_ids, *node.covers_requirement_ids]))
            replacement = previous.model_copy(
                update={"covers_requirement_ids": merged})
            canonical[key] = replacement
            kept[kept.index(previous)] = replacement
        if aliases:
            kept = [node.model_copy(update={
                "depends_on": list(dict.fromkeys(
                    aliases.get(parent, parent) for parent in node.depends_on))
            }) for node in kept]
        return kept

    def _abbreviate_team_argument(self, task, kept):
        teams = [entity for entity in task.entities if entity.type == "team"]
        if len(teams) != 1:
            return kept
        abbreviation = _team_subject_abbreviation(teams[0])
        if abbreviation is None:
            return kept
        return [node.model_copy(update={"arguments": {
            **node.arguments, "team": abbreviation}})
            if (next((name for name in node.capability_hints
                      if name in self._catalog), None) == "team_ratings"
                and "team" not in node.arguments)
            else node for node in kept]

    @staticmethod
    def _arguments_cover(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
        for key, wanted in expected.items():
            if key not in actual:
                return False
            got = actual[key]
            if isinstance(wanted, Mapping):
                if not isinstance(got, Mapping) or not ModelPlanner._arguments_cover(wanted, got):
                    return False
            elif isinstance(wanted, list):
                if got not in wanted:
                    return False
            elif isinstance(wanted, str) and isinstance(got, str):
                if wanted.strip().casefold() != got.strip().casefold():
                    return False
            elif wanted != got:
                return False
        return True

    def _normalize_requirement_coverage(
        self, task: TaskSpec, plan: Plan,
    ) -> Plan:
        requirements = {item.id: item for item in task.requirements}
        nodes = []
        for node in plan.nodes:
            selected = [name for name in node.capability_hints if name in self._catalog]
            capability = selected[0] if len(selected) == 1 else None
            valid = [
                requirement_id for requirement_id in node.covers_requirement_ids
                if requirement_id in requirements and capability is not None
                and capability in requirements[requirement_id].capability_options
                and self._arguments_cover(
                    capability_arguments_for(requirements[requirement_id], capability),
                    node.arguments)
            ]
            nodes.append(node.model_copy(update={"covers_requirement_ids": valid}))
        return plan.model_copy(update={"nodes": nodes})

    def _missing_required_arguments(
        self, node: PlanNode, plan: Plan | None = None,
    ) -> list[str]:
        selected = [name for name in node.capability_hints if name in self._catalog]
        if len(selected) != 1:
            return []
        catalog_entry = self._catalog.get(selected[0])
        if not isinstance(catalog_entry, Mapping):
            return []
        schema = catalog_entry.get("arguments")
        if not isinstance(schema, Mapping):
            return []
        required = schema.get("required", [])
        if not isinstance(required, list):
            return []
        declarations = catalog_entry.get("dependent_entity_arguments", {})
        return sorted(
            key for key in required
            if isinstance(key, str) and key not in node.arguments
            and not (plan is not None and node.depends_on
                     and isinstance(declarations, Mapping)
                     and key in declarations)
        )

    def _coverage_feedback(self, task: TaskSpec, plan: Plan) -> dict[str, Any]:
        invalid_arguments = {
            node.id: self._missing_required_arguments(node, plan)
            for node in plan.nodes
            if self._missing_required_arguments(node, plan)
        }
        valid_nodes = [
            node for node in plan.nodes if node.id not in invalid_arguments
        ]
        selected = {
            name for node in valid_nodes for name in node.capability_hints
            if name in self._catalog
        }
        missing_evidence = sorted(set(task.required_evidence) - selected)
        requirements = {item.id: item for item in task.requirements}
        covered: set[str] = set()
        mismatched: list[str] = []
        for node in valid_nodes:
            node_capabilities = set(node.capability_hints) & self._catalog.keys()
            for requirement_id in node.covers_requirement_ids:
                requirement = requirements.get(requirement_id)
                if requirement is None:
                    mismatched.append(f"unknown:{requirement_id}")
                elif node_capabilities & set(requirement.capability_options):
                    covered.add(requirement_id)
                else:
                    mismatched.append(requirement_id)
        missing_requirements = sorted(requirements.keys() - covered)
        feedback: dict[str, Any] = {}
        if missing_evidence:
            feedback["missing_required_evidence"] = missing_evidence
        if missing_requirements:
            feedback["missing_requirement_ids"] = missing_requirements
        if mismatched:
            feedback["mismatched_requirement_ids"] = sorted(set(mismatched))
        if invalid_arguments:
            feedback["missing_required_arguments"] = invalid_arguments
        return feedback

_CANONICAL_CALCULATIONS = {
    "home_mean": ("home_mean", "Canonical home points-per-game mean"),
    "away_mean": ("away_mean", "Canonical away points-per-game mean"),
    "home_away_delta": ("home_away_delta", "Canonical home-minus-away points-per-game difference"),
    "ppg_margin": ("ppg_margin", "Canonical points-per-game margin"),
    "ts_margin": ("ts_margin", "Canonical true-shooting percentage-point margin"),
}

def _derive_subject_entity_type(task: TaskSpec) -> str | None:
    kinds = {entity.type for entity in task.entities}
    if len(kinds) == 1:
        kind = next(iter(kinds))
        if kind == "player" or kind == "team":
            return kind
    return None

def _align_requirement_requested_outputs(task: TaskSpec) -> TaskSpec:
    from v2.adapters.capabilities import CAPABILITIES, resolve_metric_column
    if not task.requested_outputs or not task.requirements:
        return task
    aligned = []
    for requirement in task.requirements:
        aligned.append(_align_one_requirement(requirement, task.requested_outputs))
    return task.model_copy(update={"requirements": aligned})


def _align_one_requirement(requirement, wanted_outputs):
    from v2.adapters.capabilities import CAPABILITIES, resolve_metric_column
    options = [name for name in requirement.capability_options if name in CAPABILITIES]
    if not options:
        return requirement
    existing = list(requirement.requested_outputs)
    for wanted in wanted_outputs:
        if wanted in existing:
            continue
        wanted_columns = set()
        for name in options:
            column = resolve_metric_column(CAPABILITIES[name], wanted)
            if column is not None:
                wanted_columns.add(column)
        if not wanted_columns:
            continue
        replaced = False
        for index, current in enumerate(list(existing)):
            current_columns = set()
            for name in options:
                column = resolve_metric_column(CAPABILITIES[name], current)
                if column is not None:
                    current_columns.add(column)
            if wanted_columns & current_columns:
                existing[index] = wanted
                replaced = True
                break
        if not replaced:
            if len(existing) >= 16:
                continue
            existing.append(wanted)
    if existing == list(requirement.requested_outputs):
        return requirement
    return requirement.model_copy(update={"requested_outputs": existing})

def _drop_unresolvable_requested_outputs(task: TaskSpec) -> TaskSpec:
    from v2.adapters.capabilities import CAPABILITIES, resolve_metric_column
    if not task.requirements:
        return task
    def resolvable(output_id: str, requirement) -> bool:
        if _is_subject_identity_output(output_id):
            return True
        options = [name for name in requirement.capability_options
                 if name in CAPABILITIES]
        if any(CAPABILITIES[name].open_vocabulary for name in options):
            return True
        vocabularies = [name for name in options if servable_output_names(name)]
        structural = [name for name in options if not servable_output_names(name)]
        if not vocabularies:
            return bool(structural)
        return all(
            resolve_metric_column(CAPABILITIES[name], output_id) is not None
            for name in vocabularies)
    aligned = []
    for requirement in task.requirements:
        kept = [output_id for output_id in requirement.requested_outputs
                if resolvable(output_id, requirement)]
        metrics = [output_id for output_id in requirement.metric_ids
                   if resolvable(output_id, requirement)]
        if (kept == list(requirement.requested_outputs)
                and metrics == list(requirement.metric_ids)):
            aligned.append(requirement)
            continue
        aligned.append(requirement.model_copy(update={
            "requested_outputs": kept, "metric_ids": metrics}))
    calculation_outputs = {
        output_id
        for requirement in task.calculation_requirements
        for output_id in requirement.requested_outputs}
    task_kept = [
        output_id for output_id in task.requested_outputs
        if output_id in calculation_outputs
        or _is_subject_identity_output(output_id)
        or any(resolvable(output_id, requirement) for requirement in aligned)]
    if task_kept == list(task.requested_outputs):
        return task.model_copy(update={"requirements": aligned})
    return task.model_copy(update={
        "requirements": aligned,
        "requested_outputs": task_kept,
    })

def _backfill_open_question_outputs(task: TaskSpec) -> TaskSpec:
    if task.requested_outputs or not task.requirements:
        return task
    filled = []
    union: list[str] = []
    for requirement in task.requirements:
        for output_id in requirement.requested_outputs:
            if output_id not in union:
                union.append(output_id)
        if requirement.requested_outputs:
            filled.append(requirement)
            continue
        servable = servable_output_names(requirement.capability_options[0])
        for name in requirement.capability_options[1:]:
            allowed = set(servable_output_names(name))
            servable = [item for item in servable if item in allowed]
        servable = servable[:16]
        if not servable:
            filled.append(requirement)
            continue
        filled.append(requirement.model_copy(
            update={"requested_outputs": servable}))
        union.extend(item for item in servable if item not in union)
    if not union:
        return task
    return task.model_copy(update={
        "requirements": filled,
        "requested_outputs": union[:32],
    })

def _canonicalize_calculation_requirements(task: TaskSpec) -> TaskSpec:
    from v2.contracts import CalculationRequirement
    scope = " ".join([task.goal, task.deliverable, *task.subquestions,
                      *(item.description for item in task.calculation_requirements)]).casefold()
    evidence_caps = {cap for requirement in task.requirements
                     for cap in requirement.capability_options}
    split_shape = ("home" in scope and "away" in scope
                   and ("game_logs" in evidence_caps or "scor" in scope or "average" in scope))
    pair_shape = ("player_comparison" in evidence_caps
                  or sum(entity.type == "player" for entity in task.entities) >= 2
                  or ("compare" in scope and any(token in scope for token in ("points", "scor", "true shooting"))))
    requested = []
    if split_shape:
        requested.extend(["home_mean", "away_mean"])
        if any(token in scope for token in ("difference", "minus", "margin", "gap")):
            requested.append("home_away_delta")
    elif pair_shape:
        if any(token in scope for token in ("who scores more", "by how much", "point", "ppg", "scor")):
            requested.append("ppg_margin")
        explicit_ts_delta = any(
            ("true shooting" in item.description.casefold() or "ts%" in item.description.casefold())
            and any(token in item.description.casefold() for token in ("difference", "margin", "gap"))
            for item in task.calculation_requirements)
        if "true shooting" in scope and (explicit_ts_delta or "differences" in scope):
            requested.append("ts_margin")
    if not requested:
        return task
    kinds: set[str] = set()
    unused = list(task.calculation_requirements)
    def classify(description: str) -> str | None:
        text = description.casefold()
        if ("sample size" in text or "number of games" in text or "game count" in text):
            return "observed_sample_size"
        if "home" in text and "away" not in text and any(x in text for x in ("average", "mean", "ppg")):
            return "home_mean"
        if "away" in text and "home" not in text and any(x in text for x in ("average", "mean", "ppg")):
            return "away_mean"
        if "home" in text and "away" in text and any(x in text for x in ("difference", "minus", "margin", "gap", "subtract")):
            return "home_away_delta"
        if "true shooting" in text or "ts%" in text:
            return "ts_margin"
        if any(x in text for x in ("point", "ppg", "scor")):
            return "ppg_margin"
        return None
    for requirement in list(unused):
        kind = classify(requirement.description)
        if kind == "observed_sample_size":
            unused.remove(requirement)
        elif kind in requested:
            kinds.add(kind)
            unused.remove(requirement)
    kinds.update(requested)
    normalized = [CalculationRequirement(
        id=_CANONICAL_CALCULATIONS[kind][0],
        description=_CANONICAL_CALCULATIONS[kind][1])
        for kind in requested if kind in kinds]
    normalized.extend(unused)
    return task.model_copy(update={"calculation_requirements": normalized})

class InvalidDraftCalculation(ValueError):
    def __init__(self, message: str, requirement_ids: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.requirement_ids = tuple(requirement_ids)

def _validate_draft(
    draft: DraftReport, evidence: Sequence[EvidenceEnvelope],
    task: TaskSpec | None = None,
) -> DraftReport:
    known = {item.evidence_id for item in evidence}
    unknown = sorted({evidence_id for claim in draft.claims
                      for evidence_id in claim.evidence_ids
                      if evidence_id not in known})
    if unknown:
        raise ValueError(f"draft cites unknown evidence ids: {unknown}")
    envelope_capabilities = {
        item.evidence_id: item.capability for item in evidence}
    normalized_claims = [
        claim.model_copy(update={
            "output_bindings": [_normalized_binding_domain(binding, envelope_capabilities)
                                for binding in claim.output_bindings]})
        for claim in draft.claims]
    if normalized_claims != draft.claims:
        draft = draft.model_copy(update={"claims": normalized_claims})
    from v2.domain.evidence import EvidenceIndex
    index = EvidenceIndex(evidence)
    for declared in draft.calculations:
        _recompute_draft_calculation(declared, index)
    if task is not None:
        draft = _reconcile_draft_calculation_requirements(draft, task)
    return draft


def _normalized_binding_domain(binding, envelope_capabilities):
    from v2.adapters.capabilities import CAPABILITIES
    declared = getattr(binding, "domain", None)
    capability = envelope_capabilities.get(
        getattr(binding, "evidence_id", None))
    if declared is None or capability is None:
        return binding
    spec = CAPABILITIES.get(capability)
    allowed = {capability}
    if spec is not None:
        allowed.update({spec.domain, spec.tool_name})
    if declared in allowed:
        return binding
    return binding.model_copy(update={"domain": capability})


def _recompute_draft_calculation(declared, index) -> None:
    from v2.domain.calculations import Calculation, recompute
    calculation = Calculation.model_validate({key: value for key, value in declared.model_dump().items()
                                              if key != "requirement_id"})
    try:
        recompute(calculation, index)
    except (KeyError, ValueError) as exc:
        requirement_ids = ([declared.requirement_id]
                           if declared.requirement_id is not None else [])
        raise InvalidDraftCalculation(
            f"draft calculation path is outside admitted evidence: {exc}",
            requirement_ids) from exc


def _reconcile_draft_calculation_requirements(draft, task):
    required = {item.id for item in task.calculation_requirements}
    declared = {item.requirement_id for item in draft.calculations
                if item.requirement_id is not None}
    blocked = set(draft.blocked_calculation_requirement_ids)
    unknown_declared = declared - required
    if unknown_declared:
        draft = draft.model_copy(update={
            "calculations": [
                calculation.model_copy(update={"requirement_id": None})
                if calculation.requirement_id in unknown_declared
                else calculation
                for calculation in draft.calculations
            ],
        })
        declared -= unknown_declared
    blocked &= required
    if blocked != set(draft.blocked_calculation_requirement_ids):
        draft = draft.model_copy(update={
            "blocked_calculation_requirement_ids": sorted(blocked),
        })
    missing = required - declared - blocked
    if missing:
        raise ValueError(f"draft omits required calculations without a blocking gap: {sorted(missing)}")
    return draft

def _deterministic_game_log_draft(
    task: TaskSpec, evidence: Sequence[EvidenceEnvelope],
) -> DraftReport | None:
    from decimal import Decimal
    logs = [item for item in evidence
            if item.capability == "game_logs" and isinstance(item.rows, Mapping)]
    home = next((item for item in logs if item.rows.get("filters") == "home games"), None)
    away = next((item for item in logs if item.rows.get("filters") == "away games"), None)
    if not (home and away and task.calculation_requirements):
        return None
    try:
        home_avg = Decimal(str(home.rows["average_pts"]))
        away_avg = Decimal(str(away.rows["average_pts"]))
        home_n = int(home.rows["total"]); away_n = int(away.rows["total"])
    except (KeyError, TypeError, ValueError):
        return None
    home_ids, away_ids, delta_ids, unknown_ids = [], [], [], []
    descriptions = {value[1]: kind for kind, value in _CANONICAL_CALCULATIONS.items()}
    for requirement in task.calculation_requirements:
        kind = descriptions.get(requirement.description)
        if kind == "home_mean": home_ids.append(requirement.id)
        elif kind == "away_mean": away_ids.append(requirement.id)
        elif kind == "home_away_delta": delta_ids.append(requirement.id)
        else: unknown_ids.append(requirement.id)
    if not (home_ids or away_ids or delta_ids):
        return None
    delta = home_avg - away_avg
    player = home.rows.get("player") or away.rows.get("player") or "The player"
    season = home.season or away.season or "the selected season"
    def one(value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.1'))}"
    calculations, claims = [], []
    def add_mean(label, item, value, count, requirement_ids):
        ids = requirement_ids or [None]
        for index, requirement_id in enumerate(ids):
            calculation_id = f"{label}_mean_pts" + (f"_{index + 1}" if index else "")
            calculations.append({"calculation_id":calculation_id,
                "requirement_id":requirement_id, "operation":"mean",
                "inputs":[{"evidence_id":item.evidence_id,"path":"rows.matches[].pts"}],
                "result":str(value), "unit":"points_per_game"})
            if index == 0:
                claims.append(Claim(
                    text=f"{player} averaged {one(value)} points per game in {count} {label} games in {season}.",
                    kind="derived", evidence_ids=[item.evidence_id], calculation_id=calculation_id))
    add_mean("home", home, home_avg, home_n, home_ids)
    add_mean("away", away, away_avg, away_n, away_ids)
    for index, requirement_id in enumerate(delta_ids):
        calculation_id = "home_minus_away" + (f"_{index + 1}" if index else "")
        calculations.append({"calculation_id":calculation_id,
            "requirement_id":requirement_id, "operation":"subtract",
            "inputs":[{"evidence_id":home.evidence_id,"path":"rows.average_pts"},
                      {"evidence_id":away.evidence_id,"path":"rows.average_pts"}],
            "result":str(delta), "unit":"points_per_game"})
        if index == 0:
            claims.append(Claim(
                text=f"The home-minus-away scoring difference was {one(delta)} points per game.",
                kind="derived", evidence_ids=[home.evidence_id, away.evidence_id],
                calculation_id=calculation_id))
    return DraftReport(sections=["Home and away scoring"], claims=claims,
        calculations=calculations,
        blocked_calculation_requirement_ids=unknown_ids,
        gaps=(["Some requested calculations could not be mapped to the admitted split evidence."]
              if unknown_ids else []))

def _deterministic_player_comparison_draft(
    task: TaskSpec, evidence: Sequence[EvidenceEnvelope],
) -> DraftReport | None:
    from decimal import Decimal
    item = next((ev for ev in evidence
                 if ev.capability == "player_comparison"
                 and isinstance(ev.rows, Mapping)), None)
    if item is None or not task.calculation_requirements:
        return None
    descriptions = {value[1]: kind for kind, value in _CANONICAL_CALCULATIONS.items()}
    ppg_ids, ts_ids, leader_ids, unknown_ids = [], [], [], []
    for requirement in task.calculation_requirements:
        kind = descriptions.get(requirement.description)
        if kind == "ppg_margin": ppg_ids.append(requirement.id)
        elif kind == "ts_margin": ts_ids.append(requirement.id)
        else: unknown_ids.append(requirement.id)
    if not (ppg_ids or ts_ids or leader_ids):
        return None
    try:
        a = item.rows["a"]; b = item.rows["b"]
        a_ppg, b_ppg = Decimal(str(a["ppg"])), Decimal(str(b["ppg"]))
    except (KeyError, TypeError, ValueError):
        return None
    shooting = [ev for ev in evidence if ev.capability == "shooting_efficiency"
                and isinstance(ev.rows, Mapping) and ev.rows.get("PLAYER_NAME")
                and ev.rows.get("TS_PCT") is not None]
    a_name, b_name = _comparison_display_name(a.get("name"), task, shooting), _comparison_display_name(b.get("name"), task, shooting)
    high_name, high_ppg, high_path = ((a_name, a_ppg, "rows.a.ppg")
                                      if a_ppg >= b_ppg else (b_name, b_ppg, "rows.b.ppg"))
    low_name, low_ppg, low_path = ((b_name, b_ppg, "rows.b.ppg")
                                   if a_ppg >= b_ppg else (a_name, a_ppg, "rows.a.ppg"))
    calculations = []
    claims = [
        Claim(text=f"{a_name} averaged {a_ppg} points per game in {item.season or 'the selected season'}.",
              kind="observed", evidence_ids=[item.evidence_id]),
        Claim(text=f"{b_name} averaged {b_ppg} points per game in {item.season or 'the selected season'}.",
              kind="observed", evidence_ids=[item.evidence_id]),
    ]
    _leader_rank_block(calculations, claims, leader_ids, item, high_path, low_path, high_name, low_name)
    if ppg_ids:
        claims.append(Claim(text=f"{high_name} scored more points per game than {low_name}.",
                            kind="observed", evidence_ids=[item.evidence_id]))
    _ppg_margin_block(calculations, claims, ppg_ids, item, high_path, low_path, high_ppg, low_ppg, high_name, low_name)
    by_name = {str(ev.rows["PLAYER_NAME"]): ev for ev in shooting}
    matched = [(name, next((ev for candidate, ev in by_name.items()
                            if _comparison_display_name(candidate, task, shooting) == name), None))
               for name in (a_name, b_name)]
    def percent_value(raw: Any) -> Decimal:
        value = Decimal(str(raw))
        return value * 100 if abs(value) <= 1 else value
    for name, ev in matched:
        if ev is not None:
            value = percent_value(ev.rows["TS_PCT"]).normalize()
            claims.append(Claim(text=f"{name} had a {value}% true shooting percentage.",
                                kind="observed", evidence_ids=[ev.evidence_id]))
    if len(matched) == 2 and all(ev is not None for _, ev in matched):
        _ts_margin_block(calculations, claims, ts_ids, matched, percent_value)
    elif ts_ids:
        unknown_ids.extend(ts_ids)
    return DraftReport(sections=["Player comparison"], claims=claims,
        calculations=calculations, blocked_calculation_requirement_ids=unknown_ids,
        gaps=(["Some requested calculations could not be mapped to admitted comparison evidence."]
              if unknown_ids else []))


def _comparison_display_name(raw, task, shooting) -> str:
    raw_text = str(raw)
    key = raw_text.casefold().replace("_", " ").replace("č", "c").replace("ć", "c")
    candidates = [entity.display_name for entity in task.entities]
    candidates += [str(ev.rows["PLAYER_NAME"]) for ev in shooting]
    return next((name for name in candidates
                 if name.casefold().replace("č", "c").replace("ć", "c") == key), raw_text)


def _leader_rank_block(calculations, claims, leader_ids, item, high_path, low_path, high_name, low_name) -> None:
    for index, rid in enumerate(leader_ids):
        cid = "ppg_leader_rank" + (f"_{index + 1}" if index else "")
        calculations.append({"calculation_id":cid, "requirement_id":rid,
            "operation":"rank_desc", "inputs":[
                {"evidence_id":item.evidence_id,"path":high_path},
                {"evidence_id":item.evidence_id,"path":low_path}],
            "result":"1", "unit":"rank", "subject_input":0})
        if index == 0:
            claims.append(Claim(text=f"{high_name} scored more points per game than {low_name}.",
                kind="derived", evidence_ids=[item.evidence_id], calculation_id=cid))


def _ppg_margin_block(calculations, claims, ppg_ids, item, high_path, low_path, high_ppg, low_ppg, high_name, low_name) -> None:
    for index, rid in enumerate(ppg_ids):
        cid = "ppg_difference" + (f"_{index + 1}" if index else "")
        margin = high_ppg - low_ppg
        calculations.append({"calculation_id":cid, "requirement_id":rid,
            "operation":"subtract", "inputs":[
                {"evidence_id":item.evidence_id,"path":high_path},
                {"evidence_id":item.evidence_id,"path":low_path}],
            "result":str(margin),"unit":"points per game"})
        if index == 0:
            claims.append(Claim(text=f"{high_name} scored {margin} points per game more than {low_name}.",
                kind="derived", evidence_ids=[item.evidence_id], calculation_id=cid))


def _ts_margin_block(calculations, claims, ts_ids, matched, percent_value) -> None:
    (name_a, ev_a), (name_b, ev_b) = matched
    ts_a, ts_b = percent_value(ev_a.rows["TS_PCT"]), percent_value(ev_b.rows["TS_PCT"])
    hi_name, hi_ev, hi_ts, lo_name, lo_ev, lo_ts = ((name_a, ev_a, ts_a, name_b, ev_b, ts_b)
        if ts_a >= ts_b else (name_b, ev_b, ts_b, name_a, ev_a, ts_a))
    for index, rid in enumerate(ts_ids):
        cid = "ts_difference" + (f"_{index + 1}" if index else "")
        calculations.append({"calculation_id":cid, "requirement_id":rid,
            "operation":"subtract", "inputs":[
                {"evidence_id":hi_ev.evidence_id,"path":"rows.TS_PCT"},
                {"evidence_id":lo_ev.evidence_id,"path":"rows.TS_PCT"}],
            "result":str(hi_ts-lo_ts),"unit":"percentage points"})
        if index == 0:
            claims.append(Claim(text=f"{hi_name}'s true shooting was {hi_ts-lo_ts} percentage points higher than {lo_name}'s.",
                kind="derived", evidence_ids=[hi_ev.evidence_id, lo_ev.evidence_id], calculation_id=cid))

def _ranked_requirement_for(task: TaskSpec, item: EvidenceEnvelope,
                            metric: str):
    return next(
        (requirement for requirement in task.requirements
         if item.capability in requirement.capability_options
         and capability_arguments_for(
             requirement, item.capability).get("requested_metric") == metric),
        None)

def _rating_numeric_rows(item: EvidenceEnvelope, metric: str, decimal_value):
    numeric = []
    for row_index, candidate in enumerate(item.rows):
        value = decimal_value(candidate.get(metric))
        team = candidate.get("TEAM_NAME") or candidate.get("TEAM")
        if value is not None and team:
            numeric.append((row_index, value, str(team)))
    return numeric

def _deterministic_rank_draft(
    task: TaskSpec, evidence: Sequence[EvidenceEnvelope],
) -> DraftReport | None:
    from v2.domain.evidence import decimal_value
    from shared.tools.rating_metrics import RANKING_DIRECTIONS, TEAM_RATING_METRICS
    if ("team_ratings" in task.required_evidence
            and task.ranked_argument_conflicts
            and not any(map(_has_typed_ranked_arguments, task.requirements))):
        return DraftReport(
            sections=["Team rating leader"], claims=[], calculations=[],
            blocked_calculation_requirement_ids=[
                item.id for item in task.calculation_requirements],
            gaps=["Ranked team ratings could not be published: intake required "
                  "team_ratings evidence but no requirement carries typed "
                  "ranking arguments."])
    direction_words = {"asc": "lowest", "desc": "highest"}
    for item in evidence:
        if item.capability != "team_ratings" or not isinstance(item.rows, list) or not item.rows:
            continue
        metric = item.metric_definitions.get("__requested_metric__")
        if metric not in TEAM_RATING_METRICS:
            continue
        owner = _ranked_requirement_for(task, item, metric)
        if owner is None:
            continue
        direction = capability_arguments_for(
            owner, item.capability).get("ranking_direction")
        if direction not in RANKING_DIRECTIONS:
            continue
        numeric = _rating_numeric_rows(item, metric, decimal_value)
        if not numeric:
            continue
        extreme = (min(value for _, value, _ in numeric) if direction == "asc"
                   else max(value for _, value, _ in numeric))
        winners = [(index, value, team) for index, value, team in numeric if value == extreme]
        return _rank_draft_report(
            task, item, owner, metric, TEAM_RATING_METRICS[metric]["label"],
            direction, direction_words, numeric, winners, decimal_value)
    return None


def _has_typed_ranked_arguments(requirement) -> bool:
    if "team_ratings" not in requirement.capability_options:
        return False
    try:
        arguments = capability_arguments_for(requirement, "team_ratings")
    except ValueError:
        return False
    return bool(arguments.get("requested_metric"))


def _rank_draft_report(task, item, owner, metric, label, direction,
                       direction_words, numeric, winners, decimal_value):
    has_team_subject = any(entity.type == "team" for entity in task.entities)
    eligible, blocked = [], []
    for requirement in task.calculation_requirements:
        if not has_team_subject and metric in set(requirement.metric_ids or []):
            eligible.append(requirement)
        else:
            blocked.append(requirement.id)
    if len(winners) != 1:
        return DraftReport(
            sections=["Team rating leader"], claims=[], calculations=[],
            blocked_calculation_requirement_ids=[item.id for item in task.calculation_requirements],
            gaps=[f"The requested {label} extremum is tied across {len(winners)} teams."])
    winner_index, value, team = winners[0]
    inputs = [{"evidence_id": item.evidence_id, "path": f"rows[{row_index}].{metric}"}
              for row_index, _, _ in numeric]
    subject_input = next(index for index, (row_index, _, _) in enumerate(numeric)
                         if row_index == winner_index)
    calculations = [{
        "calculation_id": f"requested_metric_rank_{index + 1}",
        "requirement_id": requirement.id,
        "operation": "rank_asc" if direction == "asc" else "rank_desc",
        "inputs": inputs, "subject_input": subject_input, "result": "1", "unit": "rank",
    } for index, requirement in enumerate(eligible)]
    calculation_id = calculations[0]["calculation_id"] if calculations else None
    output_bindings = _rank_output_bindings(owner, item, winner_index, calculations, eligible)
    from v2.contracts import Claim
    return DraftReport(
        sections=["Team rating leader"],
        claims=[Claim(
            text=(f"{team} had the {direction_words[direction]} {label} "
                  f"in {item.season or 'the selected season'}: {value}."),
            kind="derived" if calculation_id else "observed",
            evidence_ids=[item.evidence_id], calculation_id=calculation_id,
            output_bindings=output_bindings)],
        calculations=calculations,
        blocked_calculation_requirement_ids=blocked,
        gaps=(["Some requested calculations do not declare the requested metric in their metric_ids."]
              if blocked else []))


def _rank_output_bindings(owner, item, winner_index, calculations, eligible):
    from v2.contracts import CalculationOutputBinding, EvidenceOutputBinding
    winner_row = item.rows[winner_index]
    row_selector = f"rows[{winner_index}]"
    subject_fields = _rank_subject_fields(winner_row, row_selector)
    from v2.adapters.capabilities import CAPABILITIES
    capability_units = getattr(
        CAPABILITIES.get(item.capability), "units", {}) or {}
    output_bindings: list = []
    for output_id in owner.requested_outputs:
        if output_id not in winner_row or winner_row[output_id] is None:
            continue
        unit_name = (item.units or {}).get(output_id) \
            or capability_units.get(output_id)
        unit = {"kind": "declared", "value": unit_name} \
            if unit_name else {"kind": "unitless"}
        output_bindings.append(EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=owner.id,
            output_id=output_id,
            node_id=owner.id,
            evidence_id=item.evidence_id,
            selector=f"{row_selector}.{output_id}",
            value=_rank_binding_value(winner_row[output_id]),
            unit=unit,
            domain=item.capability,
            **subject_fields,
        ))
    if calculations:
        cited_requirement_id = calculations[0]["requirement_id"]
        cited_requirement = next(
            (requirement for requirement in eligible
             if requirement.id == cited_requirement_id), None)
        if cited_requirement is not None:
            for output_id in cited_requirement.requested_outputs:
                output_bindings.append(CalculationOutputBinding(
                    requirement_kind="calculation",
                    requirement_id=cited_requirement.id,
                    output_id=output_id,
                    calculation_id=calculations[0]["calculation_id"],
                ))
    return output_bindings


def _rank_subject_fields(winner_row, row_selector) -> dict:
    subject_id = winner_row.get("TEAM_ID")
    if subject_id is not None and str(subject_id).strip():
        return {
            "subject_entity_type": "team",
            "subject_entity_id": str(subject_id),
            "subject_selector": f"{row_selector}.TEAM_ID",
            "row_selector": row_selector,
        }
    return {
        "subject_entity_type": None,
        "subject_entity_id": None,
        "subject_selector": None,
        "row_selector": None,
    }


def _rank_binding_value(raw):
    if isinstance(raw, bool):
        return {"kind": "boolean", "value": raw}
    if isinstance(raw, int):
        return {"kind": "integer", "value": raw}
    if isinstance(raw, float):
        return {"kind": "float", "value": raw}
    if isinstance(raw, Decimal):
        return {"kind": "decimal", "value": str(raw)}
    return {"kind": "string", "value": str(raw)}

class ModelSynthesizer(ModelStage):
    prompt_name = "synthesizer"
    route = "synthesizer"
    schema = DraftReport

    async def synthesize(
        self, task: TaskSpec, evidence: Sequence[EvidenceEnvelope]
    ) -> DraftReport:
        task = _canonicalize_calculation_requirements(task)
        canonical = (_deterministic_rank_draft(task, evidence)
                     or _deterministic_game_log_draft(task, evidence)
                     or _deterministic_player_comparison_draft(task, evidence))
        if canonical is not None:
            return _validate_draft(canonical, evidence, task)
        payload = {
            "task": task.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "skills": self._skills.activate(task.skills),
        }
        draft = await self._generate(payload)
        try:
            return _validate_draft(draft, evidence, task)
        except InvalidDraftCalculation as exc:
            invalid_ids = set(exc.requirement_ids)
            invalid_calculations = {
                item.calculation_id for item in draft.calculations
                if item.requirement_id in invalid_ids or not invalid_ids
            }
            safe_claims = [claim for claim in draft.claims
                           if claim.calculation_id not in invalid_calculations]
            safe_calculations = [item for item in draft.calculations
                                 if item.calculation_id not in invalid_calculations]
            blocked = sorted(set(draft.blocked_calculation_requirement_ids)
                             | invalid_ids)
            partial = draft.model_copy(update={
                "claims": safe_claims,
                "calculations": safe_calculations,
                "blocked_calculation_requirement_ids": blocked,
                "gaps": list(dict.fromkeys([
                    *draft.gaps, str(exc),
                ])),
            })
            return _validate_draft(partial, evidence, task)

class ModelRepairer(ModelStage):
    prompt_name = "repair_answer"
    route = "repair"
    schema = DraftReport

    @staticmethod
    def _key(claim: Claim) -> tuple[Any, ...]:
        return (claim.text, claim.kind, tuple(claim.evidence_ids),
                claim.calculation_id, claim.confidence)

    @classmethod
    def _missing_replacements(
        cls, original: DraftReport, repaired: DraftReport,
        verification: VerificationReport,
    ) -> list[dict[str, Any]]:
        supported_keys = {
            cls._key(original.claims[result.claim_index])
            for result in verification.claim_results
            if result.supported and result.claim_index < len(original.claims)
        }
        rejected_keys = {
            cls._key(original.claims[result.claim_index])
            for result in verification.claim_results
            if not result.supported and result.claim_index < len(original.claims)
        }
        candidates = [claim for claim in repaired.claims
                      if cls._key(claim) not in supported_keys
                      and cls._key(claim) not in rejected_keys]
        assigned: set[int] = set()
        requirements: list[dict[str, Any]] = []
        for result in verification.claim_results:
            if result.supported or result.claim_index >= len(original.claims):
                continue
            claim = original.claims[result.claim_index]
            match = next((index for index, item in enumerate(candidates)
                          if index not in assigned
                          and set(item.evidence_ids) & set(claim.evidence_ids)
                          and (claim.calculation_id is None
                               or item.calculation_id == claim.calculation_id)), None)
            if match is not None:
                assigned.add(match)
                continue
            requirements.append({
                "claim_index": result.claim_index,
                "kind": claim.kind.value,
                "evidence_ids": claim.evidence_ids,
                "calculation_id": claim.calculation_id,
            })
        return requirements

    def _merge_supported(
        self, original: DraftReport, repaired: DraftReport,
        verification: VerificationReport,
    ) -> DraftReport:
        supported = [
            original.claims[result.claim_index]
            for result in verification.claim_results
            if result.supported and result.claim_index < len(original.claims)
        ]
        supported_keys = {self._key(claim) for claim in supported}
        rejected_keys = {
            self._key(original.claims[result.claim_index])
            for result in verification.claim_results
            if not result.supported and result.claim_index < len(original.claims)
        }
        claims = [
            *supported,
            *[claim for claim in repaired.claims
              if self._key(claim) not in supported_keys
              and self._key(claim) not in rejected_keys],
        ]
        return DraftReport.model_validate(repaired.model_copy(
            update={"claims": claims, "calculations": list(original.calculations),
                    "blocked_calculation_requirement_ids": list(original.blocked_calculation_requirement_ids), "gaps": list(original.gaps)}).model_dump())

    def _fallback_repair(
        self, draft: DraftReport, verification: VerificationReport,
    ) -> DraftReport:
        rejected = {
            item.claim_index for item in verification.claim_results
            if not item.supported
        }
        claims = [
            claim for index, claim in enumerate(draft.claims)
            if index not in rejected
        ]
        gaps = list(dict.fromkeys([
            *draft.gaps,
            *verification.missing_branches,
            *verification.contradictions,
            *verification.repair_instructions,
        ]))
        return draft.model_copy(update={"claims": claims, "gaps": gaps})

    async def repair(
        self,
        task: TaskSpec,
        draft: DraftReport,
        evidence: Mapping[str, EvidenceEnvelope],
        verification: VerificationReport,
    ) -> DraftReport:
        payload = {
            "task": task.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
            "skills": self._skills.activate(task.skills),
            "admitted_evidence": [
                item.model_dump(mode="json") for item in evidence.values()
            ],
        }
        try:
            generated = await self._generate(payload)
        except Exception:
            return self._fallback_repair(draft, verification)
        repaired = _validate_draft(generated, list(evidence.values()))
        repaired = self._merge_supported(draft, repaired, verification)
        missing = self._missing_replacements(draft, repaired, verification)
        if missing:
            try:
                generated = await self._generate({
                    **payload,
                    "previous_repair": repaired.model_dump(mode="json"),
                    "required_replacements": missing,
                })
            except Exception:
                return self._fallback_repair(draft, verification)
            repaired = _validate_draft(generated, list(evidence.values()))
            repaired = self._merge_supported(draft, repaired, verification)
            missing = self._missing_replacements(draft, repaired, verification)
        if missing:
            repaired = repaired.model_copy(update={
                "gaps": list(dict.fromkeys([
                    *repaired.gaps,
                    "A rejected evidence branch could not be corrected from the available data.",
                ])),
            })
        return DraftReport.model_validate(repaired.model_dump())

class ModelSemanticVerifier(ModelStage):
    prompt_name = "verifier"
    route = "semantic_verifier"
    schema = VerificationReport

    async def verify(
        self,
        task: TaskSpec,
        draft: DraftReport,
        evidence: Mapping[str, EvidenceEnvelope],
    ) -> VerificationReport:
        compact = [
            {
                "evidence_id": item.evidence_id,
                "capability": item.capability,
                "source": item.source,
                "observed_at": item.observed_at.isoformat(),
                "season": item.season,
                "vintages": item.vintages,
                "task_season_scoped": item.task_season_scoped,
                "as_of": item.as_of.isoformat() if item.as_of else None,
                "entities": [entity.model_dump(mode="json")
                             for entity in item.entities],
                "units": item.units,
                "metric_definitions": item.metric_definitions,
                "qualification": item.qualification,
                "coverage": item.coverage,
                "warnings": item.warnings,
                "lineage": item.lineage,
                "rows": item.rows,
            }
            for item in evidence.values()
        ]
        payload = {
            "task": task.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "evidence": compact,
            "skills": self._skills.activate(task.skills),
        }
        report = await self._generate(payload)
        expected = set(range(len(draft.claims)))
        observed = [item.claim_index for item in report.claim_results]
        if (len(observed) != len(set(observed))
                or any(index not in expected for index in observed)):
            raise ValueError(
                "semantic verifier returned duplicate or unknown claim indices")
        return report

class RecordedStructuredModel:
    def __init__(self, model: StructuredModel, ledger: Any, *, turn_id: str) -> None:
        if not turn_id.strip():
            raise ValueError("recorded model turn id must be non-empty")
        self._model = model
        self._ledger = ledger
        self._turn_id = turn_id
        self._sequence = 0

    async def generate(
        self,
        *,
        schema: type[T],
        prompt: str,
        payload: Mapping[str, Any],
        envelope: RequestEnvelope,
        decode=None,
    ) -> T:
        from v2.runtime.ledger import LedgerKind

        self._sequence += 1
        call_id = f"model:{self._turn_id}:{self._sequence}"
        if hasattr(self._model, "last_request_count"):
            self._model.last_request_count = None
        if hasattr(self._model, "last_usage_unknown"):
            self._model.last_usage_unknown = None
        if hasattr(self._model, "last_output_strategy"):
            self._model.last_output_strategy = None
        self._ledger.append(
            LedgerKind.MODEL_REQUEST,
            turn_id=self._turn_id,
            call_id=call_id,
            data=envelope.model_dump(mode="json"),
        )
        started = time.perf_counter()
        try:
            result = await self._model.generate(
                schema=schema,
                prompt=prompt,
                payload=payload,
                envelope=envelope,
                decode=decode,
            )
            if not isinstance(result, schema):
                raise TypeError(
                    f"structured model must return {schema.__name__}")
            result = schema.model_validate(result.model_dump())
            if isinstance(result, (TaskSpec, RequirementReview)):
                result = result.model_copy(update={"ranked_argument_conflicts": []})
        except BaseException as exc:
            self._ledger.append(
                LedgerKind.ASSISTANT_ATTEMPT,
                turn_id=self._turn_id,
                call_id=call_id,
                data={"status": "failed", "error": exception_text(exc),
                      "duration_ms": max(0, round(
                          (time.perf_counter() - started) * 1000)),
                      "provider_attempts": list(getattr(
                          self._model, "last_failures", [])),
                      "reasoning_content_promotions": list(getattr(
                          self._model, "last_promotions", []))},
            )
            raise
        actual_provider = getattr(self._model, "last_provider", None)
        actual_model = getattr(self._model, "last_model", None)
        extra = getattr(self._model, "last_decode_extra", None)
        if extra is None and decode is not None:
            extra = decode(result)
        request_count = getattr(self._model, "last_request_count", None)
        usage_unknown = getattr(self._model, "last_usage_unknown", None)
        output_strategy = getattr(self._model, "last_output_strategy", None)
        data = {
                "status": "accepted",
                "output": result.model_dump(mode="json"),
                "provider": actual_provider or envelope.provider,
                "model": actual_model or envelope.model,
                "used_fallback": (
                    (actual_provider or envelope.provider) != envelope.provider
                    or (actual_model or envelope.model) != envelope.model
                ),
                "duration_ms": max(0, round(
                    (time.perf_counter() - started) * 1000)),
                "provider_attempts": list(getattr(
                    self._model, "last_failures", [])),
                "reasoning_content_promotions": list(getattr(
                    self._model, "last_promotions", [])),
            }
        if output_strategy is not None:
            data["output_strategy"] = str(output_strategy)
        if request_count is not None:
            data["model_requests"] = request_count
            data["repaired"] = request_count > 1
        elif usage_unknown is not None:
            data["usage_unknown"] = usage_unknown
        if extra:
            data.update(extra)
        self._ledger.append(
            LedgerKind.ASSISTANT_ATTEMPT,
            turn_id=self._turn_id,
            call_id=call_id,
            data=data,
        )
        return result
