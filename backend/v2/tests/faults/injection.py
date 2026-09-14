from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


class InjectedTimeout(TimeoutError):
    pass


class InjectedToolFailure(RuntimeError):
    pass


class InjectedVerifierRejection(RuntimeError):
    pass


@dataclass
class FaultInjector:
    faults: dict[str, list[BaseException]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    async def call(self, point: str, operation: Callable[[], Awaitable[Any]]) -> Any:
        self.calls.append(point)
        queued = self.faults.get(point, [])
        if queued:
            raise queued.pop(0)
        return await operation()

    def inject(self, point: str, error: BaseException) -> None:
        self.faults.setdefault(point, []).append(error)


@dataclass
class MemoryCheckpoint:
    completed: set[str] = field(default_factory=set)
    evidence: dict[str, Any] = field(default_factory=dict)

    def save(self, node_id: str, evidence: Any) -> None:
        self.completed.add(node_id)
        self.evidence[node_id] = evidence


async def run_nodes(node_ids: list[str], checkpoint: MemoryCheckpoint,
                    injector: FaultInjector,
                    execute: Callable[[str], Awaitable[Any]]) -> MemoryCheckpoint:
    for node_id in node_ids:
        if node_id in checkpoint.completed:
            continue
        result = await injector.call(f"tool:{node_id}", lambda: execute(node_id))
        checkpoint.save(node_id, result)
        await asyncio.sleep(0)
    return checkpoint
