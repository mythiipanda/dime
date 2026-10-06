
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
import math
import time

from v2.contracts import EvidenceEnvelope, LiveFallback, PlanNode, TaskSpec
from v2.runtime.interfaces import Capability
from v2.runtime.ledger import LedgerKind, exception_text

_WITHHELD_ARGUMENT_SUFFIXES = (
    "_id", "_ids", "_evidence_id", "_path", "_paths", "_file", "_files",
    "_dir", "_url", "_uri", "_prompt", "_instructions", "_key", "_keys",
    "_token", "_secret", "_password", "_credential", "_credentials",
)
_WITHHELD = object()

@dataclass(frozen=True)
class ArgumentSpec:
    declared: frozenset[str]
    required: tuple[str, ...]
    evidence_satisfied: frozenset[str]

@lru_cache(maxsize=1)
def _argument_specs() -> Mapping[str, ArgumentSpec]:
    from v2.runtime.assembly import capability_catalog

    return {
        name: ArgumentSpec(
            declared=frozenset((entry.get("arguments") or {}).get("properties") or {}),
            required=tuple(sorted((entry.get("arguments") or {}).get("required") or ())),
            evidence_satisfied=frozenset(entry.get("dependent_entity_arguments") or {}),
        )
        for name, entry in capability_catalog().items()
    }

def _argument_spec(capability_name: str) -> ArgumentSpec:
    return _argument_specs().get(
        capability_name, ArgumentSpec(frozenset(), (), frozenset()))

def _is_absent(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return not value
    return False

def argument_counts(capability_name: str, arguments: Mapping[str, Any]) -> tuple[int, int]:
    declared = _argument_spec(capability_name).declared
    return len(arguments), sum(
        1 for key in arguments if key not in declared)

def _publishable_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else _WITHHELD
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and len(value) <= 64:
        items = []
        for item in value:
            published = _publishable_value(item)
            if published is _WITHHELD or isinstance(published, list):
                return _WITHHELD
            items.append(published)
        return items
    return _WITHHELD

def publishable_arguments(
    capability_name: str, arguments: Mapping[str, Any],
) -> list[dict[str, Any]]:
    declared = _argument_spec(capability_name).declared
    rows = []
    for key in sorted(arguments):
        if key not in declared or key.endswith(_WITHHELD_ARGUMENT_SUFFIXES):
            continue
        value = _publishable_value(arguments[key])
        if value is _WITHHELD:
            continue
        rows.append({"name": key, "value": value})
    return rows

def _missing_required_arguments(
    capability_name: str, arguments: Mapping[str, Any],
) -> tuple[str, ...]:
    spec = _argument_spec(capability_name)
    return tuple(
        key for key in spec.required
        if key not in spec.evidence_satisfied and _is_absent(arguments.get(key)))

class RecordedCapability:
    def __init__(self, capability: Capability, ledger: Any, *, turn_id: str, activity=None) -> None:
        if not isinstance(capability.name, str) or not capability.name.strip():
            raise ValueError("recorded capability name must be non-empty")
        if not turn_id.strip():
            raise ValueError("recorded capability turn id must be non-empty")
        task_season_scoped = getattr(capability, "task_season_scoped", True)
        if not isinstance(task_season_scoped, bool):
            raise TypeError("recorded capability task_season_scoped must be boolean")
        self.name = capability.name
        self.task_season_scoped = task_season_scoped
        self._capability = capability
        self._ledger = ledger
        self._turn_id = turn_id
        self._sequence = 0
        self._activity = activity

    def _record_live_fallback(
        self, call_id: str, node_id: str, fallback: LiveFallback,
    ) -> None:
        self._ledger.append(
            LedgerKind.LIVE_FALLBACK,
            turn_id=self._turn_id,
            step_id=node_id,
            call_id=call_id,
            data={
                "capability": self.name,
                "requested_season": fallback.requested_season,
                "warehouse_table": fallback.warehouse_table,
                "warehouse_seasons": list(fallback.warehouse_seasons),
                "live_source": fallback.live_source,
                "outcome": fallback.outcome,
            },
        )

    def validate_arguments(self, node: PlanNode) -> None:
        missing = _missing_required_arguments(self.name, node.arguments)
        if missing:
            raise ValueError(
                f"capability {self.name!r} is missing required arguments: "
                f"{', '.join(missing)}")
        validator = getattr(self._capability, "validate_arguments", None)
        if validator is not None:
            validator(node)

    async def execute(
        self,
        node: PlanNode,
        task: TaskSpec,
        evidence: Sequence[EvidenceEnvelope],
    ) -> EvidenceEnvelope:
        self._sequence += 1
        call_id = f"tool:{self._turn_id}:{node.id}:{self._sequence}"
        data = {
            "name": self.name,
            "args": {
                "node": node.model_dump(mode="json"),
                "task": task.model_dump(mode="json"),
                "evidence_ids": [item.evidence_id for item in evidence],
            },
        }
        self._ledger.append(
            LedgerKind.TOOL_CALL,
            turn_id=self._turn_id,
            step_id=node.id,
            call_id=call_id,
            data=data,
        )
        if self._activity is not None:
            try:
                argument_count, unknown_argument_count = argument_counts(
                    self.name, node.arguments)
                self._activity({"kind":"tool_call","phase":"execute","status":"running","title":"Tool running","transition":"started","correlation_id":call_id,"data":{"name":self.name,"arguments":publishable_arguments(self.name,node.arguments),"argument_count":argument_count,"unknown_argument_count":unknown_argument_count}})
            except Exception:
                pass
        started = time.perf_counter()
        try:
            self.validate_arguments(node)
            result = await self._capability.execute(node, task, evidence)
            if not isinstance(result, EvidenceEnvelope):
                raise TypeError("capability must return EvidenceEnvelope")
            result = EvidenceEnvelope.model_validate(result.model_dump())
            if result.capability != self.name:
                raise ValueError(
                    f"capability returned {result.capability!r}, expected {self.name!r}")
            expected_lineage = [item.evidence_id for item in evidence]
            if result.lineage != expected_lineage:
                raise ValueError("capability result lineage does not match its inputs")
            if result.evidence_id in expected_lineage:
                raise ValueError("capability result cannot reuse an input evidence id")
        except BaseException as exc:
            fallback = getattr(exc, "fallback", None)
            if isinstance(fallback, LiveFallback):
                self._record_live_fallback(call_id, node.id, fallback)
            self._ledger.append(
                LedgerKind.TOOL_RESULT,
                turn_id=self._turn_id,
                step_id=node.id,
                call_id=call_id,
                data={"status": "failed", "error": exception_text(exc),
                      "duration_ms": max(0, round(
                          (time.perf_counter() - started) * 1000))},
            )
            if self._activity is not None:
                try:
                    self._activity({"kind":"tool_result","phase":"execute","status":"failed","title":"Tool failed","transition":"failed","correlation_id":call_id,"duration_ms":max(0,round((time.perf_counter()-started)*1000)),"data":{"name":self.name,"rows":None}})
                except Exception:
                    pass
            raise
        if result.live_fallback is not None:
            self._record_live_fallback(call_id, node.id, result.live_fallback)
        self._ledger.append(
            LedgerKind.TOOL_RESULT,
            turn_id=self._turn_id,
            step_id=node.id,
            call_id=call_id,
            data={"status": "ok", "evidence": result.model_dump(mode="json"),
                  "duration_ms": max(0, round(
                      (time.perf_counter() - started) * 1000))},
        )
        if self._activity is not None:
            rows=result.rows
            try:
                self._activity({"kind":"tool_result","phase":"execute","status":"complete","title":"Tool complete","transition":"succeeded","correlation_id":call_id,"duration_ms":max(0,round((time.perf_counter()-started)*1000)),"data":{"name":self.name,"rows":len(rows) if isinstance(rows,list) else None}})
            except Exception:
                pass
        return result
