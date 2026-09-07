"""SSE framing. Copied pattern from proven stack. No logic lives here."""

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any
import asyncio
import json


def emit_sse(event_type: str, data: Any) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


async def with_heartbeat(
    inner: AsyncIterator[str], interval_s: float = 15.0
) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def drain() -> None:
        async for chunk in inner:
            await queue.put(chunk)
        await queue.put(None)

    task = asyncio.create_task(drain())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval_s)
            except asyncio.TimeoutError:
                yield emit_sse("ping", {"ok": True})
                continue
            if item is None:
                return
            yield item
    finally:
        task.cancel()
