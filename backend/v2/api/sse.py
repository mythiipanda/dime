from __future__ import annotations

import asyncio
import json
import math
from collections.abc import AsyncIterable, AsyncIterator

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

def _public_payload(event: InternalEvent, *, diagnostics: bool = False) -> dict | None:
    payload = event.model_dump(mode="json", exclude={"type"}, exclude_none=True)
    if event.type == EventType.BINDING_DIAGNOSTIC:
        if not diagnostics:
            return None
        return payload
    if event.type == EventType.RUN_DIAGNOSTIC:
        if not diagnostics:
            return None
        return payload
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
    if event.type == EventType.STATUS:
        text = str(payload.get("text", ""))
        return {"text": text[:500]}
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

def encode_event(event: InternalEvent, *, diagnostics: bool = False) -> str | None:
    payload = _public_payload(event, diagnostics=diagnostics)
    if payload is None:
        return None
    payload = _bounded_public_value(payload)
    event_name = event.type.value if isinstance(event.type, EventType) else event.type
    return f"event: {event_name}\ndata: {json.dumps(payload, separators=(',', ':'), allow_nan=False)}\n\n"


async def stream_events(events: AsyncIterable[InternalEvent], *, diagnostics: bool = False) -> AsyncIterator[str]:
    async for event in events:
        chunk = encode_event(event, diagnostics=diagnostics)
        if chunk is not None:
            yield chunk

def encode_raw(event_type: str, data: object) -> str:
    return (f"event: {event_type}\ndata: "
            f"{json.dumps(data, separators=(',', ':'), allow_nan=False)}\n\n")

def encode_branch_reuse(*, parent_sequence: int, reused_count: int) -> str:
    if isinstance(parent_sequence, bool) or not isinstance(parent_sequence, int):
        raise TypeError("branch parent sequence must be an integer")
    if isinstance(reused_count, bool) or not isinstance(reused_count, int):
        raise TypeError("branch reused count must be an integer")
    if parent_sequence < 1:
        raise ValueError("branch parent sequence must be positive")
    if reused_count < 1:
        raise ValueError("branch reused count must be positive")
    return encode_raw("branch_reuse", {"parent_sequence": parent_sequence,
                                       "reused_count": reused_count})

def encode_replay_verification(report) -> str:
    payload = _bounded_public_value(report.model_dump(
        mode="json", exclude_none=True))
    return encode_raw("replay_verification", payload)

async def with_heartbeat(
    inner: AsyncIterator[str], interval_s: float = 15.0
) -> AsyncIterator[str]:
    queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=64)

    async def drain() -> None:
        try:
            async for chunk in inner:
                await queue.put(chunk)
        except asyncio.CancelledError:
            raise
        except BaseException:
            await queue.put(None)
            raise
        else:
            await queue.put(None)

    task = asyncio.create_task(drain())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval_s)
            except asyncio.TimeoutError:
                yield encode_raw("ping", {"ok": True})
                continue
            if item is None:
                await task
                return
            yield item
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
