from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence

from v2.contracts import EvidenceEnvelope, Plan, PlanNode, PlanStatus, TaskSpec
from v2.runtime.checkpoints import CheckpointStore, ExecutionCheckpoint
from v2.runtime.interfaces import Capability
from v2.runtime.models import ExecutionResult
from v2.domain.evidence import admit_evidence


class PlanExecutor:
    def __init__(
        self,
        capabilities: Mapping[str, Capability],
        *,
        max_concurrency: int = 4,
        max_failures: int | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        if max_failures is not None and max_failures < 1:
            raise ValueError("max_failures must be positive")
        self._capabilities = dict(capabilities)
        self._max_concurrency = max_concurrency
        self._max_failures = max_failures
        self._checkpoint_store = checkpoint_store

    async def execute(
        self, task: TaskSpec, plan: Plan, *, run_id: str | None = None
    ) -> ExecutionResult:
        self._preflight(task, plan)
        checkpoint = (
            self._checkpoint_store.load(run_id)
            if self._checkpoint_store is not None and run_id is not None
            else None
        )
        if checkpoint is not None:
            if checkpoint.task != task:
                raise ValueError("checkpoint task does not match requested task")
            if [node.id for node in checkpoint.plan.nodes] != [
                node.id for node in plan.nodes
            ]:
                raise ValueError("checkpoint plan does not match requested plan")
            nodes = {
                node.id: node.model_copy(deep=True) for node in checkpoint.plan.nodes
            }
            for node in nodes.values():
                if node.status == PlanStatus.RUNNING:
                    node.status = PlanStatus.PENDING
            evidence_by_node = dict(checkpoint.evidence_by_node)
            attempts = {
                node_id: checkpoint.attempts.get(node_id, 0) for node_id in nodes
            }
            errors = {key: list(value) for key, value in checkpoint.errors.items()}
        else:
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

            self._save_checkpoint(
                run_id, task, plan, nodes, evidence_by_node, attempts, errors
            )
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
                for node in batch:
                    node.status = PlanStatus.RUNNING
                self._save_checkpoint(
                    run_id, task, plan, nodes, evidence_by_node, attempts, errors
                )
                tasks = [
                    asyncio.create_task(
                        self._run_node(node, task, evidence_by_node, attempts, errors)
                    )
                    for node in batch
                ]
                for completed in asyncio.as_completed(tasks):
                    node, envelope = await completed
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
                    self._save_checkpoint(
                        run_id, task, plan, nodes, evidence_by_node, attempts, errors
                    )

            if self._max_failures is not None and failures >= self._max_failures:
                for node in nodes.values():
                    if node.status == PlanStatus.PENDING:
                        node.status = PlanStatus.SKIPPED
                break
            if not progressed:
                raise RuntimeError("validated plan made no execution progress")

        completed_plan = Plan(nodes=[nodes[node.id] for node in plan.nodes])
        result = ExecutionResult(
            plan=completed_plan,
            evidence=[
                evidence_by_node[node.id]
                for node in plan.nodes
                if node.id in evidence_by_node
            ],
            attempts=attempts,
            errors=errors,
        )
        if (self._checkpoint_store is not None and run_id is not None
                and all(node.status in {
                    PlanStatus.COMPLETE, PlanStatus.FAILED, PlanStatus.SKIPPED
                } for node in completed_plan.nodes)):
            self._checkpoint_store.delete(run_id)
        return result

    def _preflight(self, task: TaskSpec, plan: Plan) -> None:
        selected: set[str] = set()
        for node in plan.nodes:
            if node.status != PlanStatus.PENDING:
                raise ValueError(
                    f"new plan node {node.id!r} must start pending, got "
                    f"{node.status.value!r}")
            matches = [name for name in node.capability_hints
                       if name in self._capabilities]
            if len(matches) != 1:
                raise ValueError(
                    f"plan node {node.id!r} must select exactly one registered "
                    f"capability; got {matches!r}")
            selected.add(matches[0])
            capability = self._capabilities[matches[0]]
            validator = getattr(capability, "validate_arguments", None)
            if validator is not None:
                try:
                    validator(node)
                except Exception as exc:
                    raise ValueError(
                        f"invalid arguments for plan node {node.id!r}: {exc}") from exc
            if matches[0] == "web_fetch":
                parents = [item for item in node.depends_on
                           if self._selected_name(plan, item) == "web_search"]
                if len(parents) != 1 or len(node.depends_on) != 1:
                    raise ValueError(
                        f"web_fetch node {node.id!r} requires exactly one "
                        "web_search dependency")
        missing = sorted(set(task.required_evidence) - selected)
        if missing:
            raise ValueError(
                f"plan does not cover required evidence: {missing}")

    def _selected_name(self, plan: Plan, node_id: str) -> str | None:
        parent = next(item for item in plan.nodes if item.id == node_id)
        matches = [name for name in parent.capability_hints
                   if name in self._capabilities]
        return matches[0] if len(matches) == 1 else None

    def _save_checkpoint(
        self,
        run_id: str | None,
        task: TaskSpec,
        original_plan: Plan,
        nodes: Mapping[str, PlanNode],
        evidence_by_node: Mapping[str, EvidenceEnvelope],
        attempts: Mapping[str, int],
        errors: Mapping[str, list[str]],
    ) -> None:
        if self._checkpoint_store is None or run_id is None:
            return
        self._checkpoint_store.save(
            ExecutionCheckpoint(
                run_id=run_id,
                task=task,
                plan=Plan(nodes=[nodes[node.id] for node in original_plan.nodes]),
                evidence_by_node=dict(evidence_by_node),
                attempts=dict(attempts),
                errors={key: list(value) for key, value in errors.items()},
            )
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
        for _ in range(node.max_attempts):
            attempts[node.id] += 1
            try:
                result = await capability.execute(node, task, parent_evidence)
                task_season_scoped = getattr(
                    capability, "task_season_scoped", True)
                result = result.model_copy(update={
                    "task_season_scoped": task_season_scoped,
                })
                required_season = (
                    task.season.value
                    if task.season and task_season_scoped
                    else None
                )
                result = admit_evidence(result, required_season=required_season)
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
