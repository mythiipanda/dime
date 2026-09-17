from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Callable, Iterable

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
from v2.runtime.interfaces import Intake, Planner, Repairer, Synthesizer, Verifier
from v2.runtime.ledger import LedgerKind, RunLedger, TerminalReason, exception_text
from v2.runtime.models import ExecutionResult, RuntimeResult
from v2.domain.evidence import iter_values


class PreToolTimeoutError(TimeoutError):
    """Intake and planning exceeded the configured pre-tool budget."""


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
        pre_tool_timeout_s: float | None = None,
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
        self._progress = progress
        self._pre_tool_timeout_s = pre_tool_timeout_s

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
        if self._ledger is not None:
            if run_id is not None and self._ledger.run_id != run_id:
                raise ValueError("ledger run id does not match runtime run id")
            self._ledger.append(
                LedgerKind.TURN_START, turn_id=turn_id,
                data={"request": request},
            )
        try:
            async def prepare(deadline: float | None = None):
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
                if prepared_task.open_questions:
                    raise ValueError(
                        "intake left unresolved questions: "
                        + "; ".join(prepared_task.open_questions))
                prepared_plan = Plan.model_validate((await self._stage(
                    turn_id, "plan", self._planner.plan(prepared_task),
                    timeout_s=remaining())).model_dump())
                return prepared_task, prepared_plan

            if self._pre_tool_timeout_s is None:
                task, plan = await prepare()
            else:
                try:
                    task, plan = await prepare(
                        time.perf_counter() + self._pre_tool_timeout_s)
                except TimeoutError as exc:
                    raise PreToolTimeoutError(
                        f"intake and planning exceeded "
                        f"{self._pre_tool_timeout_s:g} seconds") from exc
            execution = ExecutionResult.model_validate((await self._stage(
                turn_id, "execute",
                self._executor.execute(task, plan, run_id=run_id))).model_dump())
            draft = DraftReport.model_validate((await self._stage(
                turn_id, "synthesize",
                self._synthesizer.synthesize(task, execution.evidence))).model_dump())
        except BaseException as exc:
            self._close_failed(turn_id, exc, started=turn_started)
            raise
        evidence = {item.evidence_id: item for item in execution.evidence}
        try:
            verification = await self._stage(
                turn_id, "verify", self._verify(task, draft, evidence))
        except BaseException as exc:
            self._close_failed(turn_id, exc, started=turn_started)
            raise
        pre_repair_draft = draft.model_copy(deep=True)
        repaired = False

        for attempt in range(self._repair_attempts):
            if (verification.status != VerificationStatus.REPAIR
                    or self._repairer is None):
                break
            suffix = "" if attempt == 0 else f":{attempt + 1}"
            try:
                repair_call = self._repairer.repair(
                    task, draft, evidence, verification)
                draft = DraftReport.model_validate((await self._stage(
                    turn_id, f"repair{suffix}", repair_call)).model_dump())
                repaired = True
                verification = await self._stage(
                    turn_id, f"reverify{suffix}",
                    self._verify(task, draft, evidence))
            except BaseException as exc:
                self._close_failed(turn_id, exc, started=turn_started)
                raise

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
        failed_nodes = {
            node.id for node in execution.plan.nodes
            if node.status.value == "failed"
        }
        unresolved_errors = {
            node_id: errors for node_id, errors in execution.errors.items()
            if node_id in failed_nodes
        }
        skipped_nodes = [
            node.id for node in execution.plan.nodes
            if node.status.value == "skipped"
        ]
        empty_draft_gaps = ([] if (
            draft.claims or draft.gaps or empty_evidence_gaps
            or unresolved_errors or skipped_nodes
        ) else [Gap(
            kind=GapKind.MISSING_EVIDENCE,
            message="synthesis produced no publishable claims",
        )])
        if ((draft.gaps or empty_evidence_gaps or empty_draft_gaps
                or unresolved_errors or skipped_nodes)
                and verification.status == VerificationStatus.PASS):
            verification = verification.model_copy(
                update={"status": VerificationStatus.PARTIAL}
            )
        verified_claims = _verified_claims(draft, verification, evidence)
        gaps = [
            *_verification_gaps(
                draft, verification, unresolved_errors, evidence_ids=set(evidence)),
            *empty_evidence_gaps,
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
        pre_repair_keys = {
            (claim.text, claim.kind, tuple(claim.evidence_ids), claim.calculation_id)
            for claim in pre_repair_draft.claims
            if claim.kind.value in {"observed", "derived"}
        }
        published_keys = {
            (claim.text, claim.kind, tuple(claim.evidence_ids), claim.calculation_id)
            for claim in draft.claims
        }
        structural_flags = (
            ["repair_stripped_evidence_claim"]
            if repaired and pre_repair_keys - published_keys else []
        )
        result = RuntimeResult(
            task=task,
            execution=execution,
            draft=draft,
            verification=verification,
            repaired=repaired,
            structural_flags=structural_flags,
            verified_claims=verified_claims,
            gaps=gaps[:256],
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
            return mechanical
        semantic = VerificationReport.model_validate(
            (await self._semantic_verifier.verify(task, draft, evidence)).model_dump()
        )
        observed = [result.claim_index for result in semantic.claim_results]
        if (len(observed) != len(set(observed))
                or any(index not in expected for index in observed)):
            raise ValueError(
                "semantic verifier returned duplicate or unknown claim indices")
        return _merge_verification(mechanical, semantic)


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
        )
    return [merged[index] for index in sorted(merged)]


def _unique(values: Iterable[str], *, limit: int | None = None) -> list[str]:
    unique = list(dict.fromkeys(value for value in values if value))
    return unique if limit is None else unique[:limit]


def _verified_claims(draft, verification, evidence=None) -> list[VerifiedClaim]:
    supported = {
        result.claim_index for result in verification.claim_results
        if result.supported
    }
    return [
        VerifiedClaim(
            claim_index=index, claim=claim,
            evidence_ids=list(claim.evidence_ids),
            sources=[ClaimSource(
                evidence_id=evidence_id,
                source=evidence[evidence_id].source,
                capability=evidence[evidence_id].capability)
                for evidence_id in claim.evidence_ids
                if evidence and evidence_id in evidence])
        for index, claim in enumerate(draft.claims)
        if index in supported
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
                       evidence_ids=None) -> list[Gap]:
    gaps = [Gap(kind=GapKind.MISSING_EVIDENCE, message=message)
            for message in draft.gaps]
    gaps.extend(Gap(kind=GapKind.MISSING_EVIDENCE, message=message)
                for message in verification.missing_branches)
    gaps.extend(Gap(kind=GapKind.SOURCE_CONFLICT, message=message)
                for message in verification.contradictions)
    for node_id, errors in (execution_errors or {}).items():
        if errors:
            gaps.append(Gap(
                kind=GapKind.EXECUTION_FAILURE,
                message=f"execution failed for {node_id}",
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
