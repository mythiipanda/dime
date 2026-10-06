from __future__ import annotations

import anyio
import asyncio
import hashlib
import inspect
import re
import json
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from ..contracts import EntityRef, EvidenceEnvelope, LiveFallback, canonical_entity_id
from ..contracts import WINDOW_ARGUMENT_NAMES, window_of_arguments
from ..domain.evidence import iter_values
from .capabilities import CAPABILITIES, Capability

class AdapterError(RuntimeError):
    pass

class LiveFallbackEmpty(AdapterError):

    def __init__(self, message: str, fallback: LiveFallback) -> None:
        super().__init__(message)
        self.fallback = fallback

def _warehouse_seasons(table: str) -> list[str]:
    from . import coverage

    return sorted(
        season for season in coverage.table_seasons(table)
        if coverage.parse_season_start(season) is not None)

def resolve_live_fallback(spec: Capability, meta: Mapping[str, Any]) -> LiveFallback | None:
    marker = meta.get("live_fallback")
    if marker is None:
        return None
    if not isinstance(marker, Mapping):
        raise AdapterError(f"{spec.tool_name}: live fallback marker must be an object")
    try:
        return LiveFallback(
            warehouse_table=marker.get("table"),
            requested_season=marker.get("requested_season"),
            warehouse_seasons=_warehouse_seasons(marker.get("table")),
            live_source=marker.get("live_source"),
            outcome=marker.get("outcome"),
        )
    except (TypeError, ValueError) as exc:
        raise AdapterError(
            f"{spec.tool_name}: invalid live fallback marker: {exc}") from exc

def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))

def evidence_id(
    capability: str, arguments: Mapping[str, Any], rows: Any,
    *, source_revision: Mapping[str, Any] | None = None,
) -> str:
    digest = hashlib.sha256(_canonical({
        "capability": capability,
        "arguments": dict(arguments),
        "source_revision": dict(source_revision or {}),
        "rows": rows,
    }).encode()).hexdigest()
    return f"{capability}:{digest[:16]}"

async def ainvoke_tool(tool: Any, arguments: Mapping[str, Any]) -> dict[str, Any]:
    ainvoke = getattr(tool, "ainvoke", None)
    invoke = getattr(tool, "invoke", None)
    if callable(ainvoke):
        result = await ainvoke(dict(arguments))
    elif callable(invoke):
        result = await anyio.to_thread.run_sync(invoke, dict(arguments))
    elif callable(tool):
        result = tool(**dict(arguments))
        if inspect.isawaitable(result):
            result = await result
    else:
        raise AdapterError("tool must be callable or expose invoke/ainvoke")
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

def _live_fallback_miss(spec: Capability, fallback: LiveFallback,
                        reported: str = "") -> str:
    on_hand = ", ".join(fallback.warehouse_seasons) or "none"
    message = (
        f"{spec.tool_name}: {spec.name} has no warehouse rows for the "
        f"{fallback.requested_season} season in {fallback.warehouse_table} "
        f"and the {fallback.live_source} live source returned nothing, so no "
        f"answer exists for {fallback.requested_season} (warehouse seasons on "
        f"hand: {on_hand})")
    return f"{message}; tool reported: {reported}" if reported else message

def build_envelope(
    spec: Capability,
    arguments: Mapping[str, Any],
    result: dict[str, Any],
    *,
    entities: Iterable[EntityRef] | None = None,
    observed_at: datetime | None = None,
) -> EvidenceEnvelope:
    raw_meta = result.get("meta")
    if raw_meta is not None and not isinstance(raw_meta, Mapping):
        raise AdapterError(f"{spec.tool_name}: result meta must be an object")
    meta = raw_meta or {}
    live_fallback = resolve_live_fallback(spec, meta)
    failed = result.get("ok") is not True
    if (live_fallback is not None and live_fallback.outcome == "empty"
            and (failed or not result.get("rows"))):
        raise LiveFallbackEmpty(
            _live_fallback_miss(
                spec, live_fallback,
                str(result.get("error") or "unknown error") if failed else ""),
            live_fallback)
    if failed:
        raise AdapterError(
            f"{spec.tool_name}: {result.get('error') or 'unknown error'}")
    rows = result.get("rows")
    if rows is None and spec.name == "game_prediction":
        fields = ("matchup", "estimate", "inputs", "methodology",
                  "assumptions", "limitations")
        if isinstance(result.get("estimate"), Mapping):
            rows = {key: result[key] for key in fields if key in result}
    if rows is None:
        raise AdapterError(f"{spec.tool_name}: result carries no rows")
    if spec.name == "contracts":
        if not isinstance(rows, Mapping):
            raise AdapterError(f"{spec.tool_name}: contract ledger must be an object")
        payroll = rows.get("payroll")
        players = rows.get("players")
        if (isinstance(payroll, bool) or not isinstance(payroll, (int, float))
                or payroll <= 0 or not isinstance(players, list) or not players):
            raise AdapterError(
                f"{spec.tool_name}: contract ledger has no usable payroll roster")
    row_warnings: list[str] = []
    if spec.name == "trade_value" and isinstance(rows, Mapping):
        data_gaps = rows.get("data_gaps")
        if data_gaps is not None:
            if (not isinstance(data_gaps, list)
                    or any(not isinstance(value, str) or not value.strip()
                           for value in data_gaps)):
                raise AdapterError(
                    f"{spec.tool_name}: data_gaps must be an array of non-empty text")
            row_warnings.extend(data_gaps)
    declared_sources = {
        token.strip() for token in str(meta.get("source") or "").split("+")
        if token.strip()
    }
    if "warehouse" in declared_sources and not (
            "warehouse_id" in meta or "warehouse_sha256" in meta):
        from shared import store as _store
        bound_identity = _store.warehouse_identity()
        meta = {**meta, **bound_identity}
    has_warehouse_id = "warehouse_id" in meta
    has_warehouse_sha = "warehouse_sha256" in meta
    lineage_kind_present = "lineage_kind" in meta
    if lineage_kind_present and meta.get("lineage_kind") != "live":
        raise AdapterError(f"{spec.tool_name}: unknown source identity kind")
    is_live = meta.get("lineage_kind") == "live"
    if has_warehouse_id != has_warehouse_sha:
        raise AdapterError(f"{spec.tool_name}: partial warehouse source identity")
    if has_warehouse_id and has_warehouse_sha:
        warehouse_id = meta.get("warehouse_id")
        warehouse_sha = meta.get("warehouse_sha256")
        if warehouse_id not in {"frozen-eval", "configured-runtime"}:
            raise AdapterError(f"{spec.tool_name}: invalid warehouse source identity")
        if (not isinstance(warehouse_sha, str)
                or re.fullmatch(r"[0-9a-f]{64}", warehouse_sha) is None):
            raise AdapterError(f"{spec.tool_name}: invalid warehouse source identity")
    if is_live and (has_warehouse_id or has_warehouse_sha):
        raise AdapterError(f"{spec.tool_name}: conflicting source identity markers")
    if is_live and not meta.get("source"):
        raise AdapterError(f"{spec.tool_name}: live source identity missing")
    season = meta.get("season")
    requested_season = arguments.get(spec.season_arg) if spec.season_arg else None
    if season is None:
        season = requested_season
    elif (spec.task_season_scoped and requested_season is not None
          and str(season) != str(requested_season)):
        raise AdapterError(
            f"{spec.tool_name}: response season {season} does not match "
            f"requested season {requested_season}")
    warning_values = meta.get("warnings") or []
    if isinstance(warning_values, str):
        warnings = [warning_values]
    elif isinstance(warning_values, (list, tuple)):
        warnings = [str(value) for value in warning_values]
    else:
        raise AdapterError(f"{spec.tool_name}: warnings must be text or an array")
    warnings = [*row_warnings, *warnings]
    if not meta.get("source"):
        warnings.append("source identity not declared by tool")
    singular_warning = meta.get("warning")
    if singular_warning:
        warnings.append(str(singular_warning))
    for key in ("sample_warning", "data_note"):
        limitation = meta.get(key)
        if limitation is not None:
            if not isinstance(limitation, str):
                raise AdapterError(
                    f"{spec.tool_name}: {key} must be non-empty text")
            if not limitation.strip():
                raise AdapterError(
                    f"{spec.tool_name}: {key} must be non-empty text")
            warnings.append(limitation)
    stale = (None if spec.name == "warehouse_freshness"
             else meta.get("stale"))
    if stale is not None and not isinstance(stale, bool):
        raise AdapterError(f"{spec.tool_name}: stale marker must be boolean")
    source_error = meta.get("live_error") or meta.get("error")
    if source_error is not None:
        if not isinstance(source_error, str) or not source_error.strip():
            raise AdapterError(f"{spec.tool_name}: source error must be non-empty text")
        label = "stale cached fallback" if stale else "source limitation"
        warnings.append(f"{label}: {source_error[:4000]}")
    elif stale:
        warnings.append("stale cached fallback")
    if result.get("ambiguity_note"):
        warnings.append(result["ambiguity_note"])
    if isinstance(rows, list) and not rows:
        warnings.append("empty result set")
    as_of = None
    for key in ("as_of", "salary_date", "production_date", "fetched_at"):
        value = meta.get(key)
        if value:
            try:
                as_of = date.fromisoformat(str(value).split("T", 1)[0])
            except ValueError:
                warnings.append(f"unparseable {key}: {value}")
            break
    served_window = window_of_arguments(arguments, season)
    envelope_entities = list(entities or [])
    if spec.extract_entities is not None:
        envelope_entities = spec.extract_entities(rows) + envelope_entities
    deduplicated_entities: dict[tuple[str, str], EntityRef] = {}
    for entity in envelope_entities:
        key = (entity.type, entity.id)
        existing = deduplicated_entities.get(key)
        if existing is not None and existing != entity:
            if canonical_entity_id(entity.type, existing.display_name) != canonical_entity_id(entity.type, entity.display_name):
                raise AdapterError(
                    f"conflicting entity identity {entity.type}:{entity.id}")
        deduplicated_entities[key] = entity
    envelope_entities = list(deduplicated_entities.values())
    vintages = {
        str(key): str(value).split(" (", 1)[0]
        for key, value in meta.items()
        if str(key).endswith("_season") and value is not None
    }
    return EvidenceEnvelope(
        evidence_id=evidence_id(
            spec.name, arguments, rows,
            source_revision={
                "source": meta.get("source", "unknown"),
                "as_of": as_of.isoformat() if as_of else None,
                "vintages": vintages,
            },
        ),
        capability=spec.name,
        source=f"{spec.source_prefix}:{spec.tool_name}:{meta.get('source', 'unknown')}",
        observed_at=observed_at or datetime.now(timezone.utc),
        season=str(season) if season is not None else None,
        vintages=vintages,
        task_season_scoped=spec.task_season_scoped,
        as_of=as_of,
        window_start=served_window[0],
        window_end=served_window[1],
        entities=envelope_entities,
        rows=rows,
        units={key: unit for key, unit in spec.units.items()
               if any(key.casefold() in {
                   segment.split("[", 1)[0].casefold()
                   for segment in item.path.split(".")
               } for item in _row_values(rows))},
        metric_definitions={
            **dict(spec.metric_definitions),
            **({"__requested_metric__": str(meta["requested_metric"])}
               if meta.get("requested_metric") else {}),
        },
        qualification=meta.get("qualification") or spec.qualification,
        coverage=(meta.get("coverage") or meta.get("coverage_note")
                  or spec.coverage),
        warnings=warnings,
        source_identity=(
            {"kind": "composite",
             "warehouse_id": str(meta["warehouse_id"]),
             "sha256": str(meta["warehouse_sha256"]),
             "live_sources": sorted(declared_sources - {"warehouse"})}
            if has_warehouse_id and has_warehouse_sha
            and "warehouse" in declared_sources
            and declared_sources - {"warehouse"} else
            {"kind": "warehouse", "warehouse_id": str(meta["warehouse_id"]),
             "sha256": str(meta["warehouse_sha256"])}
            if has_warehouse_id and has_warehouse_sha else
            {"kind": "live", "source": str(meta["source"])}
            if meta.get("lineage_kind") == "live" and meta.get("source") else None),
        live_fallback=live_fallback,
    )

def _row_values(rows: Any):
    envelope = EvidenceEnvelope(
        evidence_id="row-scan", capability="row-scan", source="runtime",
        observed_at=datetime.now(timezone.utc), rows=rows)
    return iter_values(envelope)

def _default_tools() -> dict[str, Any]:
    from shared.tools import v1_tools

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
        self.dependent_entity_arguments = dict(
            CAPABILITIES[name].dependent_entity_arguments)
        if arguments is not None and not callable(arguments):
            raise TypeError("capability arguments adapter must be callable")
        self._tools = tools
        self._arguments = arguments or (
            lambda node, task, evidence: _task_arguments(
                self.name, node, task, evidence))

    def _validated_arguments(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        registry = self._tools if self._tools is not None else _default_tools()
        tool = registry.get(CAPABILITIES[self.name].tool_name)
        schema = getattr(tool, "args_schema", None)
        values = dict(arguments)
        if schema is None:
            return values
        unsupported = sorted(
            key for key, value in values.items()
            if value is not None and key in WINDOW_ARGUMENT_NAMES
            and key not in schema.model_fields
        )
        if unsupported:
            raise AdapterError(
                f"{CAPABILITIES[self.name].tool_name}: capability {self.name} "
                f"cannot serve date-windowed arguments "
                f"{unsupported}; date-bound questions need date-filtered "
                f"evidence or an explicit gap"
            )
        accepted = {key: value for key, value in values.items()
                    if key in schema.model_fields}
        schema.model_validate(accepted)
        return accepted

    def validate_arguments(self, node: Any) -> None:
        self._validated_arguments(dict(getattr(node, "arguments", {}) or {}))

    async def execute(
        self,
        node: Any,
        task: Any,
        evidence: Iterable[EvidenceEnvelope],
    ) -> EvidenceEnvelope:
        raw_arguments = self._arguments(node, task, evidence)
        if not isinstance(raw_arguments, Mapping):
            raise TypeError("capability arguments adapter must return a mapping")
        arguments = self._validated_arguments(raw_arguments)
        result = await acall_capability(self.name, arguments, tools=self._tools)
        return result.model_copy(update={
            "lineage": [item.evidence_id for item in evidence],
        })

def _task_arguments(name: str, node: Any, task: Any, evidence: Iterable[EvidenceEnvelope]) -> dict[str, Any]:
    arguments = dict(getattr(node, "arguments", {}) or {})
    season = getattr(task, "season", None)
    if season is not None:
        spec = CAPABILITIES[name]
        if spec.season_arg and (spec.task_season_scoped
                                or spec.season_arg not in arguments):
            arguments[spec.season_arg] = season.value
    window = CAPABILITIES[name].window_args
    if window is not None:
        start_key, end_key = window
        window_start = getattr(task, "window_start", None)
        window_end = getattr(task, "window_end", None)
        if window_start is not None and not arguments.get(start_key):
            arguments[start_key] = window_start.isoformat()
        if window_end is not None and not arguments.get(end_key):
            arguments[end_key] = window_end.isoformat()
    if name == "trades" and "season" not in arguments:
        for item in evidence:
            salary_season = item.vintages.get("salary_season")
            if salary_season is None and item.capability == "contracts":
                salary_season = item.season
            if salary_season:
                arguments["season"] = salary_season
                break
    declarations = CAPABILITIES[name].dependent_entity_arguments
    for argument, entity_type in declarations.items():
        if arguments.get(argument) is not None:
            continue
        candidates = [entity for item in evidence for entity in item.entities
                      if entity.type == entity_type]
        if candidates:
            arguments[argument] = candidates[0].display_name or candidates[0].id
    if name == "game_prediction":
        teams = [entity for entity in task.entities if entity.type == "team"]
        if len(teams) == 2:
            for key, entity in zip(("a", "b"), teams, strict=True):
                candidate = str(arguments.get(key, "")).strip()
                if candidate not in {entity.id, entity.display_name}:
                    arguments[key] = entity.display_name or entity.id
    return arguments
