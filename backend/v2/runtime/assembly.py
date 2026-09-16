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
    WebFetchCapability,
    WebSearchCapability,
)
from v2.contracts import DraftReport, VerificationReport
from v2.runtime import FileLedger, PlanExecutor, RecordedCapability, RunLedger, Runtime
from v2.runtime.checkpoints import FileCheckpointStore
from v2.runtime.policy import ExecutionMode, ExecutionPolicy
from v2.runtime.verifier import verify_mechanical
from v2.adapters.web import WebFetchRequest, WebSearchRequest
from v2.adapters.capabilities import CAPABILITY_DESCRIPTIONS
from v2.skills import SkillLibrary


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



def _structural_schema(value):
    if isinstance(value, dict):
        return {
            key: _structural_schema(item)
            for key, item in value.items()
            if key not in {"description", "title"}
        }
    if isinstance(value, list):
        return [_structural_schema(item) for item in value]
    return value


def capability_catalog() -> dict[str, dict]:
    """Provider-neutral descriptions plus accepted argument schemas."""
    from app.tools import v1_tools

    by_tool = {tool.name: tool for tool in v1_tools}
    catalog: dict[str, dict] = {}
    for name, spec in CAPABILITIES.items():
        tool = by_tool.get(spec.tool_name)
        args_schema = (tool.args_schema.model_json_schema()
                       if tool is not None and tool.args_schema is not None
                       else {"type": "object", "properties": {}})
        catalog[name] = {
            "description": CAPABILITY_DESCRIPTIONS[name],
            "arguments": _structural_schema(args_schema),
        }
    catalog.update({
        "web_search": {
            "description": "Discover current public sources; snippets are discovery only.",
            "arguments": _structural_schema(WebSearchRequest.model_json_schema()),
        },
        "web_fetch": {
            "description": "Extract one selected result from exactly one web_search dependency.",
            "arguments": _structural_schema(WebFetchRequest.model_json_schema()),
        },
    })
    return catalog


def build_runtime(
    *,
    provider: ProviderName,
    model_name: str,
    run_id: str,
    progress: Callable[[str, str], None] | None = None,
    policy: ExecutionPolicy | None = None,
    ledger_dir: str | Path | None = None,
) -> tuple[Runtime, RunLedger | FileLedger]:
    if not run_id or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for char in run_id
    ):
        raise ValueError("run_id may contain only letters, numbers, '-' and '_'")
    if policy is not None and ledger_dir is not None:
        raise ValueError("ledger_dir must be configured through policy when policy is provided")
    policy = (ExecutionPolicy.live(ledger_dir=ledger_dir) if policy is None
              else ExecutionPolicy.model_validate(policy.model_dump()))
    if policy.mode in {ExecutionMode.REPLAY, ExecutionMode.EVAL}:
        raise NotImplementedError(
            f"{policy.mode.value} runtime assembly is not implemented")
    resolved_ledger_dir = policy.ledger_dir
    ledger = (FileLedger(Path(resolved_ledger_dir) / f"{run_id}.jsonl", run_id)
              if resolved_ledger_dir is not None else RunLedger(run_id))
    skills = SkillLibrary()
    model = RecordedStructuredModel(
        ProviderStructuredModel(provider, model_name), ledger, turn_id=run_id)
    catalog = capability_catalog()
    capabilities = {
        name: RecordedCapability(ToolCapability(name), ledger, turn_id=run_id)
        for name in CAPABILITIES
    }
    capabilities.update({
        "web_search": RecordedCapability(
            WebSearchCapability(), ledger, turn_id=run_id),
        "web_fetch": RecordedCapability(
            WebFetchCapability(), ledger, turn_id=run_id),
    })
    runtime = Runtime(
        intake=ModelIntake(model, provider=provider, model_name=model_name,
                          capability_catalog=catalog, skill_library=skills),
        planner=ModelPlanner(model, provider=provider, model_name=model_name,
                             capability_catalog=catalog, skill_library=skills),
        executor=PlanExecutor(
            capabilities, max_concurrency=policy.max_concurrency,
            max_failures=policy.max_failures,
            checkpoint_store=(FileCheckpointStore(policy.checkpoint_dir)
                              if policy.checkpoint_dir is not None else None)),
        synthesizer=ModelSynthesizer(
            model, provider=provider, model_name=model_name, skill_library=skills),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=ModelSemanticVerifier(
            model, provider=provider, model_name=model_name, skill_library=skills),
        repairer=ModelRepairer(
            model, provider=provider, model_name=model_name, skill_library=skills),
        repair_attempts=policy.repair_attempts,
        ledger=ledger,
        progress=progress,
    )
    return runtime, ledger
