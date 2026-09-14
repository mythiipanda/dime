from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence

from v2.contracts import EvidenceEnvelope, Plan, PlanNode, PlanStatus, TaskSpec
from v2.runtime.interfaces import Capability
from v2.runtime.models import ExecutionResult


class PlanExecutor:
    def __init__(
        self,
        capabilities: Mapping[str, Capability],
        *,
        max_concurrency: int = 4,
        max_failures: int | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        if max_failures is not None and max_failures < 1:
            raise ValueError("max_failures must be positive")
        self._capabilities = dict(capabilities)
        self._max_concurrency = max_concurrency
        self._max_failures = max_failures

    async def execute(self, task: TaskSpec, plan: Plan) -> ExecutionResult:
        nodes = {node.id: node.model_copy(deep=True) for node in plan.nodes}
        evidence_by_node: dict[str, EvidenceEnvelope] = {}
        attempts = {node_id: 0 for node_id in nodes}
        errors: dict[str, list[str]] = {}
        failures = 0

        while any(node.status == PlanStatus.PENDING for node in nodes.values()):
            progressed = False
            for node in nodes.values():
                if node.status != PlanStatus.PENDING:
                    continue
                dependency_states = [nodes[parent].status for parent in node.depends_on]
                if any(
                    state in (PlanStatus.FAILED, PlanStatus.SKIPPED)
                    for state in dependency_states
                ):
                    node.status = PlanStatus.SKIPPED
                    progressed = True

            ready = [
                node
                for node in nodes.values()
                if node.status == PlanStatus.PENDING
                and all(
                    nodes[parent].status == PlanStatus.COMPLETE
                    for parent in node.depends_on
                )
            ]
            if ready:
                progressed = True
                batch = ready[: self._max_concurrency]
                results = await asyncio.gather(
                    *(
                        self._run_node(node, task, evidence_by_node, attempts, errors)
                        for node in batch
                    )
                )
                for node, envelope in results:
                    if envelope is None:
                        node.status = PlanStatus.FAILED
                        failures += 1
                    else:
                        if envelope.evidence_id in {
                            item.evidence_id for item in evidence_by_node.values()
                        }:
                            node.status = PlanStatus.FAILED
                            errors.setdefault(node.id, []).append(
                                f"duplicate evidence id: {envelope.evidence_id}"
                            )
                            failures += 1
                        else:
                            node.status = PlanStatus.COMPLETE
                            evidence_by_node[node.id] = envelope

            if self._max_failures is not None and failures >= self._max_failures:
                for node in nodes.values():
                    if node.status == PlanStatus.PENDING:
                        node.status = PlanStatus.SKIPPED
                break
            if not progressed:
                raise RuntimeError("validated plan made no execution progress")

        completed_plan = Plan(nodes=[nodes[node.id] for node in plan.nodes])
        return ExecutionResult(
            plan=completed_plan,
            evidence=[
                evidence_by_node[node.id]
                for node in plan.nodes
                if node.id in evidence_by_node
            ],
            attempts=attempts,
            errors=errors,
        )

    async def _run_node(
        self,
        node: PlanNode,
        task: TaskSpec,
        evidence_by_node: Mapping[str, EvidenceEnvelope],
        attempts: dict[str, int],
        errors: dict[str, list[str]],
    ) -> tuple[PlanNode, EvidenceEnvelope | None]:
        capability = self._select_capability(node)
        if capability is None:
            errors.setdefault(node.id, []).append(
                "no registered capability matches capability hints"
            )
            return node, None
        parent_evidence: Sequence[EvidenceEnvelope] = tuple(
            evidence_by_node[parent] for parent in node.depends_on
        )
        node.status = PlanStatus.RUNNING
        for _ in range(node.max_attempts):
            attempts[node.id] += 1
            try:
                result = await capability.execute(node, task, parent_evidence)
                if result.capability != capability.name:
                    raise ValueError(
                        f"capability returned {result.capability!r}, expected {capability.name!r}"
                    )
                return node, result
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                errors.setdefault(node.id, []).append(f"{type(exc).__name__}: {exc}")
        return node, None

    def _select_capability(self, node: PlanNode) -> Capability | None:
        return next(
            (
                self._capabilities[name]
                for name in node.capability_hints
                if name in self._capabilities
            ),
            None,
        )
