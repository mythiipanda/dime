from __future__ import annotations

import json
from collections.abc import AsyncIterable, AsyncIterator, Iterable

from v2.api.events import InternalEvent


def encode_event(event: InternalEvent) -> str:
    payload = event.model_dump(mode="json", exclude={"type"}, exclude_none=True)
    return f"event: {event.type.value}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def encode_events(events: Iterable[InternalEvent]) -> Iterable[str]:
    for event in events:
        yield encode_event(event)


async def stream_events(events: AsyncIterable[InternalEvent]) -> AsyncIterator[str]:
    async for event in events:
        yield encode_event(event)
