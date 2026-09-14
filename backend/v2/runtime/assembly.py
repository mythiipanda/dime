from __future__ import annotations

from collections.abc import Callable

from app.providers import ProviderName
from v2.adapters import (
    CAPABILITIES,
    ModelIntake,
    ModelPlanner,
    ModelSemanticVerifier,
    ModelSynthesizer,
    ProviderStructuredModel,
    RecordedStructuredModel,
    ToolCapability,
)
from v2.contracts import DraftReport, VerificationReport
from v2.runtime import PlanExecutor, RecordedCapability, RunLedger, Runtime
from v2.runtime.verifier import verify_mechanical


class MechanicalVerifier:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return verify_mechanical(task, draft, list(evidence.values()))


class NoRepair:
    async def repair(self, task, draft, evidence, verification) -> DraftReport:
        return draft


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
) -> tuple[Runtime, RunLedger]:
    ledger = RunLedger(run_id)
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
        executor=PlanExecutor(capabilities, max_concurrency=4, max_failures=2),
        synthesizer=ModelSynthesizer(
            model, provider=provider, model_name=model_name),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=ModelSemanticVerifier(
            model, provider=provider, model_name=model_name),
        repairer=NoRepair(),
        ledger=ledger,
        progress=progress,
    )
    return runtime, ledger
