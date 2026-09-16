from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable

from v2.contracts import (
    ClaimResult,
    ConversationTurn,
    ClaimSource,
    Gap,
    GapKind,
    VerificationReport,
    VerifiedClaim,
    VerificationStatus,
)
from v2.runtime.executor import PlanExecutor
from v2.runtime.interfaces import Intake, Planner, Repairer, Synthesizer, Verifier
from v2.runtime.ledger import LedgerKind, RunLedger, TerminalReason
from v2.runtime.models import RuntimeResult
from v2.domain.evidence import iter_values


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
    ) -> None:
        self._intake = intake
        self._planner = planner
        self._executor = executor
        self._synthesizer = synthesizer
        self._mechanical_verifier = mechanical_verifier
        self._semantic_verifier = semantic_verifier
        self._repairer = repairer
        self._repair_attempts = repair_attempts
        self._ledger = ledger
        self._progress = progress

    async def run(
        self, request: str, *, run_id: str | None = None,
        context: tuple[ConversationTurn, ...] = (),
    ) -> RuntimeResult:
        turn_id = run_id or "turn"
        if self._ledger is not None:
            if run_id is not None and self._ledger.run_id != run_id:
                raise ValueError("ledger run id does not match runtime run id")
            self._ledger.append(
                LedgerKind.TURN_START, turn_id=turn_id,
                data={"request": request},
            )
        try:
            intake_call = (self._intake.understand(request, context)
                           if context else self._intake.understand(request))
            task = await self._stage(turn_id, "understand", intake_call)
            if task.open_questions:
                raise ValueError(
                    "intake left unresolved questions: "
                    + "; ".join(task.open_questions))
            plan = await self._stage(
                turn_id, "plan", self._planner.plan(task))
            execution = await self._stage(
                turn_id, "execute",
                self._executor.execute(task, plan, run_id=run_id))
            draft = await self._stage(
                turn_id, "synthesize",
                self._synthesizer.synthesize(task, execution.evidence))
        except BaseException as exc:
            self._close_failed(turn_id, exc)
            raise
        evidence = {item.evidence_id: item for item in execution.evidence}
        try:
            verification = await self._stage(
                turn_id, "verify", self._verify(task, draft, evidence))
        except BaseException as exc:
            self._close_failed(turn_id, exc)
            raise
        repaired = False

        for attempt in range(self._repair_attempts):
            if (verification.status != VerificationStatus.REPAIR
                    or self._repairer is None):
                break
            suffix = "" if attempt == 0 else f":{attempt + 1}"
            try:
                draft = await self._stage(
                    turn_id, f"repair{suffix}",
                    self._repairer.repair(task, draft, evidence, verification))
                repaired = True
                verification = await self._stage(
                    turn_id, f"reverify{suffix}",
                    self._verify(task, draft, evidence))
            except BaseException as exc:
                self._close_failed(turn_id, exc)
                raise

        if verification.status == VerificationStatus.REPAIR:
            gaps = _unique(
                [
                    *draft.gaps,
                    *verification.missing_branches,
                    *verification.contradictions,
                    *verification.repair_instructions,
                ]
            )
            draft = draft.model_copy(update={"gaps": gaps})
            verification = verification.model_copy(
                update={"status": VerificationStatus.PARTIAL}
            )

        empty_evidence_gaps = _empty_evidence_gaps(execution.evidence)
        failed_nodes = {
            node.id for node in execution.plan.nodes
            if node.status.value == "failed"
        }
        unresolved_errors = {
            node_id: errors for node_id, errors in execution.errors.items()
            if node_id in failed_nodes
        }
        if ((draft.gaps or empty_evidence_gaps or unresolved_errors)
                and verification.status == VerificationStatus.PASS):
            verification = verification.model_copy(
                update={"status": VerificationStatus.PARTIAL}
            )
        verified_claims = _verified_claims(draft, verification, evidence)
        gaps = [
            *_verification_gaps(draft, verification, unresolved_errors),
            *empty_evidence_gaps,
        ]
        result = RuntimeResult(
            task=task,
            execution=execution,
            draft=draft,
            verification=verification,
            repaired=repaired,
            verified_claims=verified_claims,
            gaps=gaps,
        )
        if self._ledger is not None:
            self._ledger.append(
                LedgerKind.TURN_END, turn_id=turn_id,
                data={"reason": TerminalReason.COMPLETE.value,
                      "verification": verification.status.value},
            )
        return result

    async def _stage(self, turn_id: str, step_id: str, awaitable):
        if self._progress is not None:
            self._progress(step_id, "running")
        if self._ledger is not None:
            self._ledger.append(
                LedgerKind.STEP_START, turn_id=turn_id, step_id=step_id)
        try:
            result = await awaitable
        except BaseException as exc:
            if self._ledger is not None:
                reason = (TerminalReason.CANCELLED
                          if isinstance(exc, asyncio.CancelledError)
                          else TerminalReason.FAILED)
                self._ledger.append(
                    LedgerKind.STEP_END, turn_id=turn_id, step_id=step_id,
                    data={"reason": reason.value,
                          "error": f"{type(exc).__name__}: {exc}"},
                )
            if self._progress is not None:
                self._progress(step_id, "failed")
            raise
        if self._progress is not None:
            self._progress(step_id, "complete")
        if self._ledger is not None:
            self._ledger.append(
                LedgerKind.STEP_END, turn_id=turn_id, step_id=step_id,
                data={"reason": TerminalReason.COMPLETE.value})
        return result

    def _close_failed(self, turn_id: str, exc: BaseException) -> None:
        if self._ledger is None:
            return
        reason = (TerminalReason.CANCELLED
                  if isinstance(exc, asyncio.CancelledError)
                  else TerminalReason.FAILED)
        self._ledger.append(
            LedgerKind.TURN_END, turn_id=turn_id,
            data={"reason": reason.value,
                  "error": f"{type(exc).__name__}: {exc}"},
        )

    async def _verify(self, task, draft, evidence) -> VerificationReport:
        mechanical = await self._mechanical_verifier.verify(task, draft, evidence)
        expected = list(range(len(draft.claims)))
        mechanical_indices = sorted(
            result.claim_index for result in mechanical.claim_results)
        if mechanical_indices != expected:
            raise ValueError(
                "mechanical verifier must adjudicate every claim exactly once")
        if mechanical.status == VerificationStatus.REPAIR:
            return mechanical
        semantic = await self._semantic_verifier.verify(task, draft, evidence)
        observed = sorted(result.claim_index for result in semantic.claim_results)
        if observed != expected:
            raise ValueError(
                "semantic verifier must adjudicate every claim exactly once")
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
            [*mechanical.missing_branches, *semantic.missing_branches]
        ),
        contradictions=_unique([*mechanical.contradictions, *semantic.contradictions]),
        repair_instructions=_unique(
            [*mechanical.repair_instructions, *semantic.repair_instructions]
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
            reasons=_unique([*current.reasons, *result.reasons]),
        )
    return [merged[index] for index in sorted(merged)]


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


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


def _verification_gaps(draft, verification,
                       execution_errors=None) -> list[Gap]:
    gaps = [Gap(kind=GapKind.MISSING_EVIDENCE, message=message)
            for message in draft.gaps]
    gaps.extend(Gap(kind=GapKind.MISSING_EVIDENCE, message=message)
                for message in verification.missing_branches)
    gaps.extend(Gap(kind=GapKind.SOURCE_CONFLICT, message=message)
                for message in verification.contradictions)
    for node_id, errors in (execution_errors or {}).items():
        gaps.extend(Gap(kind=GapKind.EXECUTION_FAILURE, message=message,
                        blocks=[f"node:{node_id}"])
                    for message in errors)
    for result in verification.claim_results:
        if not result.supported:
            gaps.extend(Gap(kind=GapKind.UNSUPPORTED_CLAIM, message=reason,
                            blocks=[f"claim:{result.claim_index}"])
                        for reason in result.reasons)
    return list({(gap.kind, gap.message, tuple(gap.blocks)): gap
                 for gap in gaps}.values())
