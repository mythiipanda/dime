from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

BACKEND = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "conformance_endpoints.json"

Outcome = Literal[
    "accepted",
    "rejected_validation",
    "rejected_http",
    "timed_out",
    "unreachable",
]

_STATED_CONSTRUCTS: tuple[tuple[str, str], ...] = (
    ("look-around, including look-ahead and look-behind", "pattern"),
    ("look-ahead", "pattern"),
    ("look-behind", "pattern"),
    ("lookahead", "pattern"),
    ("lookbehind", "pattern"),
    ("additionalproperties", "additionalProperties"),
    ("additional properties", "additionalProperties"),
    ("unevaluated", "unevaluatedProperties"),
    ("patternproperties", "patternProperties"),
    ("dependentrequired", "dependentRequired"),
    ("prefixitems", "prefixItems"),
    ("unevaluateditems", "unevaluatedItems"),
    ("anyof", "anyOf"),
    ("oneof", "oneOf"),
    ("allof", "allOf"),
    ("ref siblings", "$ref"),
    ("recursion", "$ref"),
    ("discriminator", "discriminator"),
    ("const", "const"),
    ("enum", "enum"),
    ("format", "format"),
    ("minimum", "minimum"),
    ("exclusive", "exclusiveMinimum"),
    ("multipleof", "multipleOf"),
    ("minlength", "minLength"),
    ("maxlength", "maxLength"),
    ("minitems", "minItems"),
    ("maxitems", "maxItems"),
    ("maxproperties", "maxProperties"),
)

SCHEMA_KEYWORDS: tuple[str, ...] = (
    "$ref",
    "$defs",
    "additionalProperties",
    "allOf",
    "anyOf",
    "const",
    "default",
    "description",
    "discriminator",
    "enum",
    "exclusiveMaximum",
    "exclusiveMinimum",
    "format",
    "items",
    "maxItems",
    "maxLength",
    "maxProperties",
    "maximum",
    "minItems",
    "minLength",
    "minProperties",
    "minimum",
    "multipleOf",
    "oneOf",
    "pattern",
    "prefixItems",
    "properties",
    "required",
    "title",
    "type",
    "uniqueItems",
)

_KEYWORDS = frozenset(SCHEMA_KEYWORDS)

_OUTCOME_RANK: dict[str, int] = {
    "timed_out": 0,
    "unreachable": 1,
    "rejected_http": 2,
    "rejected_validation": 3,
    "accepted": 4,
}
_SCHEMA_MAP_KEYS = frozenset({
    "$defs", "definitions", "properties", "patternProperties"})
_SCHEMA_LIST_KEYS = frozenset({"anyOf", "oneOf", "allOf", "prefixItems"})
_SCHEMA_NODE_KEYS = frozenset({
    "items", "additionalItems", "contains", "propertyNames", "not",
    "if", "then", "else", "additionalProperties", "unevaluatedItems",
    "unevaluatedProperties"})

class SchemaConformanceError(ValueError):
    pass

def environment(path: Path | None = None) -> dict[str, str]:
    source = path if path is not None else BACKEND / ".env"
    env = dict(os.environ)
    if not source.exists():
        return env
    for line in source.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        name, _, value = entry.partition("=")
        name = name.strip()
        if name and name not in env:
            env[name] = value.strip().strip('"').strip("'")
    return env

@dataclass(frozen=True)
class EndpointConfig:
    name: str
    base_url: str
    key_env: tuple[str, ...]
    models: tuple[str, ...]
    strict: bool
    timeout_s: float
    thinking_off: bool

    def resolve_key(self, env: Mapping[str, str]) -> str | None:
        for name in self.key_env:
            value = env.get(name, "")
            if value.strip():
                return value
        return None

    def key_present(self, env: Mapping[str, str] | None = None) -> bool:
        return self.resolve_key(
            environment() if env is None else env) is not None

@dataclass(frozen=True)
class ProbePlan:
    endpoints: tuple[EndpointConfig, ...]
    budget: int

    @property
    def model_count(self) -> int:
        return sum(len(endpoint.models) for endpoint in self.endpoints)

@dataclass(frozen=True)
class StageSpec:
    stage: str
    route: str
    schema: type

    def wire_response_format(self, model_name: str) -> dict[str, Any]:
        return wire_response_format(self.schema, model_name=model_name)

@dataclass(frozen=True)
class Classification:
    outcome: Outcome
    stated_construct: str | None = None
    schema_attributable: bool = False
    detail: str = ""

@dataclass(frozen=True)
class ProbeResult:
    endpoint: str
    model: str
    stage: str
    outcome: Outcome
    latency_ms: int
    schema_sha256: str
    schema_bytes: int
    detail: str = ""
    stated_construct: str | None = None
    schema_attributable: bool = False

    @property
    def accepted(self) -> bool:
        return self.outcome == "accepted"

@dataclass(frozen=True)
class ConstructFinding:
    construct: str
    broken_models: tuple[str, ...]
    broken_cells: tuple[str, ...]

    @property
    def model_count(self) -> int:
        return len(self.broken_models)

@dataclass
class ConformanceReport:
    results: list[ProbeResult] = field(default_factory=list)
    requests_spent: int = 0
    control_results: list[ProbeResult] = field(default_factory=list)

    def cell(self, endpoint: str, model: str, stage: str) -> ProbeResult | None:
        for result in self.results:
            if (result.endpoint, result.model, result.stage) == (
                endpoint, model, stage):
                return result
        return None

    def models_for(self, endpoint: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            result.model for result in self.results
            if result.endpoint == endpoint))

    def stages(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(result.stage for result in self.results))

    def endpoints(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(result.endpoint for result in self.results))

    def requests_remaining(self, budget: int) -> int:
        return max(0, budget - self.requests_spent)

def report_from_payload(payload: Mapping[str, Any]) -> ConformanceReport:
    def rows(name: str) -> list[ProbeResult]:
        return [
            ProbeResult(
                endpoint=row["endpoint"], model=row["model"],
                stage=row["stage"], outcome=row["outcome"],
                latency_ms=int(row["latency_ms"]),
                schema_sha256=row.get("schema_sha256", ""),
                schema_bytes=int(row.get("schema_bytes", 0)),
                detail=row.get("detail", "") or "",
                stated_construct=row.get("stated_construct"),
                schema_attributable=bool(row.get("schema_attributable")))
            for row in payload.get(name, [])]

    return ConformanceReport(
        results=rows("results"),
        control_results=rows("control_results"),
        requests_spent=int(payload.get("requests_spent", 0)))

def merge_report(fresh: ConformanceReport, prior_path: Path) -> ConformanceReport:
    if not prior_path.exists():
        return fresh
    prior = report_from_payload(json.loads(prior_path.read_text()))
    merged = list(fresh.results)
    index = {(r.endpoint, r.model, r.stage): position
             for position, r in enumerate(merged)}
    for result in prior.results:
        key = (result.endpoint, result.model, result.stage)
        if key not in index:
            index[key] = len(merged)
            merged.append(result)
        elif _OUTCOME_RANK[result.outcome] > _OUTCOME_RANK[
                merged[index[key]].outcome]:
            merged[index[key]] = result
    controls = list(fresh.control_results)
    seen_control = {(r.endpoint, r.model) for r in controls}
    controls.extend(
        result for result in prior.control_results
        if (result.endpoint, result.model) not in seen_control)
    return ConformanceReport(results=merged, control_results=controls,
                             requests_spent=fresh.requests_spent)

def load_plan(path: str | Path | None = None) -> ProbePlan:
    source = Path(path) if path is not None else CONFIG_PATH
    raw = json.loads(source.read_text(encoding="utf-8"))
    budget = raw.get("budget_requests")
    if not isinstance(budget, int) or budget <= 0:
        raise SchemaConformanceError("budget_requests must be a positive integer")
    endpoints: list[EndpointConfig] = []
    for entry in raw.get("endpoints", []):
        name = entry.get("name")
        base_url = entry.get("base_url")
        models = tuple(entry.get("models", ()))
        if not isinstance(name, str) or not name.strip():
            raise SchemaConformanceError("endpoint name must be non-empty")
        if not isinstance(base_url, str) or not base_url.strip():
            raise SchemaConformanceError(f"{name}: base_url must be non-empty")
        if not models:
            raise SchemaConformanceError(f"{name}: at least one model is required")
        for model in models:
            if not isinstance(model, str) or not model.strip():
                raise SchemaConformanceError(f"{name}: model must be non-empty")
        endpoints.append(EndpointConfig(
            name=name.strip(),
            base_url=base_url.strip(),
            key_env=tuple(
                key for key in entry.get("key_env", ()) if isinstance(key, str)),
            models=models,
            strict=bool(entry.get("strict", True)),
            timeout_s=float(entry.get("timeout_s", 60.0)),
            thinking_off=bool(entry.get("thinking_off", False)),
        ))
    if not endpoints:
        raise SchemaConformanceError("no endpoints configured")
    return ProbePlan(endpoints=tuple(endpoints), budget=budget)

def stage_specs() -> tuple[StageSpec, ...]:
    from v2.adapters.models import (
        ModelIntake,
        ModelPlanner,
        ModelRepairer,
        ModelSemanticVerifier,
        ModelSynthesizer,
    )

    return (
        StageSpec("intake", ModelIntake.route, ModelIntake.schema),
        StageSpec("plan", ModelPlanner.route, ModelPlanner.schema),
        StageSpec("synthesizer", ModelSynthesizer.route,
                  ModelSynthesizer.schema),
        StageSpec("verifier", ModelSemanticVerifier.route,
                  ModelSemanticVerifier.schema),
        StageSpec("repair", ModelRepairer.route, ModelRepairer.schema),
    )

def control_schema() -> type:
    from pydantic import BaseModel, ConfigDict, Field

    class ConformanceControl(BaseModel):
        model_config = ConfigDict(extra="forbid")
        ok: bool = Field(description="Confirm the schema was accepted.")

    return ConformanceControl

def wire_response_format(schema: type, *, model_name: str,
                         strict: bool = True) -> dict[str, Any]:
    from v2.adapters.models import _map_wire_response_format

    return _map_wire_response_format(
        schema.model_json_schema(), name=schema.__name__, strict=strict)

def schema_sha256(schema: Mapping[str, Any]) -> str:
    payload = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()

def collect_constructs(schema: Any, into: set[str] | None = None) -> set[str]:
    found = into if into is not None else set()
    if isinstance(schema, bool):
        return found
    if isinstance(schema, list):
        for item in schema:
            collect_constructs(item, found)
        return found
    if not isinstance(schema, Mapping):
        return found
    for key, value in schema.items():
        if key in _KEYWORDS:
            found.add(key)
        if key in _SCHEMA_MAP_KEYS and isinstance(value, Mapping):
            for child in value.values():
                collect_constructs(child, found)
        elif key in _SCHEMA_LIST_KEYS and isinstance(value, list):
            collect_constructs(value, found)
        elif key in _SCHEMA_NODE_KEYS:
            collect_constructs(value, found)
    return found

def _body_of(payload: Any) -> str:
    if isinstance(payload, (dict, list)):
        return json.dumps(payload)
    return payload if isinstance(payload, str) else str(payload)

def stated_construct(body: str) -> str | None:
    text = body.casefold()
    for needle, construct in _STATED_CONSTRUCTS:
        if needle in text:
            return construct
    return None

_AUTH_MARKERS = ("api key expired", "invalid api key", "unauthorized",
                "authentication", "invalid_api_key", "permission denied",
                "forbidden")

def is_credential_failure(body: str) -> bool:
    text = body.casefold()
    return any(marker in text for marker in _AUTH_MARKERS)

def classify_response(status: int, body: str) -> Classification:
    construct = stated_construct(body)
    if status == 200:
        try:
            payload = json.loads(body) if body.strip().startswith("{") else None
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and payload.get("error"):
            error = payload["error"]
            code = error.get("code") if isinstance(error, dict) else None
            message = _body_of(error)
            nested = classify_response(code, message) if isinstance(
                code, int) else Classification(
                "rejected_http", None, False, _detail_from_body(message, ""))
            return Classification(
                nested.outcome,
                nested.stated_construct,
                nested.schema_attributable,
                nested.detail)
        if isinstance(payload, dict) and payload.get("choices") is None:
            return Classification("rejected_http", None, False, "choices was null")
        return Classification("accepted")
    if status in (401, 403, 404, 429):
        return Classification("rejected_http", None, False,
                              _detail_from_body(body, ""))
    if is_credential_failure(body):
        return Classification("rejected_http", None, False,
                              _detail_from_body(body, ""))
    if status in (400, 422):
        if construct is not None:
            return Classification("rejected_validation", construct, True,
                                  _detail_from_body(body, ""))
        lowered = body.casefold()
        non_schema = ("quota", "billing", "rate limit", "too many requests",
                      "not found", "page not found", "invalid api key",
                      "permission", "model_not_found", "high demand",
                      "does not exist", "unauthorized")
        if any(word in lowered for word in non_schema):
            return Classification("rejected_http", None, False,
                                  _detail_from_body(body, ""))
        return Classification("rejected_validation", None, False,
                              _detail_from_body(body, ""))
    return Classification("rejected_http", None, False,
                          _detail_from_body(body, ""))

def classify_http_status(status: int, body: str) -> Outcome:
    return classify_response(status, body).outcome

def _detail_from_body(body: str, api_key: str, limit: int = 220) -> str:
    text = " ".join(str(body).split())
    if api_key:
        text = text.replace(api_key, "<redacted>")
    return text[:limit]

async def _post(client: Any, model: str, response_format: Mapping[str, Any],
                api_key: str, prompt: str,
                extra: Mapping[str, Any] | None = None
                ) -> tuple[Classification, int]:
    started = time.perf_counter()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format=dict(response_format),
            max_tokens=8,
            **dict(extra or {}),
        )
    except asyncio.TimeoutError:
        return (Classification("timed_out"), _elapsed_ms(started))
    except Exception as exc:
        latency = _elapsed_ms(started)
        status = getattr(exc, "status_code", None)
        body = _body_of(getattr(exc, "body", None) or exc)
        if isinstance(status, int):
            verdict = classify_response(status, body)
            verdict = Classification(
                verdict.outcome, verdict.stated_construct,
                verdict.schema_attributable,
                verdict.detail or _detail_from_body(body, api_key))
            return verdict, latency
        name = type(exc).__name__
        if "Timeout" in name:
            return Classification("timed_out", detail=name), latency
        if "Connection" in name or "Connect" in name:
            return Classification("unreachable", detail=name), latency
        verdict = classify_response(200, body)
        if verdict.outcome == "accepted":
            verdict = Classification("rejected_http", detail=name)
        return Classification(
            verdict.outcome, verdict.stated_construct,
            verdict.schema_attributable, verdict.detail or name), latency
    latency = _elapsed_ms(started)
    body = _body_of(response.model_dump(exclude_none=True))
    verdict = classify_response(200, body)
    if verdict.outcome == "accepted" and not getattr(response, "choices", None):
        verdict = Classification("rejected_http",
                                 detail="no choices in the response")
    return verdict, latency

def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)

def _build_client(endpoint: EndpointConfig, api_key: str,
                  timeout_s: float) -> Any:
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        base_url=endpoint.base_url,
        api_key=api_key,
        timeout=timeout_s,
        max_retries=0,
    )

def _request_kwargs(endpoint: EndpointConfig) -> dict[str, Any]:
    if not endpoint.thinking_off:
        return {}
    from v2.adapters.models import _with_thinking_off

    return _with_thinking_off({})

async def probe_model(endpoint: EndpointConfig, model: str,
                      specs: Sequence[StageSpec], with_control: bool,
                      concurrency: int = 4,
                      env: Mapping[str, str] | None = None) -> tuple[list[ProbeResult], int]:
    api_key = endpoint.resolve_key(environment() if env is None else env)
    if api_key is None:
        return [
            ProbeResult(endpoint.name, model, spec.stage, "unreachable", 0,
                        "", 0, "no credential in environment")
            for spec in specs
        ], 0
    client = _build_client(endpoint, api_key, endpoint.timeout_s)
    semaphore = asyncio.Semaphore(max(1, concurrency))
    prompt = "Reply with the smallest object that satisfies the schema."
    grouped = group_specs_by_wire_schema(specs, model)

    async def run_group(digest: str, stages: Sequence[StageSpec],
                        body: Mapping[str, Any]) -> tuple[str, ProbeResult]:
        async with semaphore:
            response_format = wire_response_format(
                stages[0].schema, model_name=model, strict=endpoint.strict)
            verdict, latency = await _post(
                client, model, response_format, api_key, prompt,
                _request_kwargs(endpoint))
            return digest, ProbeResult(
                endpoint=endpoint.name, model=model,
                stage=stages[0].stage, outcome=verdict.outcome,
                latency_ms=latency, schema_sha256=schema_sha256(body),
                schema_bytes=len(json.dumps(body)), detail=verdict.detail,
                stated_construct=verdict.stated_construct,
                schema_attributable=verdict.schema_attributable)

    async def run_control() -> ProbeResult | None:
        if not with_control:
            return None
        control_format = wire_response_format(control_schema(),
                                              model_name=model,
                                              strict=endpoint.strict)
        body = control_format["json_schema"]["schema"]
        async with semaphore:
            verdict, latency = await _post(
                client, model, control_format, api_key, prompt,
                _request_kwargs(endpoint))
            return ProbeResult(
                endpoint=endpoint.name, model=model, stage="control",
                outcome=verdict.outcome, latency_ms=latency,
                schema_sha256=schema_sha256(body),
                schema_bytes=len(json.dumps(body)), detail=verdict.detail,
                stated_construct=verdict.stated_construct,
                schema_attributable=verdict.schema_attributable)

    tasks = [asyncio.create_task(run_control())]
    tasks.extend(
        asyncio.create_task(run_group(digest, stages, body))
        for digest, (stages, body) in grouped.items())
    resolved = await asyncio.gather(*tasks)
    await client.close()

    control_result = resolved[0]
    by_digest = {digest: result for digest, result in resolved[1:]}
    results: list[ProbeResult] = []
    spent = len(grouped) + (1 if control_result is not None else 0)
    if control_result is not None:
        results.append(control_result)
    for spec in specs:
        for key, (_stages, _body) in group_specs_by_wire_schema(
                [spec], model).items():
            result = by_digest[key]
            results.append(ProbeResult(
                endpoint=result.endpoint, model=result.model,
                stage=spec.stage, outcome=result.outcome,
                latency_ms=result.latency_ms, schema_sha256=result.schema_sha256,
                schema_bytes=result.schema_bytes, detail=result.detail,
                stated_construct=result.stated_construct,
                schema_attributable=result.schema_attributable))
    return results, spent

def group_specs_by_wire_schema(specs: Sequence[StageSpec], model: str
                               ) -> dict[str, tuple[list[StageSpec], Any]]:
    grouped: dict[str, tuple[list[StageSpec], Any]] = {}
    for spec in specs:
        body = spec.wire_response_format(model)["json_schema"]["schema"]
        digest = schema_sha256(body)
        stages, _ = grouped.get(digest, ([], body))
        stages.append(spec)
        grouped[digest] = (stages, body)
    return grouped

def requests_for_model(specs: Sequence[StageSpec], model: str,
                       with_control: bool) -> int:
    grouped = group_specs_by_wire_schema(specs, model)
    return len(grouped) + (1 if with_control else 0)

async def run_probe(plan: ProbePlan, concurrency: int = 4) -> ConformanceReport:
    specs = stage_specs()
    report = ConformanceReport()
    for endpoint in plan.endpoints:
        for index, model in enumerate(endpoint.models):
            with_control = index == 0
            cost = requests_for_model(specs, model, with_control)
            if report.requests_spent + cost > plan.budget:
                continue
            results, spent = await probe_model(
                endpoint, model, specs, with_control,
                concurrency=concurrency)
            report.results.extend(
                result for result in results if result.stage != "control")
            report.control_results.extend(
                result for result in results if result.stage == "control")
            report.requests_spent += spent
    return report

def accepted_constructs(report: ConformanceReport, endpoint: str,
                        model: str, specs: Sequence[StageSpec]) -> set[str]:
    accepted: set[str] = set()
    for spec in specs:
        result = report.cell(endpoint, model, spec.stage)
        if result is None or not result.accepted:
            continue
        body = spec.wire_response_format(model)["json_schema"]["schema"]
        accepted |= collect_constructs(body)
    for result in report.control_results:
        if (result.endpoint, result.model) == (endpoint, model) and result.accepted:
            accepted |= {"additionalProperties", "properties", "required",
                         "title", "type", "description"}
    return accepted

def attribute_constructs(report: ConformanceReport,
                         specs: Sequence[StageSpec]) -> list[ConstructFinding]:
    per_construct: dict[str, dict[str, set[str]]] = {}
    for endpoint in report.endpoints():
        for model in report.models_for(endpoint):
            accepted = accepted_constructs(report, endpoint, model, specs)
            for spec in specs:
                result = report.cell(endpoint, model, spec.stage)
                if result is None or result.accepted:
                    continue
                if result.stated_construct is not None:
                    candidates = {result.stated_construct}
                elif result.outcome != "rejected_validation" or not accepted:
                    candidates = set()
                else:
                    body = spec.wire_response_format(model)[
                        "json_schema"]["schema"]
                    candidates = collect_constructs(body) - accepted
                for construct in sorted(candidates):
                    entry = per_construct.setdefault(
                        construct, {"models": set(), "cells": set()})
                    entry["models"].add(f"{endpoint}/{model}")
                    entry["cells"].add(f"{endpoint}/{model}/{spec.stage}")
    findings = [
        ConstructFinding(construct=construct,
                         broken_models=tuple(sorted(entry["models"])),
                         broken_cells=tuple(sorted(entry["cells"])))
        for construct, entry in per_construct.items()
    ]
    findings.sort(key=lambda item: (-item.model_count, item.construct))
    return findings

def unattributed(report: ConformanceReport) -> list[ProbeResult]:
    findings = attribute_constructs(report, stage_specs())
    claimed = {
        cell for finding in findings for cell in finding.broken_cells}
    return [
        result for result in report.results
        if not result.accepted
        and f"{result.endpoint}/{result.model}/{result.stage}" not in claimed
    ]

def _matrix_cell(result: ProbeResult | None) -> str:
    if result is None:
        return "-"
    if result.outcome == "accepted":
        return f"ok {result.latency_ms / 1000:.1f}s"
    marker = {
        "rejected_validation": "VAL",
        "rejected_http": "HTTP",
        "timed_out": "TIME",
        "unreachable": "UNREACH",
    }[result.outcome]
    return f"{marker} {result.latency_ms / 1000:.1f}s"

def render_matrix(report: ConformanceReport) -> str:
    stages = report.stages()
    header = f"{'provider':<11} {'model':<42} " + " ".join(
        f"{stage:<11}" for stage in stages)
    lines = [header, "-" * len(header)]
    for endpoint in report.endpoints():
        for model in report.models_for(endpoint):
            cells = " ".join(
                f"{_matrix_cell(report.cell(endpoint, model, stage)):<11}"
                for stage in stages)
            lines.append(f"{endpoint:<11} {model:<42} {cells}".rstrip())
    return "\n".join(lines)

def render_constructs(findings: Sequence[ConstructFinding], limit: int = 10
                      ) -> str:
    if not findings:
        return "no attributable constructs: every probed schema was accepted"
    lines = [f"{'rank':<5} {'construct':<22} {'models':<7} cells"]
    for rank, finding in enumerate(findings[:limit], 1):
        lines.append(
            f"{rank:<5} {finding.construct:<22} {finding.model_count:<7} "
            f"{len(finding.broken_cells)}")
        lines.append(f"      models: {', '.join(finding.broken_models)}")
    return "\n".join(lines)

def render_summary(report: ConformanceReport, plan: ProbePlan) -> str:
    total = len(report.results)
    accepted = sum(1 for result in report.results if result.accepted)
    unreachable = sorted({
        f"{result.endpoint}/{result.model}"
        for result in report.results
        if result.outcome == "unreachable"
    })
    control = {f"{r.endpoint}/{r.model}": r.outcome
               for r in report.control_results}
    unexplained = unattributed(report)
    reasons: dict[str, int] = {}
    for result in unexplained:
        reasons[result.outcome] = reasons.get(result.outcome, 0) + 1
    credential = sorted({
        f"{result.endpoint}/{result.model}"
        for result in report.results if is_credential_failure(result.detail)})
    lines = [
        f"requests spent: {report.requests_spent} of {plan.budget}",
        f"schema cells: {accepted} accepted of {total}",
        f"unreachable targets: {', '.join(unreachable) or 'none'}",
        f"credential failures: {', '.join(credential) or 'none'}",
        "rejections with no construct attributed: " + (
            ", ".join(f"{count} {outcome}"
                      for outcome, count in sorted(reasons.items()))
            or "none"),
        "control probes: " + ", ".join(
            f"{key}={control[key]}" for key in sorted(control)),
    ]
    return "\n".join(lines)

def redact(text: str, env: Mapping[str, str] | None = None) -> str:
    source = environment() if env is None else env
    for value in source.values():
        if len(value) >= 16:
            text = text.replace(value, "<redacted>")
    return text

def build_artifacts(report: ConformanceReport, plan: ProbePlan,
                    out_dir: Path,
                    env: Mapping[str, str] | None = None) -> dict[str, Path]:
    specs = stage_specs()
    redacted = ConformanceReport(
        results=[replace(result, detail=redact(result.detail, env))
                 for result in report.results],
        control_results=[replace(result, detail=redact(result.detail, env))
                         for result in report.control_results],
        requests_spent=report.requests_spent)
    report = redacted
    findings = attribute_constructs(report, specs)
    out_dir.mkdir(parents=True, exist_ok=True)
    matrix_path = out_dir / "schema_conformance_matrix.md"
    json_path = out_dir / "schema_conformance.json"
    matrix = "\n".join([
        "# Structured-output conformance matrix",
        "",
        "provider by model by stage. ok accepted, VAL schema validation",
        "rejection, HTTP non-validation HTTP rejection, TIME timeout,",
        "UNREACH transport or credential failure.",
        "",
        "```",
        render_matrix(report),
        "```",
        "",
        "## Requests",
        "",
        "```",
        render_summary(report, plan),
        "```",
        "",
        "## Ranked constructs",
        "",
        "A construct is attributed when the provider named it in the rejection",
        "body, or when the cell was a validation rejection and the construct",
        "is present in the rejected schema and absent from every schema that",
        "same model accepted. An unnamed HTTP rejection, a timeout, a quota",
        "wall, a missing model and an expired credential attribute nothing.",
        "",
        "```",
        render_constructs(findings),
        "```",
        "",
        "## Rejections with no construct attributed",
        "",
        "| provider | model | stage | outcome | detail |",
        "| --- | --- | --- | --- | --- |",
        *[
            f"| {r.endpoint} | {r.model} | {r.stage} | {r.outcome} | "
            f"{r.detail[:140]} |"
            for r in unattributed(report)
        ],
        "",
    ])
    matrix_path.write_text(matrix, encoding="utf-8")
    json_path.write_text(json.dumps({
        "requests_spent": report.requests_spent,
        "budget": plan.budget,
        "results": [result.__dict__ for result in report.results],
        "control_results": [
            result.__dict__ for result in report.control_results],
        "constructs": [
            {"construct": item.construct,
             "models": list(item.broken_models),
             "cells": list(item.broken_cells)}
            for item in findings],
    }, indent=2, sort_keys=True), encoding="utf-8")
    return {"matrix": matrix_path, "json": json_path}

def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Probe harness stage schemas against every configured "
                    "OpenAI-compatible provider.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--out-dir", default="/tmp")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--merge", default=None,
                        help="Fold an earlier JSON artifact into this run so a "
                             "fresh sweep only pays for cells that are still "
                             "missing. No request is repeated.")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    plan = load_plan(ns.config)
    report = asyncio.run(run_probe(plan, concurrency=ns.concurrency))
    specs = stage_specs()
    if ns.merge is not None:
        report = merge_report(report, Path(ns.merge))
    findings = attribute_constructs(report, specs)
    paths = build_artifacts(report, plan, Path(ns.out_dir))
    print(render_matrix(report))
    print()
    print(render_constructs(findings))
    print()
    print(render_summary(report, plan))
    print()
    print(f"matrix: {paths['matrix']}")
    print(f"json:   {paths['json']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())