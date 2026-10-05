from __future__ import annotations

import copy
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

from pydantic import BaseModel
from pydantic_ai import NativeOutput, PromptedOutput, ToolOutput
from v2.argument_schemas import normalize_provider_wire_schema


class OutputStrategy(StrEnum):
    STRICT_SCHEMA = "strict_schema"
    TOOL_CALL = "tool_call"
    PROMPTED_JSON = "prompted_json"


STRATEGY_LADDER: Final[tuple[OutputStrategy, ...]] = (
    OutputStrategy.STRICT_SCHEMA,
    OutputStrategy.TOOL_CALL,
    OutputStrategy.PROMPTED_JSON,
)


class CapabilityTableError(ValueError):
    pass


class Support(StrEnum):
    MEASURED = "measured"
    REFUSED = "refused"
    UNMEASURED = "unmeasured"

    @property
    def supported(self) -> bool:
        return self is Support.MEASURED


_SUPPORT_FLAGS: Final[tuple[str, ...]] = (
    "strict_json_schema", "tool_calling", "strict_tool_definitions")


@dataclass(frozen=True)
class CapabilityMeasurement:
    probe: str
    measured_at: str
    models: tuple[str, ...]


@dataclass(frozen=True)
class EndpointCapabilities:
    endpoint: str
    strict_json_schema: Support = Support.UNMEASURED
    tool_calling: Support = Support.UNMEASURED
    strict_tool_definitions: Support = Support.UNMEASURED
    measurement: CapabilityMeasurement | None = None

    def supports(self, strategy: OutputStrategy) -> bool:
        if strategy is OutputStrategy.STRICT_SCHEMA:
            return self.strict_json_schema.supported
        if strategy is OutputStrategy.TOOL_CALL:
            return self.tool_calling.supported
        return True


def resolve_strategy(capabilities: EndpointCapabilities) -> OutputStrategy:
    return next(strategy for strategy in STRATEGY_LADDER
                if capabilities.supports(strategy))


def output_type_for(strategy: OutputStrategy, schema: type[BaseModel],
                    capabilities: EndpointCapabilities) -> Any:
    if strategy is OutputStrategy.STRICT_SCHEMA:
        return NativeOutput(schema, strict=True)
    if strategy is OutputStrategy.TOOL_CALL:
        return ToolOutput(
            schema, strict=capabilities.strict_tool_definitions.supported)
    return PromptedOutput(schema)


CAPABILITY_TABLE_PATH: Final[Path] = Path(__file__).with_name(
    "endpoint_capabilities.json")
_CAPABILITY_ENTRY_KEYS: Final[frozenset[str]] = frozenset(
    {"base_url", *_SUPPORT_FLAGS})
_MEASUREMENT_KEYS: Final[frozenset[str]] = frozenset(
    {"probe", "measured_at", "models"})


def normalize_endpoint(base_url: str) -> str:
    parts = urlsplit(str(base_url or "").strip())
    if parts.scheme != "https" or not parts.netloc:
        raise CapabilityTableError(f"endpoint base_url must be https: {base_url!r}")
    return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/").casefold()


def _support(value: object, endpoint: str, flag: str) -> Support:
    try:
        return Support(value)
    except ValueError as error:
        raise CapabilityTableError(
            f"{flag} for {endpoint} must be measured or refused, never an "
            f"assumption: {value!r}") from error


def _measurement(entry: Mapping[str, Any]) -> CapabilityMeasurement | None:
    raw = entry.get("measurement")
    if raw is None:
        return None
    if (not isinstance(raw, Mapping) or set(raw) != _MEASUREMENT_KEYS
            or not isinstance(raw["probe"], str) or not raw["probe"].strip()
            or not isinstance(raw["measured_at"], str)
            or not raw["measured_at"].strip()
            or not isinstance(raw["models"], list)
            or not raw["models"]
            or not all(isinstance(model, str) and model.strip()
                       for model in raw["models"])):
        raise CapabilityTableError(
            f"measurement needs {sorted(_MEASUREMENT_KEYS)}: {raw!r}")
    return CapabilityMeasurement(
        probe=raw["probe"], measured_at=raw["measured_at"],
        models=tuple(raw["models"]))


def load_capability_table(
    path: Path | None = None,
) -> dict[str, EndpointCapabilities]:
    document = json.loads((path or CAPABILITY_TABLE_PATH).read_text())
    entries = document.get("endpoints") if isinstance(document, Mapping) else None
    if not isinstance(entries, list):
        raise CapabilityTableError("capability table needs an endpoints list")
    table: dict[str, EndpointCapabilities] = {}
    for entry in entries:
        if (not isinstance(entry, Mapping)
                or not _CAPABILITY_ENTRY_KEYS <= set(entry)
                or set(entry) - _CAPABILITY_ENTRY_KEYS - {"measurement"}):
            raise CapabilityTableError(
                f"capability entry needs exactly "
                f"{sorted({*_CAPABILITY_ENTRY_KEYS, 'measurement'})}")
        endpoint = normalize_endpoint(str(entry["base_url"]))
        if endpoint in table:
            raise CapabilityTableError(f"duplicate capability entry for {endpoint}")
        flags = {flag: _support(entry[flag], endpoint, flag)
                 for flag in _SUPPORT_FLAGS}
        measurement = _measurement(entry)
        if (measurement is None
                and any(flag is not Support.UNMEASURED
                        for flag in flags.values())):
            raise CapabilityTableError(
                f"capability row for {endpoint} reports an outcome without a "
                "measurement")
        table[endpoint] = EndpointCapabilities(
            endpoint=endpoint, measurement=measurement, **flags)
    return table


@lru_cache(maxsize=1)
def _shipped_capability_table() -> dict[str, EndpointCapabilities]:
    return load_capability_table()


def capabilities_for(
    base_url: str,
    table: Mapping[str, EndpointCapabilities] | None = None,
) -> EndpointCapabilities:
    endpoint = normalize_endpoint(base_url)
    known = _shipped_capability_table() if table is None else table
    return known.get(endpoint, EndpointCapabilities(endpoint=endpoint))


class SchemaNotPortable(ValueError):
    def __init__(self, path: str, construct: str, detail: str) -> None:
        self.path = path
        self.construct = construct
        super().__init__(f"{construct} at {path} has no portable form: {detail}")


@dataclass(frozen=True)
class SchemaSanitization:
    schema: dict[str, Any]
    rewrites: tuple[str, ...]


LOOKAROUND_PATTERN: Final[re.Pattern[str]] = re.compile(r"\(\?(?:=|!|<=|<!)")
STRICT_SAFE_PATTERNS: Final[dict[str, str]] = {
    r"^(?!^[-+.]*$)[+-]?0*\d*\.?\d*$": r"^[+-]?(?:0*\d+(?:\.\d*)?|0*\.\d+)$",
}
DROPPED_SCHEMA_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"maxItems", "minItems", "discriminator"})
OPAQUE_SCHEMA_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"default", "enum", "examples"})


def _portable_pattern(pattern: str, path: str,
                      rewrites: list[str]) -> str:
    replacement = STRICT_SAFE_PATTERNS.get(pattern)
    if replacement is not None:
        rewrites.append(f"{path}.pattern-rewritten")
        return replacement
    if LOOKAROUND_PATTERN.search(pattern) is None:
        return pattern
    raise SchemaNotPortable(
        path, "pattern", f"look-around cannot be compiled: {pattern!r}")


def sanitize_schema(schema: Mapping[str, Any]) -> SchemaSanitization:
    rewrites: list[str] = []

    def walk(node: Any, path: str) -> Any:
        if isinstance(node, list):
            return [walk(item, f"{path}[]") for item in node]
        if not isinstance(node, Mapping):
            return copy.deepcopy(node)
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in DROPPED_SCHEMA_KEYWORDS:
                rewrites.append(f"{path}.{key}-dropped")
                continue
            if key == "const":
                out["enum"] = [copy.deepcopy(value)]
                rewrites.append(f"{path}.const-to-enum")
                continue
            if key == "pattern" and isinstance(value, str):
                out[key] = _portable_pattern(value, path, rewrites)
                continue
            if key in OPAQUE_SCHEMA_KEYWORDS:
                out[key] = copy.deepcopy(value)
                continue
            out[key] = walk(value, f"{path}.{key}")
        return out

    return SchemaSanitization(walk(dict(schema), "$"), tuple(rewrites))


def _free_form_paths(node: Any, path: str = "$") -> list[str]:
    if isinstance(node, list):
        return [found for item in node
                for found in _free_form_paths(item, f"{path}[]")]
    if not isinstance(node, Mapping):
        return []
    found = ([] if node.get("type") != "object"
             or node.get("additionalProperties", False) is False
             else [path])
    return found + [nested for key, value in node.items()
                    if key not in OPAQUE_SCHEMA_KEYWORDS
                    for nested in _free_form_paths(value, f"{path}.{key}")]


def strict_compatible(schema: Mapping[str, Any]) -> SchemaSanitization:
    portable = sanitize_schema(schema)
    free_form = _free_form_paths(portable.schema)
    if free_form:
        return SchemaSanitization(
            portable.schema,
            portable.rewrites + tuple(
                f"{path}-free-form-not-strict-compatible" for path in free_form),
        )
    candidate, report = normalize_provider_wire_schema(portable.schema)
    return SchemaSanitization(
        candidate,
        portable.rewrites + tuple(
            f"{loss['path']}.{loss['classification']}"
            for loss in report["losses"]),
    )


def wire_schema_for(strategy: OutputStrategy,
                    schema: Mapping[str, Any]) -> SchemaSanitization:
    if strategy is OutputStrategy.STRICT_SCHEMA:
        return strict_compatible(schema)
    if strategy is OutputStrategy.TOOL_CALL:
        return sanitize_schema(schema)
    return SchemaSanitization({}, ())


FENCE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\A\s*```[A-Za-z0-9_+-]*[ \t]*\r?\n(?P<body>.*?)\r?\n?[ \t]*```\s*\Z",
    re.S)
TRAILING_COMMA_PATTERN: Final[re.Pattern[str]] = re.compile(
    r",([ \t\r\n]*[}\]])")


def strip_code_fence(text: str) -> str:
    match = FENCE_PATTERN.match(text)
    return match.group("body") if match is not None else text


def strip_surrounding_prose(text: str) -> str:
    start = min((index for index in (text.find("{"), text.find("[")) if index >= 0),
                default=-1)
    end = max(text.rfind("}"), text.rfind("]"))
    if start < 0 or end <= start:
        return text
    return text[start:end + 1]


def parses_as_json(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


def repair_json_text(text: str) -> str:
    for candidate in (strip_code_fence(text), strip_surrounding_prose(text), text):
        if parses_as_json(candidate):
            return candidate
        without_trailing_commas = TRAILING_COMMA_PATTERN.sub(r"\1", candidate)
        if without_trailing_commas != candidate and parses_as_json(
                without_trailing_commas):
            return without_trailing_commas
    return text


def repaired_output_payload(_ctx: Any = None, /, *, output: Any,
                            **_ignored: Any) -> Any:
    return repair_json_text(output) if isinstance(output, str) else output


class FailureKind(StrEnum):
    TRANSIENT = "transient"
    SCHEMA_REJECTED = "schema_rejected"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


TRANSIENT_STATUS_CODES: Final[frozenset[int]] = frozenset(
    {408, 409, 425, 429, 500, 502, 503, 504})
PERMANENT_STATUS_CODES: Final[frozenset[int]] = frozenset({401, 403, 404})
SCHEMA_REJECTION_STATUS_CODES: Final[frozenset[int]] = frozenset({400, 415, 422})
TRANSIENT_MARKERS: Final[tuple[str, ...]] = (
    "timed out", "timeout", "rate limit", "ratelimit", "too many requests",
    "connection reset", "connection refused", "connection aborted",
    "remoteprotocolerror", "econnreset", "etimedout", "incomplete read",
    "server disconnected", "temporarily unavailable", "server_error",
)
PERMANENT_MARKERS: Final[tuple[str, ...]] = (
    "quota_exceeded", "perday", "per_day", "/day", "daily quota",
    "quota reset", "api key", "unauthorized", "forbidden", "not found",
    "content filter", "safety", "token limit", "context length",
    "maximum context",
)
SCHEMA_REFUSAL_MARKERS: Final[tuple[str, ...]] = (
    "response_format", "json_schema", "json schema", "grammar error",
    "regex parse error", "look-ahead", "look-behind", "lookahead",
    "lookbehind", "invalid schema", "schema validation", "structured output",
    "does not match the schema", "unrecognized request argument",
)
SCHEMA_REJECTION_EXCEPTION_NAMES: Final[frozenset[str]] = frozenset({
    "ValidationError", "UnexpectedModelBehavior", "ToolRetryError",
    "ModelRetry"})
PERMANENT_EXCEPTION_NAMES: Final[frozenset[str]] = frozenset({
    "ContentFilterError", "UserError"})
STATUS_CODE_ATTRIBUTES: Final[tuple[str, ...]] = ("status_code", "http_status")
MAX_FAILURE_CARRIERS: Final[int] = 8
MAX_FAILURE_DETAIL_CHARS: Final[int] = 2000


def classify_failure(*, status_code: int | None, detail: str,
                     exception_names: frozenset[str] = frozenset()
                     ) -> FailureKind:
    folded = str(detail or "").casefold()
    if (exception_names & SCHEMA_REJECTION_EXCEPTION_NAMES
            or any(marker in folded for marker in SCHEMA_REFUSAL_MARKERS)):
        return FailureKind.SCHEMA_REJECTED
    if (any(marker in folded for marker in TRANSIENT_MARKERS)
            or status_code in TRANSIENT_STATUS_CODES):
        return FailureKind.TRANSIENT
    if (any(marker in folded for marker in PERMANENT_MARKERS)
            or exception_names & PERMANENT_EXCEPTION_NAMES
            or status_code in PERMANENT_STATUS_CODES):
        return FailureKind.PERMANENT
    if status_code in SCHEMA_REJECTION_STATUS_CODES:
        return FailureKind.SCHEMA_REJECTED
    return FailureKind.UNKNOWN


def failure_status_code(carriers: Iterable[BaseException]) -> int | None:
    for carrier in carriers:
        for attribute in STATUS_CODE_ATTRIBUTES:
            value = getattr(carrier, attribute, None)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    return None


def failure_detail(carriers: Iterable[BaseException]) -> str:
    return " ".join(
        f"{type(carrier).__name__} {str(carrier)[:MAX_FAILURE_DETAIL_CHARS]}"
        for carrier in carriers).casefold()


def classify_exception(exc: BaseException) -> FailureKind:
    carriers = list(_failure_carriers([exc]))
    names = {type(carrier).__name__ for carrier in carriers}
    return classify_failure(
        status_code=failure_status_code(carriers),
        detail=failure_detail(carriers),
        exception_names=names,
    )


def _failure_carriers(carriers: Iterable[BaseException]) -> Iterable[BaseException]:
    pending: list[BaseException] = list(carriers)
    seen: set[int] = set()
    while pending:
        item = pending.pop(0)
        if id(item) in seen or not isinstance(item, BaseException):
            continue
        seen.add(id(item))
        yield item
        if len(seen) >= MAX_FAILURE_CARRIERS:
            return
        for linked in (item.__cause__, item.__context__):
            if isinstance(linked, BaseException):
                pending.append(linked)
        if isinstance(item, BaseExceptionGroup):
            pending.extend(child for child in item.exceptions
                           if isinstance(child, BaseException))


DESCENDING_KINDS: Final[frozenset[FailureKind]] = frozenset(
    {FailureKind.SCHEMA_REJECTED, FailureKind.TRANSIENT, FailureKind.UNKNOWN})


@dataclass(frozen=True)
class LadderAttempt:
    rung: OutputStrategy
    attempt_number: int
    failure_kind: FailureKind | None


class StrategyLadder:
    """The rungs one stage call has left, and the ones it has already lost.

    A stage call owns its ladder, so a stage that has to descend does not
    move any other stage. The floor is terminal: its failure is the answer.
    """

    def __init__(self, capabilities: EndpointCapabilities) -> None:
        self._index = STRATEGY_LADDER.index(resolve_strategy(capabilities))
        self._attempts: list[LadderAttempt] = []

    @property
    def rung(self) -> OutputStrategy:
        return STRATEGY_LADDER[self._index]

    @property
    def at_floor(self) -> bool:
        return self._index == len(STRATEGY_LADDER) - 1

    @property
    def attempts(self) -> tuple[LadderAttempt, ...]:
        return tuple(self._attempts)

    def record(self, *, attempt_number: int,
               failure_kind: FailureKind | None) -> None:
        self._attempts.append(
            LadderAttempt(self.rung, attempt_number, failure_kind))

    def descend(self, kind: FailureKind) -> OutputStrategy | None:
        """The rung given up, or None when the ladder holds its ground."""
        if kind not in DESCENDING_KINDS or self.at_floor:
            return None
        given_up = self.rung
        self._index += 1
        return given_up
