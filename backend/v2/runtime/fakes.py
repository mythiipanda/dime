from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from v2.contracts import EvidenceEnvelope, PlanNode, TaskSpec


class FakeCapability:
    def __init__(
        self,
        name: str,
        rows: list[dict[str, Any]] | dict[str, Any] | Callable[[PlanNode], Any],
        *,
        failures_before_success: int = 0,
    ) -> None:
        self.name = name
        self.task_season_scoped = True
        self._rows = rows
        self._failures_remaining = failures_before_success

    async def execute(
        self,
        node: PlanNode,
        task: TaskSpec,
        evidence: Sequence[EvidenceEnvelope],
    ) -> EvidenceEnvelope:
        if self._failures_remaining:
            self._failures_remaining -= 1
            raise RuntimeError("injected capability failure")
        rows = self._rows(node) if callable(self._rows) else self._rows
        return EvidenceEnvelope(
            evidence_id=f"evidence:{node.id}",
            capability=self.name,
            source="fake",
            observed_at=datetime.now(UTC),
            season=task.season.value if task.season else None,
            as_of=task.as_of,
            entities=task.entities,
            rows=rows,
            lineage=[item.evidence_id for item in evidence],
        )
