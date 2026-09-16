from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from v2.contracts import EvidenceEnvelope, PlanNode, TaskSpec
from v2.runtime.interfaces import Capability
from v2.runtime.ledger import LedgerKind


class RecordedCapability:
    def __init__(self, capability: Capability, ledger: Any, *, turn_id: str) -> None:
        if not isinstance(capability.name, str) or not capability.name.strip():
            raise ValueError("recorded capability name must be non-empty")
        if not turn_id.strip():
            raise ValueError("recorded capability turn id must be non-empty")
        self.name = capability.name
        self.task_season_scoped = getattr(capability, "task_season_scoped", True)
        self._capability = capability
        self._ledger = ledger
        self._turn_id = turn_id
        self._sequence = 0

    def validate_arguments(self, node: PlanNode) -> None:
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
        try:
            result = await self._capability.execute(node, task, evidence)
            if not isinstance(result, EvidenceEnvelope):
                raise TypeError("capability must return EvidenceEnvelope")
            if result.capability != self.name:
                raise ValueError(
                    f"capability returned {result.capability!r}, expected {self.name!r}")
            expected_lineage = [item.evidence_id for item in evidence]
            if result.lineage != expected_lineage:
                raise ValueError("capability result lineage does not match its inputs")
            if result.evidence_id in expected_lineage:
                raise ValueError("capability result cannot reuse an input evidence id")
        except BaseException as exc:
            self._ledger.append(
                LedgerKind.TOOL_RESULT,
                turn_id=self._turn_id,
                step_id=node.id,
                call_id=call_id,
                data={"status": "failed", "error": f"{type(exc).__name__}: {exc}"},
            )
            raise
        self._ledger.append(
            LedgerKind.TOOL_RESULT,
            turn_id=self._turn_id,
            step_id=node.id,
            call_id=call_id,
            data={"status": "ok", "evidence": result.model_dump(mode="json")},
        )
        return result
