"""Invoke v1 tools and normalize their payloads into EvidenceEnvelopes."""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from ..contracts import EntityRef, EvidenceEnvelope
from ..domain.evidence import iter_values
from .capabilities import CAPABILITIES, Capability


class AdapterError(RuntimeError):
    """The underlying v1 tool failed or returned an unusable payload."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def evidence_id(capability: str, arguments: Mapping[str, Any], rows: Any) -> str:
    """Stable id: identical capability + arguments + payload dedupe to one id."""
    digest = hashlib.sha256(_canonical(
        {"capability": capability, "arguments": dict(arguments), "rows": rows}
    ).encode()).hexdigest()
    return f"{capability}:{digest[:16]}"


async def ainvoke_tool(tool: Any, arguments: Mapping[str, Any]) -> dict[str, Any]:
    if hasattr(tool, "ainvoke"):
        result = await tool.ainvoke(dict(arguments))
    elif hasattr(tool, "invoke"):
        result = await asyncio.to_thread(tool.invoke, dict(arguments))
    else:
        result = tool(**dict(arguments))
        if inspect.isawaitable(result):
            result = await result
    if not isinstance(result, dict):
        raise AdapterError(
            f"unexpected result type {type(result).__name__}")
    return result


def invoke_tool(tool: Any, arguments: Mapping[str, Any]) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(ainvoke_tool(tool, arguments))
    raise AdapterError(
        "invoke_tool cannot block inside a running event loop; "
        "use acall_capability")


def build_envelope(
    spec: Capability,
    arguments: Mapping[str, Any],
    result: dict[str, Any],
    *,
    entities: Iterable[EntityRef] | None = None,
    observed_at: datetime | None = None,
) -> EvidenceEnvelope:
    if not result.get("ok"):
        raise AdapterError(
            f"{spec.tool_name}: {result.get('error') or 'unknown error'}")
    rows = result.get("rows")
    if rows is None:
        raise AdapterError(f"{spec.tool_name}: result carries no rows")
    meta = result.get("meta") or {}
    season = meta.get("season")
    if season is None and spec.season_arg:
        season = arguments.get(spec.season_arg)
    warnings = list(meta.get("warnings") or [])
    if result.get("ambiguity_note"):
        warnings.append(result["ambiguity_note"])
    if isinstance(rows, list) and not rows:
        warnings.append("empty result set")
    envelope_entities = list(entities or [])
    if spec.extract_entities is not None:
        envelope_entities = spec.extract_entities(rows) + envelope_entities
    vintages = {
        str(key): str(value).split(" (", 1)[0]
        for key, value in meta.items()
        if str(key).endswith("_season") and value is not None
    }
    return EvidenceEnvelope(
        evidence_id=evidence_id(spec.name, arguments, rows),
        capability=spec.name,
        source=f"{spec.source_prefix}:{spec.tool_name}:{meta.get('source', 'unknown')}",
        observed_at=observed_at or datetime.now(timezone.utc),
        season=str(season) if season is not None else None,
        vintages=vintages,
        task_season_scoped=spec.task_season_scoped,
        entities=envelope_entities,
        rows=rows,
        units={key: unit for key, unit in spec.units.items()
               if any(key.casefold() == item.path.rsplit(".", 1)[-1].casefold()
                      for item in _row_values(rows))},
        metric_definitions=dict(spec.metric_definitions),
        qualification=meta.get("qualification") or spec.qualification,
        coverage=meta.get("coverage") or spec.coverage,
        warnings=warnings,
    )


def _row_values(rows: Any):
    envelope = EvidenceEnvelope(
        evidence_id="row-scan", capability="row-scan", source="runtime",
        observed_at=datetime.now(timezone.utc), rows=rows)
    return iter_values(envelope)


def _default_tools() -> dict[str, Any]:
    from app.tools import v1_tools

    from . import coverage

    registry = {tool.name: tool for tool in v1_tools}
    registry["metric_coverage"] = coverage.metric_coverage
    return registry


async def acall_capability(
    name: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    entities: Iterable[EntityRef] | None = None,
    tools: Mapping[str, Any] | None = None,
) -> EvidenceEnvelope:
    spec = CAPABILITIES.get(name)
    if spec is None:
        raise AdapterError(f"unknown capability {name!r}")
    registry = tools if tools is not None else _default_tools()
    tool = registry.get(spec.tool_name)
    if tool is None:
        raise AdapterError(f"v1 tool {spec.tool_name!r} not available")
    result = await ainvoke_tool(tool, arguments or {})
    return build_envelope(spec, arguments or {}, result, entities=entities)


def call_capability(
    name: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    entities: Iterable[EntityRef] | None = None,
    tools: Mapping[str, Any] | None = None,
) -> EvidenceEnvelope:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            acall_capability(name, arguments, entities=entities, tools=tools))
    raise AdapterError(
        "call_capability cannot block inside a running event loop; "
        "use acall_capability")

class ToolCapability:
    def __init__(
        self,
        name: str,
        *,
        tools: Mapping[str, Any] | None = None,
        arguments: Callable[[Any, Any, Iterable[EvidenceEnvelope]], Mapping[str, Any]] | None = None,
    ) -> None:
        if name not in CAPABILITIES:
            raise AdapterError(f"unknown capability {name!r}")
        self.name = name
        self.task_season_scoped = CAPABILITIES[name].task_season_scoped
        self._tools = tools
        self._arguments = arguments or (
            lambda node, task, evidence: _task_arguments(
                self.name, node, task, evidence))

    def validate_arguments(self, node: Any) -> None:
        registry = self._tools if self._tools is not None else _default_tools()
        tool = registry.get(CAPABILITIES[self.name].tool_name)
        schema = getattr(tool, "args_schema", None)
        if schema is not None:
            schema.model_validate(dict(getattr(node, "arguments", {}) or {}))

    async def execute(
        self,
        node: Any,
        task: Any,
        evidence: Iterable[EvidenceEnvelope],
    ) -> EvidenceEnvelope:
        arguments = dict(self._arguments(node, task, evidence))
        return await acall_capability(self.name, arguments, tools=self._tools)


def _task_arguments(name: str, node: Any, task: Any, evidence: Iterable[EvidenceEnvelope]) -> dict[str, Any]:
    arguments = dict(getattr(node, "arguments", {}) or {})
    season = getattr(task, "season", None)
    if season is not None:
        spec = CAPABILITIES[name]
        if spec.season_arg and spec.season_arg not in arguments:
            arguments[spec.season_arg] = season.value
    if name == "trades" and "season" not in arguments:
        for item in evidence:
            salary_season = item.vintages.get("salary_season")
            if salary_season is None and item.capability == "contracts":
                salary_season = item.season
            if salary_season:
                arguments["season"] = salary_season
                break
    return arguments
