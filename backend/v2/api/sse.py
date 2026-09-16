from __future__ import annotations

import json
import math
from collections.abc import AsyncIterable, AsyncIterator, Iterable

from v2.api.events import InternalEvent


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


def encode_event(event: InternalEvent) -> str:
    payload = event.model_dump(mode="json", exclude={"type"}, exclude_none=True)
    payload = _bounded_public_value(payload)
    return f"event: {event.type.value}\ndata: {json.dumps(payload, separators=(',', ':'), allow_nan=False)}\n\n"


def encode_events(events: Iterable[InternalEvent]) -> Iterable[str]:
    for event in events:
        yield encode_event(event)


async def stream_events(events: AsyncIterable[InternalEvent]) -> AsyncIterator[str]:
    async for event in events:
        yield encode_event(event)
