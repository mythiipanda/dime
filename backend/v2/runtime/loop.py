from __future__ import annotations

import asyncio
import inspect
import re
import time
from collections.abc import Callable, Iterable

from shared.config import settings

from v2.api.events import BindingDiagnostic
from v2.contracts import (
    ClaimResult,
    ConversationTurn,
    ClaimSource,
    Gap,
    GapKind,
    VerificationReport,
    VerifiedClaim,
    DraftReport,
    Plan,
    TaskSpec,
    VerificationStatus,
)
from v2.runtime.executor import PlanExecutor
from v2.runtime.fast_path import (
    FastPathUnverifiable,
    build_fast_plan,
    check_fast_evidence,
    check_fast_verification,
    is_fast_path_eligible,
)
from v2.runtime.interfaces import Intake, Planner, Repairer, Synthesizer, Verifier
from v2.runtime.ledger import LedgerKind, RunLedger, TerminalReason, exception_text
from v2.runtime.models import (BindingFormMismatch, ExecutionResult, RuntimeResult,
                               admit_verified_claim_bindings,
                               propagate_evidence_to_task,
                               reanchor_verified_claim_bindings)
from v2.domain.evidence import iter_values
from v2.runtime.budget import RUN_MODEL_DEADLINE

JUDGE_UNAVAILABLE_BRANCH = "Semantic verification was unavailable; published claims passed deterministic verification."
JUDGE_UNAVAILABLE_LEGACY_BRANCH = "Semantic completeness review was unavailable; published claims passed deterministic verification."
JUDGE_UNAVAILABLE_BRANCHES = frozenset({JUDGE_UNAVAILABLE_BRANCH, JUDGE_UNAVAILABLE_LEGACY_BRANCH})


class PreToolTimeoutError(TimeoutError):
    pass


class Runtime:
    def __init__(
        self,
        *,
        intake: Intake,
        planner: Planner,
        executor: PlanExecutor,
        synthesizer: Synthesizer,
        mechanical_verifier: Verifier,
        semantic_verifier: Verifier,
        repairer: Repairer | None = None,
        repair_attempts: int = 1,
        ledger: RunLedger | None = None,
        progress: Callable[[str, str], None] | None = None,
        activity: Callable[[dict], None] | None = None,
        pre_tool_timeout_s: float | None = None,
        run_timeout_s: float | None = None,
        diagnostics: bool = False,
        fast_path: bool = True,
    ) -> None:
        if not isinstance(repair_attempts, int) or isinstance(repair_attempts, bool):
            raise TypeError("repair_attempts must be an integer")
        if not 0 <= repair_attempts <= 2:
            raise ValueError("repair_attempts must be between 0 and 2")
        self._intake = intake
        self._planner = planner
        self._executor = executor
        self._synthesizer = synthesizer
        self._mechanical_verifier = mechanical_verifier
        self._semantic_verifier = semantic_verifier
        self._repairer = repairer
        self._repair_attempts = repair_attempts
        self._ledger = ledger
        if (pre_tool_timeout_s is not None
                and (isinstance(pre_tool_timeout_s, bool)
                      or not isinstance(pre_tool_timeout_s, (int, float))
                      or pre_tool_timeout_s <= 0)):
            raise ValueError("pre_tool_timeout_s must be a positive number or None")
        if (run_timeout_s is not None
                and (isinstance(run_timeout_s, bool)
                      or not isinstance(run_timeout_s, (int, float))
                      or run_timeout_s <= 0)):
            raise ValueError("run_timeout_s must be a positive number or None")
        self._progress = progress
        self._activity = activity
        self._pre_tool_timeout_s = pre_tool_timeout_s
        self._run_timeout_s = run_timeout_s
        if not isinstance(diagnostics, bool):
            raise TypeError("diagnostics must be a boolean")
        self._diagnostics = diagnostics
        if not isinstance(fast_path, bool):
            raise TypeError("fast_path must be a boolean")
        self._fast_path = fast_path

    async def run(
        self, request: str, *, run_id: str | None = None,
        context: tuple[ConversationTurn, ...] = (),
    ) -> RuntimeResult:
        if not isinstance(request, str):
            raise TypeError("runtime request must be a string")
        if not request.strip():
            raise ValueError("runtime request must be non-empty")
        if len(request) > 2000:
            raise ValueError("runtime request cannot exceed 2000 characters")
        context = tuple(ConversationTurn.model_validate(
            turn.model_dump() if isinstance(turn, ConversationTurn) else turn
        ) for turn in context)
        if len(context) > 8:
            raise ValueError("runtime context cannot exceed 8 turns")
        turn_id = run_id or "turn"
        turn_started = time.perf_counter()
        run_deadline = (None if self._run_timeout_s is None
                        else turn_started + self._run_timeout_s)

        def run_remaining() -> float | None:
            if run_deadline is None:
                return None
            return max(0.000001, run_deadline - time.perf_counter())



        RUN_MODEL_DEADLINE.set(
            None if settings.dime_v2_model_deadline_s <= 0
            else turn_started + settings.dime_v2_model_deadline_s)
        if self._ledger is not None:
            if run_id is not None and self._ledger.run_id != run_id:
                raise ValueError("ledger run id does not match runtime run id")
            self._ledger.append(
                LedgerKind.TURN_START, turn_id=turn_id,
                data={"request": request},
            )
        try:
            async def understand(deadline: float | None = None):
                def remaining() -> float | None:
                    if deadline is None:
                        return None
                    return max(0.000001, deadline - time.perf_counter())
                intake_call = (self._intake.understand(request, context)
                               if context else self._intake.understand(request))
                prepared_task = TaskSpec.model_validate(
                    (await self._stage(
                        turn_id, "understand", intake_call,
                        timeout_s=remaining())).model_dump()
                )
                self._report_activity({"kind":"stage_summary","phase":"understand","status":"complete","title":"Request understood","transition":"completed","correlation_id":"stage:understand","data":{"mode":prepared_task.mode.value,"season":prepared_task.season.value if prepared_task.season else None,"entity_count":len(prepared_task.entities),"requirement_count":len(prepared_task.requirements),"calculation_count":len(prepared_task.calculation_requirements)}})
                if prepared_task.open_questions:
                    raise ValueError(
                        "intake left unresolved questions: "
                        + "; ".join(prepared_task.open_questions))
                return prepared_task

            async def plan_task(prepared_task, deadline: float | None = None):
                def remaining() -> float | None:
                    if deadline is None:
                        return None
                    return max(0.000001, deadline - time.perf_counter())
                prepared_plan = Plan.model_validate((await self._stage(
                    turn_id, "plan", self._planner.plan(prepared_task),
                    timeout_s=remaining())).model_dump())
                catalog = getattr(self._executor, "capability_names", frozenset())
                self._report_activity({"kind":"plan_update","phase":"plan","status":"complete","title":"Plan accepted","transition":"completed","correlation_id":"stage:plan","data":{"node_count":len(prepared_plan.nodes),"capabilities":sorted({cap for n in prepared_plan.nodes for cap in n.capability_hints if cap in catalog}),"unknown_capability_count":sum(1 for n in prepared_plan.nodes for cap in n.capability_hints if cap not in catalog)}})
                return prepared_plan

            pre_tool_deadline = (None if self._pre_tool_timeout_s is None
                                 else time.perf_counter() + self._pre_tool_timeout_s)
            try:
                pre_tool_remaining = (lambda: None if pre_tool_deadline is None
                                      else max(0.000001, pre_tool_deadline - time.perf_counter()))()
                task = await understand(pre_tool_remaining)
            except TimeoutError as exc:
                raise PreToolTimeoutError(
                    f"intake and planning exceeded "
                    f"{self._pre_tool_timeout_s:g} seconds") from exc
            if self._fast_path and is_fast_path_eligible(task):
                try:
                    fast_result = await self._run_fast_path(
                        turn_id, task, run_remaining=run_remaining)
                    return fast_result
                except FastPathUnverifiable as exc:
                    self._report_activity({"kind":"stage_summary","phase":"fast_path","status":"complete","title":"Fast path fell back","transition":"completed","correlation_id":"stage:fast_path","data":{"reason": str(exc)}})
                except PreToolTimeoutError:
                    raise
                except TimeoutError:
                    raise
                except asyncio.CancelledError:
                    raise
                except BaseException as exc:
                    self._report_activity({"kind":"stage_summary","phase":"fast_path","status":"complete","title":"Fast path fell back","transition":"completed","correlation_id":"stage:fast_path","data":{"reason": f"{type(exc).__name__}: {exc}"}})
            try:
                pre_tool_remaining = (None if pre_tool_deadline is None
                                      else max(0.000001, pre_tool_deadline - time.perf_counter()))
                plan = await plan_task(task, pre_tool_remaining)
            except TimeoutError as exc:
                raise PreToolTimeoutError(
                    f"intake and planning exceeded "
                    f"{self._pre_tool_timeout_s:g} seconds") from exc
            execution = ExecutionResult.model_validate((await self._stage(
                turn_id, "execute",
                self._executor.execute(task, plan, run_id=run_id),
                timeout_s=run_remaining())).model_dump())
            if (execution.plan.nodes
                    and not any(node.status.value == "complete"
                                for node in execution.plan.nodes)
                    and _planner_accepts_failure_context(self._planner)):
                recovery_plan = Plan.model_validate((await self._stage(
                    turn_id, "replan",
                    self._planner.plan(
                        task,
                        failure_context=_failure_context(task, execution)),
                    timeout_s=run_remaining()
                )).model_dump())
                self._report_activity({"kind":"stage_summary","phase":"replan","status":"complete","title":"Recovery plan accepted","transition":"completed","correlation_id":"stage:replan","data":{"node_count":len(recovery_plan.nodes),"capabilities":sorted({cap for n in recovery_plan.nodes for cap in n.capability_hints})}})
                recovery = ExecutionResult.model_validate((await self._stage(
                    turn_id, "recover",
                    self._executor.execute(
                        task, recovery_plan, run_id=run_id, resume=False),
                    timeout_s=run_remaining())).model_dump())
                execution = _merge_recovery(execution, recovery)
            draft = DraftReport.model_validate((await self._stage(
                turn_id, "synthesize",
                self._synthesizer.synthesize(task, execution.evidence),
                timeout_s=run_remaining())).model_dump())
        except BaseException as exc:
            self._close_failed(turn_id, exc, started=turn_started)
            raise
        evidence = {item.evidence_id: item for item in execution.evidence}
        try:
            verification = await self._stage(
                turn_id, "verify", self._verify(task, draft, evidence),
                timeout_s=run_remaining())
        except BaseException as exc:
            self._close_failed(turn_id, exc, started=turn_started)
            raise
        self._verification_activity(verification, "initial")
        pre_repair_draft = draft.model_copy(deep=True)
        pre_repair_verification = verification.model_copy(deep=True)
        repaired = False

        for attempt in range(self._repair_attempts):
            missing = _completeness_missing(task, execution, draft, verification, evidence)
            needs_verification = _needs_repair(verification)
            if (not needs_verification and not missing) or self._repairer is None:
                break
            effective = verification
            if missing:
                effective = _with_completeness_findings(verification, missing)
            suffix = "" if attempt == 0 else f":{attempt + 1}"
            try:
                repair_call = self._repairer.repair(
                    task, draft, evidence, effective)
                draft = DraftReport.model_validate((await self._stage(
                    turn_id, f"repair{suffix}", repair_call,
                    timeout_s=run_remaining())).model_dump())
                repaired = True
                verification = await self._stage(
                    turn_id, f"reverify{suffix}",
                    self._verify(task, draft, evidence),
                    timeout_s=run_remaining())
                self._verification_activity(verification, f"reverify:{attempt + 1}")
            except asyncio.CancelledError:
                self._close_failed(turn_id, asyncio.CancelledError(), started=turn_started)
                raise
            except RuntimeError as exc:
                if not str(exc).startswith("all structured-output providers failed"):
                    self._close_failed(turn_id, exc, started=turn_started)
                    raise




                supported = {
                    item.claim_index for item in verification.claim_results
                    if item.supported
                }
                draft = draft.model_copy(update={
                    "claims": [claim for index, claim in enumerate(draft.claims)
                               if index in supported],
                    "calculations": [calculation for calculation in draft.calculations
                                     if any(claim.calculation_id == calculation.calculation_id
                                            for index, claim in enumerate(draft.claims)
                                            if index in supported)],
                    "gaps": _unique([
                        *draft.gaps, *verification.missing_branches,
                        *verification.contradictions,
                        *verification.repair_instructions,
                        "Model repair was unavailable; unsupported claims were withheld."
                    ], limit=128),
                })
                verification = VerificationReport(
                    status=VerificationStatus.PARTIAL,
                    claim_results=[ClaimResult(
                        claim_index=index, supported=True)
                        for index, _claim in enumerate(draft.claims)],
                    missing_branches=[
                        "Model repair was unavailable; unsupported claims were withheld."
                    ],
                )
                break

        if verification.status == VerificationStatus.REPAIR:
            gaps = _unique(
                [
                    *draft.gaps,
                    *verification.missing_branches,
                    *verification.contradictions,
                ],
                limit=128,
            )
            draft = DraftReport.model_validate(
                draft.model_copy(update={"gaps": gaps}).model_dump())
            verification = verification.model_copy(
                update={"status": VerificationStatus.PARTIAL}
            )

        return self._publish(
            task=task,
            execution=execution,
            draft=draft,
            verification=verification,
            evidence=evidence,
            turn_id=turn_id,
            turn_started=turn_started,
            pre_repair_draft=pre_repair_draft,
            pre_repair_verification=pre_repair_verification,
            repaired=repaired,
        )

    def _publish(
        self,
        *,
        task,
        execution,
        draft,
        verification,
        evidence,
        turn_id,
        turn_started,
        pre_repair_draft,
        pre_repair_verification,
        repaired,
    ) -> RuntimeResult:
        final_missing = _completeness_missing(task, execution, draft, verification, evidence)
        if final_missing:
            instruction = _format_completeness_instruction(final_missing)
            failure_message = _format_completeness_failure(final_missing)
            verification = verification.model_copy(update={
                "status": VerificationStatus.PARTIAL,
                "missing_branches": _unique([*verification.missing_branches, instruction], limit=128),
            })
            draft = draft.model_copy(update={
                "gaps": _unique([*draft.gaps, failure_message], limit=128),
            })

        unavailable_claims = {
            index: sorted(set(claim.evidence_ids) - set(evidence))
            for index, claim in enumerate(draft.claims)
            if set(claim.evidence_ids) - set(evidence)
        }
        if unavailable_claims:
            claim_results = [
                ClaimResult(
                    claim_index=result.claim_index,
                    supported=False,
                    reasons=[f"unknown execution evidence ids: "
                             f"{unavailable_claims[result.claim_index]}"])
                if result.supported and result.claim_index in unavailable_claims
                else result
                for result in verification.claim_results
            ]
            verification = verification.model_copy(update={
                "status": VerificationStatus.PARTIAL,
                "claim_results": claim_results,
            })

        empty_evidence_gaps = _empty_evidence_gaps(execution.evidence)
        uncovered_requirement_gaps = _uncovered_requirement_gaps(task, execution)
        failed_nodes = {
            node.id for node in execution.plan.nodes
            if node.status.value == "failed"
        }
        redundant_failures = _redundant_failed_nodes(task, execution)
        represented_failures = _failures_represented_by_precise_gaps(
            task, execution, [*draft.gaps, *verification.missing_branches])
        unresolved_errors = {
            node_id: errors for node_id, errors in execution.errors.items()
            if node_id in failed_nodes
            and node_id not in redundant_failures
            and node_id not in represented_failures
        }
        skipped_nodes = [
            node.id for node in execution.plan.nodes
            if node.status.value == "skipped"
        ]
        empty_draft_gaps = ([] if (
            draft.claims or draft.gaps or empty_evidence_gaps
            or uncovered_requirement_gaps or unresolved_errors or skipped_nodes
        ) else [Gap(
            kind=GapKind.MISSING_EVIDENCE,
            message="synthesis produced no publishable claims",
        )])
        if ((draft.gaps or empty_evidence_gaps or uncovered_requirement_gaps
                or empty_draft_gaps or unresolved_errors or skipped_nodes)
                and verification.status == VerificationStatus.PASS):
            verification = verification.model_copy(
                update={"status": VerificationStatus.PARTIAL}
            )
        binding_diagnostics = []
        verified_claims, binding_gaps = _verified_claims(
            task, execution, draft, verification, evidence,
            diagnostics=self._diagnostics,
            diagnostics_run_id=turn_id,
            diagnostics_events=binding_diagnostics)
        if binding_gaps and verification.status == VerificationStatus.PASS:
            verification = verification.model_copy(
                update={"status": VerificationStatus.PARTIAL})
        gaps = [
            *_verification_gaps(
                draft, verification, unresolved_errors,
                execution_error_codes=execution.error_codes,
                evidence_ids=set(evidence),
                satisfied_requirement_ids={
                    requirement_id for node in execution.plan.nodes
                    if node.status.value == "complete"
                    for requirement_id in node.covers_requirement_ids
                }),
            *binding_gaps,
            *empty_evidence_gaps,
            *uncovered_requirement_gaps,
            *empty_draft_gaps,
            *[
                Gap(kind=GapKind.EXECUTION_FAILURE,
                    message=f"execution skipped node {node_id}",
                    blocks=[f"node:{node_id}"])
                for node_id in skipped_nodes
            ],
        ]
        if verification.status == VerificationStatus.PARTIAL and not gaps:
            gaps.append(Gap(
                kind=GapKind.MISSING_EVIDENCE,
                message="verification did not establish complete support",
            ))
        pre_repair_supported = {
            result.claim_index for result in pre_repair_verification.claim_results
            if result.supported
        }
        pre_repair_keys = {
            (claim.text, claim.kind, tuple(claim.evidence_ids), claim.calculation_id)
            for index, claim in enumerate(pre_repair_draft.claims)
            if index in pre_repair_supported
            and claim.kind.value in {"observed", "derived"}
        }
        published_keys = {
            (claim.text, claim.kind, tuple(claim.evidence_ids), claim.calculation_id)
            for claim in draft.claims
        }
        structural_flags = []
        if repaired and pre_repair_keys - published_keys:
            structural_flags.append("repair_stripped_evidence_claim")
        if redundant_failures:
            structural_flags.append("false_partial_downgrade")
        result = RuntimeResult(
            task=task,
            execution=execution,
            draft=draft,
            verification=verification,
            repaired=repaired,
            structural_flags=structural_flags,
            verified_claims=verified_claims,
            gaps=gaps[:256],
            binding_diagnostics=[
                event.model_dump(mode="json", exclude_none=True)
                for event in binding_diagnostics
            ],
        )
        if self._ledger is not None:
            self._ledger.append(
                LedgerKind.TURN_END, turn_id=turn_id,
                data={"reason": TerminalReason.COMPLETE.value,
                      "verification": verification.status.value,
                      "duration_ms": max(0, round(
                          (time.perf_counter() - turn_started) * 1000))},
            )
        return result

    def _report_activity(self, payload: dict) -> None:
        if self._activity is None:
            return
        try:
            self._activity(payload)
        except Exception:
            pass

    def _verification_activity(self, report: VerificationReport, round_id: str) -> None:
        self._report_activity({"kind":"verification_update","phase":"verify","status":report.status.value,"title":"Verification updated","transition":"snapshot","correlation_id":f"verification:{round_id}","data":{"round":round_id,"supported_count":sum(1 for item in report.claim_results if item.supported),"claim_count":len(report.claim_results),"missing_count":len(report.missing_branches),"contradiction_count":len(report.contradictions),"repair_count":len(report.repair_instructions)}})

    async def _run_fast_path(self, turn_id: str, task: TaskSpec, *, run_remaining) -> RuntimeResult:
        turn_started = time.perf_counter()
        fast_plan = build_fast_plan(task)
        try:
            execution = ExecutionResult.model_validate((await self._stage(
                turn_id, "fast_execute",
                self._executor.execute(task, fast_plan),
                timeout_s=run_remaining())).model_dump())
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise FastPathUnverifiable(f"fast execution unavailable: {exc}") from exc
        check_fast_evidence(list(execution.evidence))
        try:
            draft = DraftReport.model_validate((await self._stage(
                turn_id, "fast_synthesize",
                self._synthesizer.synthesize(task, execution.evidence),
                timeout_s=run_remaining())).model_dump())
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise FastPathUnverifiable(f"fast synthesis unavailable: {exc}") from exc
        evidence = {item.evidence_id: item for item in execution.evidence}
        try:
            verification = await self._stage(
                turn_id, "fast_verify",
                self._fast_verify(task, draft, evidence),
                timeout_s=run_remaining())
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            if isinstance(exc, FastPathUnverifiable):
                raise
            raise FastPathUnverifiable(f"fast verification unavailable: {exc}") from exc
        check_fast_verification(verification, len(draft.claims))
        self._verification_activity(verification, "fast")
        published = self._publish(
            task=task,
            execution=execution,
            draft=draft,
            verification=verification,
            evidence=evidence,
            turn_id=turn_id,
            turn_started=turn_started,
            pre_repair_draft=draft.model_copy(deep=True),
            pre_repair_verification=verification.model_copy(deep=True),
            repaired=False,
        )
        if not published.verified_claims:
            raise FastPathUnverifiable("fast path published no verified claims")
        return published

    async def _fast_verify(self, task, draft, evidence) -> VerificationReport:
        mechanical = VerificationReport.model_validate(
            (await self._mechanical_verifier.verify(task, draft, evidence)).model_dump()
        )
        expected = list(range(len(draft.claims)))
        mechanical_indices = sorted(
            result.claim_index for result in mechanical.claim_results)
        if mechanical_indices != expected:
            raise FastPathUnverifiable(
                "mechanical verifier must adjudicate every claim exactly once")
        return mechanical

    def _report_progress(self, step_id: str, status: str) -> None:
        if self._progress is None:
            return
        try:
            self._progress(step_id, status)
        except Exception:
            pass

    async def _stage(
        self, turn_id: str, step_id: str, awaitable,
        *, timeout_s: float | None = None,
    ):
        started = time.perf_counter()
        if self._ledger is not None:
            try:
                self._ledger.append(
                    LedgerKind.STEP_START, turn_id=turn_id, step_id=step_id)
            except BaseException:
                if inspect.iscoroutine(awaitable):
                    awaitable.close()
                elif isinstance(awaitable, asyncio.Future):
                    awaitable.cancel()
                raise
        self._report_progress(step_id, "running")
        try:
            if timeout_s is None:
                result = await awaitable
            else:
                async with asyncio.timeout(timeout_s):
                    result = await awaitable
        except BaseException as exc:
            if self._ledger is not None:
                reason = (TerminalReason.CANCELLED
                          if isinstance(exc, asyncio.CancelledError)
                          else TerminalReason.TIMEOUT
                          if isinstance(exc, TimeoutError)
                          else TerminalReason.FAILED)
                self._ledger.append(
                    LedgerKind.STEP_END, turn_id=turn_id, step_id=step_id,
                    data={"reason": reason.value,
                          "error": exception_text(exc),
                          "duration_ms": max(0, round(
                              (time.perf_counter() - started) * 1000))},
                )
            self._report_progress(step_id, "failed")
            raise
        if self._ledger is not None:
            self._ledger.append(
                LedgerKind.STEP_END, turn_id=turn_id, step_id=step_id,
                data={"reason": TerminalReason.COMPLETE.value,
                      "duration_ms": max(0, round(
                          (time.perf_counter() - started) * 1000))})
        self._report_progress(step_id, "complete")
        return result

    def _close_failed(
        self, turn_id: str, exc: BaseException, *, started: float,
    ) -> None:
        if self._ledger is None:
            return
        reason = (TerminalReason.CANCELLED
                  if isinstance(exc, asyncio.CancelledError)
                  else TerminalReason.TIMEOUT
                  if isinstance(exc, (TimeoutError, PreToolTimeoutError))
                  else TerminalReason.FAILED)
        self._ledger.append(
            LedgerKind.TURN_END, turn_id=turn_id,
            data={"reason": reason.value,
                  "error": exception_text(exc),
                  "duration_ms": max(0, round(
                      (time.perf_counter() - started) * 1000))},
        )

    async def _verify(self, task, draft, evidence) -> VerificationReport:
        mechanical = VerificationReport.model_validate(
            (await self._mechanical_verifier.verify(task, draft, evidence)).model_dump()
        )
        expected = list(range(len(draft.claims)))
        mechanical_indices = sorted(
            result.claim_index for result in mechanical.claim_results)
        if mechanical_indices != expected:
            raise ValueError(
                "mechanical verifier must adjudicate every claim exactly once")
        if mechanical.status == VerificationStatus.REPAIR:
            return mechanical.model_copy(update={
                "missing_branches": _unique(
                    [*mechanical.missing_branches, JUDGE_UNAVAILABLE_BRANCH],
                    limit=128),
            })
        try:
            semantic = VerificationReport.model_validate(
                (await self._semantic_verifier.verify(task, draft, evidence)).model_dump()
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            if all(item.supported for item in mechanical.claim_results):
                return mechanical.model_copy(update={
                    "status": VerificationStatus.PARTIAL,
                    "missing_branches": _unique(
                        [*mechanical.missing_branches, JUDGE_UNAVAILABLE_BRANCH],
                        limit=128),
                })
            return mechanical.model_copy(update={
                "missing_branches": _unique(
                    [*mechanical.missing_branches, JUDGE_UNAVAILABLE_BRANCH],
                    limit=128),
            })
        satisfied_calculation_ids = {
            calculation.requirement_id
            for calculation in draft.calculations
            if calculation.requirement_id is not None
            and any(claim.calculation_id == calculation.calculation_id
                    for claim in draft.claims)
        }
        satisfied_calculations = [
            requirement for requirement in task.calculation_requirements
            if requirement.id in satisfied_calculation_ids
        ]
        def repeats_satisfied_calculation(message: str) -> bool:
            folded = " ".join(message.casefold().replace("_", " ").split())
            return any(
                requirement.id.replace("_", " ").casefold() in folded
                or requirement.description.casefold() in folded
                for requirement in satisfied_calculations
            )
        if satisfied_calculations:
            semantic = semantic.model_copy(update={
                "missing_branches": [item for item in semantic.missing_branches
                                     if not repeats_satisfied_calculation(item)],
                "repair_instructions": [item for item in semantic.repair_instructions
                                        if not repeats_satisfied_calculation(item)],
            })
            if (semantic.status == VerificationStatus.REPAIR
                    and not semantic.missing_branches
                    and not semantic.contradictions
                    and not semantic.repair_instructions
                    and all(item.supported for item in semantic.claim_results)):
                semantic = semantic.model_copy(update={"status": VerificationStatus.PASS})
        populated_capabilities = {
            item.capability for item in evidence.values()
            if any(True for _ in iter_values(item))
        }
        satisfied_requirements = [
            requirement for requirement in task.requirements
            if set(requirement.capability_options) & populated_capabilities
        ]
        def repeats_satisfied_requirement(message: str) -> bool:
            folded = " ".join(message.casefold().replace("_", " ").split())
            return any(
                requirement.id.replace("_", " ").casefold() in folded
                or requirement.description.casefold() in folded
                for requirement in satisfied_requirements
            )
        if satisfied_requirements:
            semantic = semantic.model_copy(update={
                "missing_branches": [item for item in semantic.missing_branches
                                     if not repeats_satisfied_requirement(item)],
                "repair_instructions": [item for item in semantic.repair_instructions
                                        if not repeats_satisfied_requirement(item)],
            })
            if (semantic.status == VerificationStatus.REPAIR
                    and not semantic.missing_branches
                    and not semantic.contradictions
                    and not semantic.repair_instructions
                    and all(item.supported for item in semantic.claim_results)):
                semantic = semantic.model_copy(update={"status": VerificationStatus.PASS})



        if (semantic.status == VerificationStatus.PARTIAL
                and sorted(item.claim_index for item in semantic.claim_results) == expected
                and all(item.supported for item in semantic.claim_results)
                and not semantic.missing_branches
                and not semantic.contradictions
                and not semantic.repair_instructions):
            semantic = semantic.model_copy(update={"status": VerificationStatus.PASS})
        observed = [result.claim_index for result in semantic.claim_results]
        if (len(observed) != len(set(observed))
                or any(index not in expected for index in observed)):
            raise ValueError(
                "semantic verifier returned duplicate or unknown claim indices")
        merged = _merge_verification(mechanical, semantic)
        uncertain_indices = sorted({
            result.claim_index for result in merged.claim_results
            if result.uncertain
        })
        if uncertain_indices:
            merged = merged.model_copy(update={
                "status": (VerificationStatus.PARTIAL
                           if merged.status == VerificationStatus.PASS
                           else merged.status),
                "missing_branches": _unique(
                    [*merged.missing_branches, *(
                        f"Claim {index} could not be fully confirmed "
                        f"against the admitted evidence."
                        for index in uncertain_indices
                    )],
                    limit=128),
            })
        return merged


def _needs_repair(report: VerificationReport) -> bool:
    return (report.status == VerificationStatus.REPAIR
            and any(not item.supported for item in report.claim_results))


def _requested_output_identities(task):
    rows = []
    for output_id in task.requested_outputs:
        rows.append(("task", None, output_id))
    for requirement in task.requirements:
        for output_id in requirement.requested_outputs:
            rows.append(("evidence", requirement.id, output_id))
    for requirement in task.calculation_requirements:
        for output_id in requirement.requested_outputs:
            rows.append(("calculation", requirement.id, output_id))
    return rows


def _serving_columns(task, execution, kind, requirement_id, output_id):
    from v2.adapters.capabilities import CAPABILITIES, resolve_metric_column
    if kind == "calculation":
        return []
    if kind == "evidence":
        requirement = next((item for item in task.requirements if item.id == requirement_id), None)
        if requirement is None:
            candidates = []
        else:
            candidates = list(requirement.capability_options)
    else:
        names = set()
        for requirement in task.requirements:
            names.update(requirement.capability_options)
        for envelope in execution.evidence:
            names.add(envelope.capability)
        candidates = sorted(names)
    served = []
    for name in candidates:
        capability = CAPABILITIES.get(name)
        if capability is None:
            continue
        column = resolve_metric_column(capability, output_id)
        if column is not None:
            served.append(f"{column} via {name}")
    return list(dict.fromkeys(served))


def _has_serving_values(execution, output_id):
    from v2.adapters.capabilities import CAPABILITIES, resolve_metric_column
    for envelope in execution.evidence:
        capability = CAPABILITIES.get(envelope.capability)
        if capability is None:
            continue
        column = resolve_metric_column(capability, output_id)
        if column is None:
            continue
        for item in iter_values(envelope):
            leaf = item.path.rsplit(".", 1)[-1].split("[", 1)[0]
            if leaf == column and item.value is not None:
                return True
    return False


def _completeness_missing(task, execution, draft, verification, evidence):
    from v2.runtime.models import build_output_statuses
    admitted, binding_gaps = _verified_claims(task, execution, draft, verification, evidence)
    statuses = build_output_statuses(task, admitted, binding_gaps)
    missing = []
    for status in statuses:
        if status.status == "complete":
            continue
        serving = _serving_columns(task, execution, status.requirement_kind, status.requirement_id, status.output_id)
        if status.requirement_kind != "calculation" and not _has_serving_values(execution, status.output_id):
            continue
        missing.append((status.requirement_kind, status.requirement_id, status.output_id, serving))
    return missing


def _format_completeness_instruction(missing):
    parts = []
    for kind, requirement_id, output_id, serving in missing:
        if serving:
            parts.append(f"Bind missing requested output {output_id} served by {', '.join(serving)}")
        else:
            parts.append(f"Bind missing requested output {output_id}")
    return "; ".join(parts)


def _with_completeness_findings(verification, missing):
    instruction = _format_completeness_instruction(missing)
    return verification.model_copy(update={
        "status": VerificationStatus.REPAIR,
        "missing_branches": _unique([*verification.missing_branches, instruction], limit=128),
        "repair_instructions": _unique([*verification.repair_instructions, instruction], limit=128),
    })


def _format_completeness_failure(missing):
    parts = []
    for kind, requirement_id, output_id, serving in missing:
        if serving:
            parts.append(f"requested output {output_id} unbound; expected evidence {', '.join(serving)}")
        else:
            parts.append(f"requested output {output_id} unbound")
    return "Incomplete synthesis: " + "; ".join(parts)


def _merge_verification(
    mechanical: VerificationReport, semantic: VerificationReport
) -> VerificationReport:
    statuses = {mechanical.status, semantic.status}
    if VerificationStatus.REPAIR in statuses:
        status = VerificationStatus.REPAIR
    elif VerificationStatus.PARTIAL in statuses:
        status = VerificationStatus.PARTIAL
    else:
        status = VerificationStatus.PASS
    return VerificationReport(
        status=status,
        claim_results=_merge_claim_results(
            [*mechanical.claim_results, *semantic.claim_results]
        ),
        missing_branches=_unique(
            [*mechanical.missing_branches, *semantic.missing_branches], limit=128
        ),
        contradictions=_unique(
            [*mechanical.contradictions, *semantic.contradictions], limit=128),
        repair_instructions=_unique(
            [*mechanical.repair_instructions, *semantic.repair_instructions],
            limit=128,
        ),
    )


def _merge_claim_results(results: Iterable[ClaimResult]) -> list[ClaimResult]:
    merged: dict[int, ClaimResult] = {}
    for result in results:
        current = merged.get(result.claim_index)
        if current is None:
            merged[result.claim_index] = result.model_copy(deep=True)
            continue
        merged[result.claim_index] = ClaimResult(
            claim_index=result.claim_index,
            supported=current.supported and result.supported,
            reasons=_unique([*current.reasons, *result.reasons], limit=64),
            evidence_spans=_unique(
                [*current.evidence_spans, *result.evidence_spans], limit=32),
            uncertain=current.uncertain or result.uncertain,
        )
    return [merged[index] for index in sorted(merged)]


def _planner_accepts_failure_context(planner) -> bool:
    try:
        parameters = inspect.signature(planner.plan).parameters
    except (TypeError, ValueError):
        return True
    return "failure_context" in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


def _failure_context(task, execution) -> dict:
    requirements = {item.id: item for item in task.requirements}
    grouped: dict[str, list] = {}
    for node in execution.plan.nodes:
        if node.status.value not in {"failed", "skipped"}:
            continue
        for requirement_id in node.covers_requirement_ids:
            grouped.setdefault(requirement_id, []).append(node)
    entries = []
    for requirement_id, nodes in grouped.items():
        requirement = requirements.get(requirement_id)
        if requirement is None:
            continue
        tried = {hint for node in nodes if node.status.value == "failed"
                 for hint in node.capability_hints}
        entries.append({
            "requirement_id": requirement_id,
            "failed_nodes": [node.id for node in nodes],
            "failure_reasons": [message for node in nodes
                                for message in execution.errors.get(node.id, [])],
            "remaining_capability_options": [
                option for option in requirement.capability_options
                if option not in tried],
        })
    return {"requirements": entries}


def _merge_recovery(execution: ExecutionResult, recovery: ExecutionResult) -> ExecutionResult:
    taken = {node.id for node in execution.plan.nodes}
    renames: dict[str, str] = {}
    for node in recovery.plan.nodes:
        target = node.id
        index = 1
        while target in taken:
            index += 1
            target = f"{node.id}-replan{index}"
        renames[node.id] = target
        taken.add(target)
    merged_nodes = [*execution.plan.nodes, *(
        node.model_copy(update={
            "id": renames[node.id],
            "depends_on": [renames.get(parent, parent)
                           for parent in node.depends_on],
        })
        for node in recovery.plan.nodes
    )]
    merged_evidence = dict(execution.evidence_by_node)
    remapped: dict[str, str] = {}
    for node_id, envelope in recovery.evidence_by_node.items():
        target = renames.get(node_id, node_id)
        if target != node_id:
            remapped[envelope.evidence_id] = f"evidence:{target}"
    for node_id, envelope in recovery.evidence_by_node.items():
        target = renames.get(node_id, node_id)
        lineage = [remapped.get(entry, entry) for entry in envelope.lineage]
        new_id = remapped.get(envelope.evidence_id)
        if new_id is not None:
            envelope = envelope.model_copy(update={"evidence_id": new_id, "lineage": lineage})
        elif lineage != envelope.lineage:
            envelope = envelope.model_copy(update={"lineage": lineage})
        merged_evidence[target] = envelope
    merged_attempts = dict(execution.attempts)
    for node_id, count in recovery.attempts.items():
        merged_attempts[renames.get(node_id, node_id)] = count
    merged_errors = dict(execution.errors)
    for node_id, messages in recovery.errors.items():
        target = renames.get(node_id, node_id)
        merged_errors[target] = list(dict.fromkeys(
            [*merged_errors.get(target, []), *messages]))
    merged_codes = dict(execution.error_codes)
    for node_id, codes in recovery.error_codes.items():
        target = renames.get(node_id, node_id)
        merged_codes[target] = list(dict.fromkeys(
            [*merged_codes.get(target, []), *codes]))
    return ExecutionResult.model_validate({
        **execution.model_dump(),
        "plan": {"nodes": [node.model_dump() for node in merged_nodes]},
        "evidence_by_node": {
            node_id: envelope.model_dump()
            for node_id, envelope in merged_evidence.items()
        },
        "attempts": merged_attempts,
        "errors": merged_errors,
        "error_codes": merged_codes,
    })


def _unique(values: Iterable[str], *, limit: int | None = None) -> list[str]:
    unique = list(dict.fromkeys(value for value in values if value))
    return unique if limit is None else unique[:limit]


_DIAGNOSTIC_TEXT_CAP = 512


def _diagnostic_text(value):
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    return text[:_DIAGNOSTIC_TEXT_CAP]


def _binding_diagnostic_event(execution, candidate, position, run_id, rejection,
                               evidence=None):
    binding = candidate.output_bindings[position]
    fixed = reanchor_verified_claim_bindings(execution, candidate).output_bindings[position]
    changed = any(
        getattr(binding, name, None) != getattr(fixed, name, None)
        for name in ("selector", "row_selector", "subject_selector"))
    value = getattr(binding, "value", None)
    unit = getattr(binding, "unit", None)
    declared_unit = None
    if unit is not None:
        declared_unit = {
            "kind": unit.kind,
            "value": _diagnostic_text(getattr(unit, "value", None)),
        }
    envelope = None
    if evidence is not None:
        envelope = evidence.get(getattr(binding, "evidence_id", None))
    capability = getattr(envelope, "capability", None) if envelope is not None else None
    return BindingDiagnostic(
        run_id=run_id,
        claim_index=candidate.claim_index,
        requirement_kind=binding.requirement_kind,
        requirement_id=_diagnostic_text(binding.requirement_id),
        output_id=_diagnostic_text(binding.output_id),
        node_id=_diagnostic_text(getattr(binding, "node_id", None)),
        evidence_id=_diagnostic_text(getattr(binding, "evidence_id", None)),
        selector=_diagnostic_text(getattr(binding, "selector", None)),
        row_selector=_diagnostic_text(getattr(binding, "row_selector", None)),
        subject_selector=_diagnostic_text(getattr(binding, "subject_selector", None)),
        subject_entity_type=_diagnostic_text(getattr(binding, "subject_entity_type", None)),
        subject_entity_id=_diagnostic_text(getattr(binding, "subject_entity_id", None)),
        declared_value={
            "kind": getattr(value, "kind", None),
            "value": _diagnostic_text(getattr(value, "value", None)),
        },
        declared_unit=declared_unit,
        domain=_diagnostic_text(getattr(binding, "domain", None)),
        evidence_capability=_diagnostic_text(capability),
        reanchor_changed=changed,
        rejection=_diagnostic_text(rejection),
    )


def _admitted_bindings(task, execution, draft, candidate):
    """Admit a candidate's bindings, isolating the ones that fail alone.

    Returns the claim to publish, the rejection message per dropped position,
    and the failure that withholds the claim instead. A binding whose declared
    shape does not match the row it names drops on its own, so one malformed
    output costs one output. When every binding drops this way the claim keeps
    no admitted output and is withheld as unbacked. Any other failure means the
    claim itself is not trustworthy, so nothing it binds publishes.
    """
    def admit(bindings):
        return admit_verified_claim_bindings(
            task, execution, draft,
            candidate.model_copy(update={"output_bindings": list(bindings)}))

    try:
        return admit(candidate.output_bindings), {}, None
    except ValueError:
        pass
    survivors: list = []
    rejections: dict[int, str] = {}
    withheld: ValueError | None = None
    for position, binding in enumerate(candidate.output_bindings):
        try:
            admit([binding])
        except BindingFormMismatch as exc:
            rejections[position] = str(exc)
            continue
        except ValueError as exc:
            rejections[position] = str(exc)
            withheld = withheld if withheld is not None else exc
            continue
        survivors.append(binding)
    if withheld is not None:
        return None, rejections, withheld
    if not survivors:
        return candidate.model_copy(update={"output_bindings": []}), rejections, None
    try:
        return admit(survivors), rejections, None
    except ValueError as exc:
        return None, rejections, exc


def _verified_claims(task, execution, draft, verification, evidence=None, *,
                     diagnostics=False, diagnostics_run_id="",
                     diagnostics_events=None):
    supported = {result.claim_index for result in verification.claim_results
                 if result.supported and not result.uncertain}
    admitted: list[VerifiedClaim] = []
    rejected: list[Gap] = []
    for index, claim in enumerate(draft.claims):
        if index not in supported:
            continue
        candidate = VerifiedClaim(
            claim_index=index, claim=claim,
            evidence_ids=list(claim.evidence_ids),
            sources=[ClaimSource(
                evidence_id=evidence_id, source=evidence[evidence_id].source,
                capability=evidence[evidence_id].capability,
                observed_at=evidence[evidence_id].observed_at,
                as_of=evidence[evidence_id].as_of,
                vintages=dict(evidence[evidence_id].vintages))
                for evidence_id in claim.evidence_ids
                if evidence and evidence_id in evidence],
            output_bindings=list(claim.output_bindings))
        admitted_claim, rejections, withheld = _admitted_bindings(
            task, execution, draft, candidate)
        if diagnostics and diagnostics_events is not None:
            for position, message in sorted(rejections.items()):
                diagnostics_events.append(_binding_diagnostic_event(
                    execution, candidate, position,
                    diagnostics_run_id, message, evidence))
        if withheld is not None:
            admitted.append(VerifiedClaim(
                claim_index=index, claim=claim,
                evidence_ids=list(claim.evidence_ids),
                sources=list(candidate.sources), output_bindings=[]))
            rejected.append(Gap(
                kind=GapKind.SYNTHESIS_INCOMPLETE,
                message=f"claim output binding rejected: {withheld}",
                evidence_ids=list(claim.evidence_ids),
                blocks=[f"claim:{index}"]))
            continue
        admitted.append(admitted_claim)
        if rejections and not admitted_claim.output_bindings:
            rejected.append(Gap(
                kind=GapKind.SYNTHESIS_INCOMPLETE,
                message=(f"claim:{index} output bindings not admitted: "
                         f"{rejections[min(rejections)]}"),
                evidence_ids=list(claim.evidence_ids),
                blocks=[f"claim:{index}"]))
        elif rejections:
            rejected.append(Gap(
                kind=GapKind.SYNTHESIS_INCOMPLETE,
                message=(f"claim:{index} output binding not admitted: "
                         f"{rejections[min(rejections)]}"),
                evidence_ids=list(claim.evidence_ids),
                blocks=[]))
    admitted = propagate_evidence_to_task(task, execution, draft, admitted)
    return admitted, rejected


def _failures_represented_by_precise_gaps(
    task: TaskSpec, execution: ExecutionResult, messages: Iterable[str],
) -> set[str]:
    requirements = {item.id: item for item in task.requirements}
    stop = {"a", "an", "and", "for", "in", "of", "the", "to", "with"}
    def terms(value: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", value.casefold())) - stop
    gap_terms = [terms(message) for message in messages]
    represented = set()
    for node in execution.plan.nodes:
        if node.status.value != "failed":
            continue
        descriptions = [
            requirements[item].description for item in node.covers_requirement_ids
            if item in requirements
        ]
        if any(
            overlap >= min(3, len(wanted), len(observed))
            for description in descriptions
            for wanted in [terms(description)]
            for observed in gap_terms
            for overlap in [len(wanted & observed)]
            if wanted and observed
        ):
            represented.add(node.id)
    return represented


def _redundant_failed_nodes(task: TaskSpec, execution: ExecutionResult) -> set[str]:
    from v2.runtime.subsumption import (
        arguments_share_subject, capability_subsumes,
    )

    completed = {
        node.id: node for node in execution.plan.nodes
        if node.status.value == "complete"
    }
    requirements = {item.id: item for item in task.requirements}
    redundant: set[str] = set()
    for failed in execution.plan.nodes:
        if failed.status.value != "failed":
            continue
        failed_requirements = set(failed.covers_requirement_ids)
        if failed_requirements and any(
            failed_requirements <= set(node.covers_requirement_ids)
            for node in completed.values()
        ):
            redundant.add(failed.id)
            continue
        narrow_name = next(iter(failed.capability_hints), "")
        for broader in completed.values():
            broad_name = next(iter(broader.capability_hints), "")
            if (capability_subsumes(broad_name, narrow_name)
                    and arguments_share_subject(
                        broader.arguments, failed.arguments)
                    and all(
                        requirement_id in requirements
                        and broad_name in requirements[requirement_id].capability_options
                        for requirement_id in failed.covers_requirement_ids
                    )):
                redundant.add(failed.id)
                break
    return redundant


def _uncovered_requirement_gaps(
    task: TaskSpec, execution: ExecutionResult,
) -> list[Gap]:
    covered = {
        requirement_id
        for node in execution.plan.nodes
        for requirement_id in node.covers_requirement_ids
    }
    return [
        Gap(
            kind=GapKind.MISSING_EVIDENCE,
            message=f"Uncovered requirement: {requirement.description}",
            blocks=[f"requirement:{requirement.id}"],
        )
        for requirement in task.requirements
        if requirement.id not in covered
    ]


def _empty_evidence_gaps(evidence) -> list[Gap]:
    return [
        Gap(
            kind=GapKind.MISSING_EVIDENCE,
            message=(f"{item.capability} returned no evidence values"),
            evidence_ids=[item.evidence_id],
        )
        for item in evidence
        if not any(True for _ in iter_values(item))
    ]


def _verification_gaps(draft, verification, execution_errors=None,
                       execution_error_codes=None, evidence_ids=None,
                       satisfied_requirement_ids=None) -> list[Gap]:
    missing_messages = [*draft.gaps]
    def message_terms(message: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-z0-9]+", message.casefold())
            if token not in {"a", "an", "and", "for", "in", "of", "the",
                             "to", "was", "were", "what", "with"}
        }
    for message in verification.missing_branches:
        terms = message_terms(message)
        if not any(
            terms and other_terms
            and len(terms & other_terms) >= min(3, len(terms), len(other_terms))
            for other_terms in map(message_terms, missing_messages)
        ):
            missing_messages.append(message)
    satisfied_requirement_ids = satisfied_requirement_ids or set()
    gaps = [Gap(
        kind=(GapKind.JUDGE_UNAVAILABLE
              if message in JUDGE_UNAVAILABLE_BRANCHES
              else GapKind.SYNTHESIS_INCOMPLETE
              if any(requirement_id.casefold().replace("_", " ") in
                     message.casefold().replace("_", " ")
                     for requirement_id in satisfied_requirement_ids)
              else GapKind.MISSING_EVIDENCE),
        message=message,
    ) for message in missing_messages]
    gaps.extend(Gap(kind=GapKind.SOURCE_CONFLICT, message=message)
                for message in verification.contradictions)
    for node_id, errors in (execution_errors or {}).items():
        if errors:
            name_resolution = (
                "profile/name_resolution_unavailable"
                in {str(code) for code in (execution_error_codes or {}).get(node_id, [])}
            )
            gaps.append(Gap(
                kind=(GapKind.PROFILE_NAME_RESOLUTION_UNAVAILABLE
                      if name_resolution else GapKind.EXECUTION_FAILURE),
                message=("profile/name_resolution unavailable"
                         if name_resolution
                         else f"execution failed for {node_id}"),
                blocks=[f"node:{node_id}"],
            ))
    for result in verification.claim_results:
        if not result.supported:
            claim_evidence = (
                list(draft.claims[result.claim_index].evidence_ids)
                if result.claim_index < len(draft.claims) else []
            )
            if evidence_ids is not None:
                claim_evidence = [
                    evidence_id for evidence_id in claim_evidence
                    if evidence_id in evidence_ids
                ]
            gaps.extend(Gap(kind=GapKind.UNSUPPORTED_CLAIM, message=reason,
                            evidence_ids=claim_evidence,
                            blocks=[f"claim:{result.claim_index}"])
                        for reason in result.reasons)
    return list({(gap.kind, gap.message, tuple(gap.blocks)): gap
                 for gap in gaps}.values())
