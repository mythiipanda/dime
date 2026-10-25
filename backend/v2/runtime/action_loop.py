from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from v2.adapters.models import (
    StructuredModel, _model_evidence_dump, _validate_draft,
    provider_route_prompt,
)
from v2.contracts import (
    ConversationTurn, DraftReport, EvidenceEnvelope, Plan, PlanNode, TaskSpec,
    VerificationReport, VerificationStatus,
)
from v2.runtime.executor import PlanExecutor, PlanValidationError
from v2.runtime.interfaces import (
    Intake, Verifier, freeze_draft, freeze_evidence_map, freeze_task,
)
from v2.runtime.ledger import LedgerKind, RequestEnvelope, RunLedger
from v2.runtime.loop import close_failed, publish_result
from v2.runtime.models import ExecutionResult, RuntimeResult
from v2.runtime.verifier import merge_verification_reports

class _ActionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

class ToolAction(_ActionBase):
    action: Literal["tool"]
    capability: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)

class AnswerAction(_ActionBase):
    action: Literal["answer"]
    draft: DraftReport

LoopActionPayload = Annotated[ToolAction | AnswerAction, Field(discriminator="action")]

class LoopAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step: LoopActionPayload

class TypedDefect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    message: str

@dataclass
class _LoopState:
    nodes: list[PlanNode] = field(default_factory=list)
    evidence_by_node: dict[str, EvidenceEnvelope] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)
    errors: dict[str, list[str]] = field(default_factory=dict)
    error_codes: dict[str, list[Any]] = field(default_factory=dict)
    used_node_ids: set[str] = field(default_factory=set)
    history: list[dict[str, Any]] = field(default_factory=list)
    defects: list[TypedDefect] = field(default_factory=list)
    last_draft: DraftReport | None = None
    last_verification: VerificationReport | None = None

class ActionLoop:
    def __init__(
        self,
        *,
        model: StructuredModel,
        executor: PlanExecutor,
        mechanical_verifier: Verifier,
        semantic_verifier: Verifier,
        ledger: RunLedger | None,
        tool_catalog: Mapping[str, Any],
        turn_id: str,
        max_actions: int = 4,
        run_timeout_s: float | None = None,
        diagnostics: bool = False,
        provider: str = "offline",
        model_name: str = "scripted",
        planner_version: str = "v2",
    ) -> None:
        if not turn_id.strip():
            raise ValueError("turn_id must be non-empty")
        if not isinstance(max_actions, int) or isinstance(max_actions, bool):
            raise TypeError("max_actions must be an integer")
        if max_actions < 1:
            raise ValueError("max_actions must be positive")
        if (run_timeout_s is not None
                and (isinstance(run_timeout_s, bool)
                     or not isinstance(run_timeout_s, (int, float))
                     or run_timeout_s <= 0)):
            raise ValueError("run_timeout_s must be positive or None")
        if not isinstance(diagnostics, bool):
            raise TypeError("diagnostics must be a boolean")
        self._model = model
        self._executor = executor
        self._mechanical = mechanical_verifier
        self._semantic = semantic_verifier
        self._ledger = ledger
        self._tool_catalog = dict(tool_catalog)
        self._turn_id = turn_id
        self._max_actions = max_actions
        self._run_timeout_s = run_timeout_s
        self._diagnostics = diagnostics
        self._provider = provider
        self._model_name = model_name
        self._planner_version = planner_version
        self._prompt = provider_route_prompt("action_loop", "action_loop")

    def _payload(self, task, evidence, state):
        return {
            "task": task.model_dump(mode="json"),
            "tools": self._tool_catalog,
            "admitted_evidence": [_model_evidence_dump(item) for item in evidence],
            "actions": list(state.history),
            "defects": [item.model_dump(mode="json") for item in state.defects],
            "remaining_actions": self._max_actions - len(state.history),
        }

    def _aggregate(self, state: _LoopState) -> ExecutionResult:
        return ExecutionResult(
            plan=Plan(nodes=list(state.nodes)),
            evidence_by_node=dict(state.evidence_by_node),
            attempts=dict(state.attempts),
            errors=dict(state.errors),
            error_codes=dict(state.error_codes),
        )

    def _publish(self, task, state, draft, verification, started) -> RuntimeResult:
        return publish_result(
            task=task, execution=self._aggregate(state),
            draft=draft, verification=verification,
            evidence={item.evidence_id: item
                      for item in state.evidence_by_node.values()},
            turn_id=self._turn_id,
            turn_started=started, pre_repair_draft=draft,
            pre_repair_verification=verification, repaired=False,
            ledger=self._ledger, diagnostics=self._diagnostics)

    async def _within(self, awaitable, deadline):
        if deadline is None:
            return await awaitable
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError("action loop deadline exceeded")
        async with asyncio.timeout(remaining):
            return await awaitable

    async def _run_tool(self, tool: ToolAction, task, state, deadline) -> None:
        if tool.node_id in state.used_node_ids:
            state.defects.append(TypedDefect(
                kind="duplicate_node",
                message=f"node id {tool.node_id!r} already has evidence authority"))
            state.history.append({"action": "tool", "node_id": tool.node_id,
                                  "status": "rejected"})
            return
        covers = [item.id for item in task.requirements
                  if tool.capability in item.capability_options]
        node = PlanNode(
            id=tool.node_id, description=tool.capability,
            capability_hints=[tool.capability],
            covers_requirement_ids=covers,
            arguments=tool.arguments, max_attempts=1, status="pending")
        plan = Plan(nodes=[node])
        try:
            self._executor.validate_plan(task, plan)
            execution = await self._within(
                self._executor.execute(
                    task, plan, run_id=f"{self._turn_id}:{tool.node_id}",
                    resume=False),
                deadline)
        except PlanValidationError as exc:
            state.defects.append(TypedDefect(
                kind="invalid_tool", message=str(exc)))
            state.history.append({"action": "tool", "node_id": tool.node_id,
                                  "status": "rejected"})
            return
        except (asyncio.CancelledError, TimeoutError):
            raise
        except Exception as exc:
            state.defects.append(TypedDefect(
                kind="tool_failure", message=f"{type(exc).__name__}: {exc}"))
            state.history.append({"action": "tool", "node_id": tool.node_id,
                                  "status": "failed"})
            return
        state.used_node_ids.add(tool.node_id)
        state.nodes.extend(execution.plan.nodes)
        state.evidence_by_node.update(execution.evidence_by_node)
        state.attempts.update(execution.attempts)
        state.errors.update(execution.errors)
        for node_id, codes in execution.error_codes.items():
            state.error_codes.setdefault(node_id, []).extend(codes)
        for node_id, messages in execution.errors.items():
            for message in messages:
                state.defects.append(TypedDefect(
                    kind="tool_failure", message=f"{node_id}: {message}"))
        state.history.append({
            "action": "tool", "node_id": tool.node_id,
            "status": ("complete" if tool.node_id in execution.evidence_by_node
                       else "failed")})

    async def _run_answer(self, answer: AnswerAction, task, state, started, deadline) -> RuntimeResult:
        state.last_draft = answer.draft
        evidence = list(state.evidence_by_node.values())
        try:
            draft = _validate_draft(answer.draft, evidence, task)
        except ValueError as exc:
            state.last_verification = VerificationReport(
                status=VerificationStatus.PARTIAL,
                missing_branches=[str(exc)])
            return self._publish(
                task, state, answer.draft, state.last_verification, started)
        evidence_map = {item.evidence_id: item for item in evidence}
        mechanical = await self._within(
            self._mechanical.verify(
                freeze_task(task), freeze_draft(draft),
                freeze_evidence_map(evidence_map)), deadline)
        mechanical = VerificationReport.model_validate(
            mechanical.model_dump() if hasattr(mechanical, "model_dump")
            else mechanical)
        semantic = await self._within(
            self._semantic.verify(
                freeze_task(task), freeze_draft(draft),
                freeze_evidence_map(evidence_map)), deadline)
        semantic = VerificationReport.model_validate(
            semantic.model_dump() if hasattr(semantic, "model_dump")
            else semantic)
        state.last_verification = merge_verification_reports(mechanical, semantic)
        return self._publish(
            task, state, draft, state.last_verification, started)

    async def run(
        self,
        task: TaskSpec,
        request: str = "action loop",
        *,
        owns_turn: bool = True,
        started: float | None = None,
        deadline: float | None = None,
    ) -> RuntimeResult:
        if started is None:
            started = time.perf_counter()
        if deadline is None and self._run_timeout_s is not None:
            deadline = started + self._run_timeout_s
        if owns_turn and self._ledger is not None:
            self._ledger.append(
                LedgerKind.TURN_START, turn_id=self._turn_id,
                data={"request": request})
        state = _LoopState()
        try:
            for _ in range(self._max_actions):
                payload = self._payload(
                    task, list(state.evidence_by_node.values()), state)
                envelope = RequestEnvelope.freeze(
                    provider=self._provider, model=self._model_name,
                    route="action_loop", prompt=self._prompt,
                    context=payload, tool_schemas=LoopAction.model_json_schema(),
                    planner_version=self._planner_version,
                    output_strategy="prompted_json")
                action = await self._within(
                    self._model.generate(
                        schema=LoopAction, prompt=self._prompt,
                        payload=payload, envelope=envelope),
                    deadline)
                if isinstance(action.step, ToolAction):
                    await self._run_tool(action.step, task, state, deadline)
                    continue
                return await self._run_answer(
                    action.step, task, state, started, deadline)
            message = ("action budget exhausted" if not state.defects
                       else "; ".join(item.message for item in state.defects))
            state.last_draft = state.last_draft or DraftReport(
                sections=[], claims=[], gaps=[message])
            state.last_verification = state.last_verification or VerificationReport(
                status=VerificationStatus.PARTIAL, missing_branches=[message])
            return self._publish(
                task, state, state.last_draft, state.last_verification, started)
        except BaseException as exc:
            if owns_turn:
                close_failed(
                    ledger=self._ledger, turn_id=self._turn_id,
                    exc=exc, started=started)
            raise


async def _within(awaitable, deadline):
    if deadline is None:
        return await awaitable
    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        raise TimeoutError("action runtime deadline exceeded")
    async with asyncio.timeout(remaining):
        return await awaitable


class ActionRuntime:
    def __init__(
        self,
        *,
        intake: Intake,
        model: StructuredModel,
        executor: PlanExecutor,
        mechanical_verifier: Verifier,
        semantic_verifier: Verifier,
        ledger: RunLedger | None,
        tool_catalog: Mapping[str, Any],
        run_timeout_s: float | None = None,
        pre_tool_timeout_s: float | None = None,
        max_actions: int = 4,
        diagnostics: bool = False,
        provider: str = "offline",
        model_name: str = "scripted",
        planner_version: str = "v2",
        progress: Callable[[str, str], None] | None = None,
    ) -> None:
        for name, value in (
            ("run_timeout_s", run_timeout_s),
            ("pre_tool_timeout_s", pre_tool_timeout_s),
        ):
            if (value is not None
                    and (isinstance(value, bool)
                         or not isinstance(value, (int, float))
                         or value <= 0)):
                raise ValueError(f"{name} must be positive or None")
        self._intake = intake
        self._model = model
        self._executor = executor
        self._mechanical = mechanical_verifier
        self._semantic = semantic_verifier
        self._ledger = ledger
        self._tool_catalog = dict(tool_catalog)
        self._run_timeout_s = run_timeout_s
        self._pre_tool_timeout_s = pre_tool_timeout_s
        self._max_actions = max_actions
        self._diagnostics = diagnostics
        self._provider = provider
        self._model_name = model_name
        self._planner_version = planner_version
        self._progress = progress

    def _report(self, status: str) -> None:
        if self._progress is not None:
            self._progress("understand", status)

    async def run(
        self,
        request: str,
        *,
        run_id: str | None = None,
        context: Sequence[ConversationTurn] = (),
    ) -> RuntimeResult:
        if not isinstance(request, str):
            raise TypeError("runtime request must be a string")
        if not request.strip():
            raise ValueError("runtime request must be non-empty")
        if len(request) > 2000:
            raise ValueError("runtime request cannot exceed 2000 characters")
        context = tuple(context)
        if len(context) > 8:
            raise ValueError("runtime context cannot exceed 8 turns")
        turn_id = run_id or "turn"
        started = time.perf_counter()
        deadline = (None if self._run_timeout_s is None
                    else started + self._run_timeout_s)
        pre_deadline = deadline
        if self._pre_tool_timeout_s is not None:
            pre = started + self._pre_tool_timeout_s
            pre_deadline = pre if pre_deadline is None else min(pre_deadline, pre)
        if self._ledger is not None:
            self._ledger.append(
                LedgerKind.TURN_START, turn_id=turn_id,
                data={"request": request})
        try:
            self._report("running")
            intake_call = (self._intake.understand(request, context)
                           if context else self._intake.understand(request))
            raw_task = await _within(intake_call, pre_deadline)
            task = TaskSpec.model_validate(
                raw_task.model_dump() if hasattr(raw_task, "model_dump")
                else raw_task)
            self._report("complete")
            loop = ActionLoop(
                model=self._model, executor=self._executor,
                mechanical_verifier=self._mechanical,
                semantic_verifier=self._semantic, ledger=self._ledger,
                tool_catalog=self._tool_catalog, turn_id=turn_id,
                max_actions=self._max_actions, run_timeout_s=None,
                diagnostics=self._diagnostics, provider=self._provider,
                model_name=self._model_name,
                planner_version=self._planner_version)
            return await loop.run(
                task, owns_turn=False, started=started, deadline=deadline)
        except BaseException as exc:
            close_failed(
                ledger=self._ledger, turn_id=turn_id, exc=exc, started=started)
            raise
