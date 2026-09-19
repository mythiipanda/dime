from __future__ import annotations

import json
import math
from collections.abc import AsyncIterable, AsyncIterator, Iterable

from v2.api.events import EventType, InternalEvent


def _bounded_public_value(value, *, depth: int = 0):
    if depth > 8:
        return None
    if isinstance(value, str):
        return value[:200_000]
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, list):
        return [_bounded_public_value(item, depth=depth + 1)
                for item in value[:1000]]
    if isinstance(value, dict):
        return {
            str(key)[:1000]: _bounded_public_value(item, depth=depth + 1)
            for key, item in list(value.items())[:256]
        }
    return str(value)[:200_000]


def _public_payload(event: InternalEvent) -> dict:
    payload = event.model_dump(mode="json", exclude={"type"}, exclude_none=True)
    if isinstance(event.type, str) and event.type in {"stage_summary", "plan_update", "evidence_update", "verification_update"}:
        common = {key: payload[key] for key in ("event_id","sequence","emitted_at","phase","status","title","correlation_id","transition","duration_ms") if key in payload}
        allowed = {
            "stage_summary": ("mode","season","entity_count","requirement_count","calculation_count"),
            "plan_update": ("node_count","capabilities","unknown_capability_count"),
            "evidence_update": ("capability","season","as_of","observed_at","rows","qualification","coverage","warning_count"),
            "verification_update": ("round","supported_count","claim_count","missing_count","contradiction_count","repair_count"),
        }[event.type]
        data = payload.get("data", {})
        common["data"] = {key:data[key] for key in allowed if key in data}
        return common
    if event.type == EventType.TOKEN:
        return {"text": ""}
    if event.type == EventType.THOUGHT_STREAM:
        return {key: payload[key] for key in ("node",) if key in payload} | {
            "text": "Working through the evidence...",
        }
    if event.type == EventType.TOOL_RESULT:
        out = {key: payload[key] for key in (
            "node", "name", "status", "rows", "ms", "agent", "event_id",
            "sequence", "emitted_at", "phase", "correlation_id", "transition", "duration_ms",
        ) if key in payload}
        if payload.get("status") == "fail":
            out["error"] = "Tool failed"
        return out
    return payload


def encode_event(event: InternalEvent) -> str:
    payload = _bounded_public_value(_public_payload(event))
    event_name = event.type.value if isinstance(event.type, EventType) else event.type
    return f"event: {event_name}\ndata: {json.dumps(payload, separators=(',', ':'), allow_nan=False)}\n\n"


def encode_events(events: Iterable[InternalEvent]) -> Iterable[str]:
    for event in events:
        yield encode_event(event)


async def stream_events(events: AsyncIterable[InternalEvent]) -> AsyncIterator[str]:
    async for event in events:
        yield encode_event(event)
