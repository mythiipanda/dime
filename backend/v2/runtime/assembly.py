from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.providers import ProviderName
from v2.adapters import (
    CAPABILITIES,
    ModelIntake,
    ModelPlanner,
    ModelRepairer,
    ModelSemanticVerifier,
    ModelSynthesizer,
    ProviderStructuredModel,
    RecordedStructuredModel,
    ToolCapability,
)
from v2.contracts import DraftReport, VerificationReport
from v2.runtime import FileLedger, PlanExecutor, RecordedCapability, RunLedger, Runtime
from v2.runtime.policy import ExecutionPolicy
from v2.runtime.verifier import verify_mechanical


class MechanicalVerifier:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return verify_mechanical(task, draft, list(evidence.values()))


class EvidenceBoundRepair:
    async def repair(self, task, draft, evidence, verification) -> DraftReport:
        rejected = {
            item.claim_index for item in verification.claim_results
            if not item.supported
        }
        claims = [
            claim for index, claim in enumerate(draft.claims)
            if index not in rejected
        ]
        gaps = list(dict.fromkeys([
            *draft.gaps,
            *verification.missing_branches,
            *verification.contradictions,
            *verification.repair_instructions,
        ]))
        return draft.model_copy(update={"claims": claims, "gaps": gaps})


def capability_catalog() -> dict[str, str]:
    return {
        name: spec.tool_name.replace("_", " ")
        for name, spec in CAPABILITIES.items()
    }


def build_runtime(
    *,
    provider: ProviderName,
    model_name: str,
    run_id: str,
    progress: Callable[[str, str], None] | None = None,
    policy: ExecutionPolicy | None = None,
    ledger_dir: str | Path | None = None,
) -> tuple[Runtime, RunLedger | FileLedger]:
    policy = policy or ExecutionPolicy.live(ledger_dir=ledger_dir)
    resolved_ledger_dir = policy.ledger_dir
    ledger = (FileLedger(Path(resolved_ledger_dir) / f"{run_id}.jsonl", run_id)
              if resolved_ledger_dir is not None else RunLedger(run_id))
    model = RecordedStructuredModel(
        ProviderStructuredModel(provider, model_name), ledger, turn_id=run_id)
    catalog = capability_catalog()
    capabilities = {
        name: RecordedCapability(ToolCapability(name), ledger, turn_id=run_id)
        for name in CAPABILITIES
    }
    runtime = Runtime(
        intake=ModelIntake(model, provider=provider, model_name=model_name,
                          capability_catalog=catalog),
        planner=ModelPlanner(model, provider=provider, model_name=model_name,
                             capability_catalog=catalog),
        executor=PlanExecutor(
            capabilities, max_concurrency=policy.max_concurrency,
            max_failures=policy.max_failures),
        synthesizer=ModelSynthesizer(
            model, provider=provider, model_name=model_name),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=ModelSemanticVerifier(
            model, provider=provider, model_name=model_name),
        repairer=ModelRepairer(
            model, provider=provider, model_name=model_name),
        ledger=ledger,
        progress=progress,
    )
    return runtime, ledger
