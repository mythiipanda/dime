from __future__ import annotations

from collections.abc import Iterable

from v2.contracts import (
    ClaimResult,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime.executor import PlanExecutor
from v2.runtime.interfaces import Intake, Planner, Repairer, Synthesizer, Verifier
from v2.runtime.models import RuntimeResult


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
    ) -> None:
        self._intake = intake
        self._planner = planner
        self._executor = executor
        self._synthesizer = synthesizer
        self._mechanical_verifier = mechanical_verifier
        self._semantic_verifier = semantic_verifier
        self._repairer = repairer

    async def run(self, request: str) -> RuntimeResult:
        task = await self._intake.understand(request)
        plan = await self._planner.plan(task)
        execution = await self._executor.execute(task, plan)
        draft = await self._synthesizer.synthesize(task, execution.evidence)
        evidence = {item.evidence_id: item for item in execution.evidence}
        verification = await self._verify(task, draft, evidence)
        repaired = False

        if (
            verification.status == VerificationStatus.REPAIR
            and self._repairer is not None
        ):
            draft = await self._repairer.repair(task, draft, evidence, verification)
            repaired = True
            verification = await self._verify(task, draft, evidence)

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

        return RuntimeResult(
            task=task,
            execution=execution,
            draft=draft,
            verification=verification,
            repaired=repaired,
        )

    async def _verify(self, task, draft, evidence) -> VerificationReport:
        mechanical = await self._mechanical_verifier.verify(task, draft, evidence)
        semantic = await self._semantic_verifier.verify(task, draft, evidence)
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
