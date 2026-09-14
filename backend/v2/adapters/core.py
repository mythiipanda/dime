"""Invoke v1 tools and normalize their payloads into EvidenceEnvelopes."""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from ..contracts import EntityRef, EvidenceEnvelope
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
    if getattr(tool, "coroutine", None) is not None:
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
    return EvidenceEnvelope(
        evidence_id=evidence_id(spec.name, arguments, rows),
        capability=spec.name,
        source=f"v1:{spec.tool_name}:{meta.get('source', 'unknown')}",
        observed_at=observed_at or datetime.now(timezone.utc),
        season=str(season) if season is not None else None,
        entities=envelope_entities,
        rows=rows,
        units=dict(spec.units),
        metric_definitions=dict(spec.metric_definitions),
        qualification=meta.get("qualification") or spec.qualification,
        coverage=meta.get("coverage"),
        warnings=warnings,
    )


def _default_tools() -> dict[str, Any]:
    from app.tools import v1_tools

    return {tool.name: tool for tool in v1_tools}


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
