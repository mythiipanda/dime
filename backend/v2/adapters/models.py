from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings
from app.providers import (
    GROQ_DEFAULT,
    INCEPTION_DEFAULT,
    MISTRAL_DEFAULT,
    OPENROUTER_DEFAULT,
    ProviderName,
    fallback_order,
)
from v2.contracts import (
    ConversationTurn,
    DraftReport,
    EvidenceEnvelope,
    Plan,
    TaskSpec,
    VerificationReport,
)
from v2.prompts import load_prompt
from v2.runtime.ledger import RequestEnvelope
from v2.skills import SkillLibrary, skill_hashes

T = TypeVar("T", bound=BaseModel)


class StructuredModel(Protocol):
    async def generate(
        self,
        *,
        schema: type[T],
        prompt: str,
        payload: Mapping[str, Any],
        envelope: RequestEnvelope,
    ) -> T: ...


class ProviderStructuredModel:
    def __init__(self, provider: ProviderName, model: str) -> None:
        self.provider = provider
        self.model = model
        self.last_provider: ProviderName | None = None
        self.last_model: str | None = None

    def _models(self) -> list[tuple[ProviderName, OpenAIChatModel]]:
        configs = {
            "mistral": ("https://api.mistral.ai/v1", settings.mistral_api_key,
                        settings.mistral_model or MISTRAL_DEFAULT),
            "openrouter": ("https://openrouter.ai/api/v1", settings.openrouter_api_key,
                           settings.openrouter_model or OPENROUTER_DEFAULT),
            "inception": ("https://api.inceptionlabs.ai/v1", settings.inception_api_key,
                          settings.inception_model or INCEPTION_DEFAULT),
            "groq": ("https://api.groq.com/openai/v1", settings.groq_api_key,
                     settings.groq_model or GROQ_DEFAULT),
        }
        models: list[tuple[ProviderName, OpenAIChatModel]] = []
        for provider in fallback_order(self.provider):
            base_url, api_key, fallback_model = configs[provider]
            if not api_key:
                continue
            headers = ({
                "HTTP-Referer": "https://github.com/mythiipanda/dime",
                "X-Title": "Dime NBA Analyst",
            } if provider == "openrouter" else None)
            client = AsyncOpenAI(
                base_url=base_url,
                api_key=api_key,
                timeout=settings.llm_timeout_s,
                max_retries=0,
                default_headers=headers,
            )
            models.append((provider, OpenAIChatModel(
                self.model if provider == self.provider else fallback_model,
                provider=OpenAIProvider(openai_client=client),
            )))
        return models

    async def generate(
        self,
        *,
        schema: type[T],
        prompt: str,
        payload: Mapping[str, Any],
        envelope: RequestEnvelope,
    ) -> T:
        models = self._models()
        if not models:
            raise RuntimeError("no configured structured-output provider")
        self.last_provider = None
        self.last_model = None
        errors: list[str] = []
        user_prompt = json.dumps(payload, sort_keys=True, default=str)
        for provider, model in models:
            try:
                agent = Agent(
                    model,
                    instructions=prompt,
                    output_type=NativeOutput(schema, strict=True),
                    retries=settings.llm_max_retries,
                )
                result = await agent.run(user_prompt)
                self.last_provider = provider
                self.last_model = model.model_name
                return result.output
            except Exception as exc:
                errors.append(f"{provider}: {str(exc)[:160]}")
        raise RuntimeError("all structured-output providers failed: " + " | ".join(errors))


class ModelStage:
    prompt_name: str
    route: str
    schema: type[BaseModel]

    def __init__(
        self,
        model: StructuredModel,
        *,
        provider: str,
        model_name: str,
        planner_version: str = "v2",
        budgets: Mapping[str, int | float] | None = None,
        skill_library: SkillLibrary | None = None,
    ) -> None:
        for name, value in {
            "provider": provider,
            "model_name": model_name,
            "planner_version": planner_version,
        }.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        self._model = model
        self._provider = provider
        self._model_name = model_name
        self._planner_version = planner_version
        self._budgets = dict(budgets or {})
        self._skills = skill_library or SkillLibrary()
        self.last_envelope: RequestEnvelope | None = None

    async def _generate(self, payload: Mapping[str, Any]) -> Any:
        prompt = load_prompt(self.prompt_name)
        envelope = RequestEnvelope.freeze(
            provider=self._provider,
            model=self._model_name,
            route=self.route,
            prompt=prompt,
            context=payload,
            tool_schemas=self.schema.model_json_schema(),
            planner_version=self._planner_version,
            budgets=self._budgets,
            skill_hashes=skill_hashes(list(payload.get("skills", []))),
        )
        self.last_envelope = envelope
        return await self._model.generate(
            schema=self.schema,
            prompt=prompt,
            payload=payload,
            envelope=envelope,
        )


class ModelIntake(ModelStage):
    prompt_name = "intake"
    route = "intake"
    schema = TaskSpec

    def __init__(self, *args: Any, capability_catalog: Mapping[str, str], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._catalog = dict(capability_catalog)

    async def understand(
        self, request: str, context: Sequence[ConversationTurn] = ()
    ) -> TaskSpec:
        task = await self._generate({
            "question": request,
            "current_date": datetime.now(UTC).date().isoformat(),
            "conversation_context": [
                turn.model_dump(mode="json") for turn in context[-8:]
            ],
            "capability_catalog": self._catalog,
            "skill_catalog": self._skills.catalog(),
        })
        self._skills.activate(task.skills)
        unknown = sorted(set(task.required_evidence) - self._catalog.keys())
        if unknown:
            raise ValueError(f"intake selected unknown capabilities: {unknown}")
        return task


class ModelPlanner(ModelStage):
    prompt_name = "planner"
    route = "planner"
    schema = Plan

    def __init__(self, *args: Any, capability_catalog: Mapping[str, str], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._catalog = dict(capability_catalog)

    async def plan(self, task: TaskSpec) -> Plan:
        return await self._generate({
            "task": task.model_dump(mode="json"),
            "capability_catalog": self._catalog,
            "skills": self._skills.activate(task.skills),
        })


def _validate_draft(
    draft: DraftReport, evidence: Sequence[EvidenceEnvelope]
) -> DraftReport:
    known = {item.evidence_id for item in evidence}
    unknown = sorted({evidence_id for claim in draft.claims
                      for evidence_id in claim.evidence_ids
                      if evidence_id not in known})
    if unknown:
        raise ValueError(f"draft cites unknown evidence ids: {unknown}")
    return draft


class ModelSynthesizer(ModelStage):
    prompt_name = "synthesizer"
    route = "synthesizer"
    schema = DraftReport

    async def synthesize(
        self, task: TaskSpec, evidence: Sequence[EvidenceEnvelope]
    ) -> DraftReport:
        draft = await self._generate(
            {
                "task": task.model_dump(mode="json"),
                "evidence": [item.model_dump(mode="json") for item in evidence],
                "skills": self._skills.activate(task.skills),
            }
        )
        return _validate_draft(draft, evidence)


class ModelRepairer(ModelStage):
    prompt_name = "repair_answer"
    route = "repair"
    schema = DraftReport

    async def repair(
        self,
        task: TaskSpec,
        draft: DraftReport,
        evidence: Mapping[str, EvidenceEnvelope],
        verification: VerificationReport,
    ) -> DraftReport:
        repaired = await self._generate({
            "task": task.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
            "skills": self._skills.activate(task.skills),
            "admitted_evidence": [
                item.model_dump(mode="json") for item in evidence.values()
            ],
        })
        repaired = _validate_draft(repaired, list(evidence.values()))
        repaired_keys = {
            (claim.text, claim.kind, tuple(claim.evidence_ids),
             claim.calculation_id, claim.confidence)
            for claim in repaired.claims
        }
        rejected = {
            (draft.claims[result.claim_index].text,
             draft.claims[result.claim_index].kind,
             tuple(draft.claims[result.claim_index].evidence_ids),
             draft.claims[result.claim_index].calculation_id,
             draft.claims[result.claim_index].confidence)
            for result in verification.claim_results
            if not result.supported and result.claim_index < len(draft.claims)
        }
        if rejected & repaired_keys:
            raise ValueError("repair retained a rejected claim unchanged")
        return repaired


class ModelSemanticVerifier(ModelStage):
    prompt_name = "verifier"
    route = "semantic_verifier"
    schema = VerificationReport

    async def verify(
        self,
        task: TaskSpec,
        draft: DraftReport,
        evidence: Mapping[str, EvidenceEnvelope],
    ) -> VerificationReport:
        compact = [
            {
                "evidence_id": item.evidence_id,
                "capability": item.capability,
                "source": item.source,
                "observed_at": item.observed_at.isoformat(),
                "season": item.season,
                "vintages": item.vintages,
                "task_season_scoped": item.task_season_scoped,
                "as_of": item.as_of.isoformat() if item.as_of else None,
                "entities": [entity.model_dump(mode="json")
                             for entity in item.entities],
                "units": item.units,
                "metric_definitions": item.metric_definitions,
                "qualification": item.qualification,
                "coverage": item.coverage,
                "warnings": item.warnings,
                "lineage": item.lineage,
                "rows": item.rows,
            }
            for item in evidence.values()
        ]
        report = await self._generate(
            {
                "task": task.model_dump(mode="json"),
                "draft": draft.model_dump(mode="json"),
                "evidence": compact,
                "skills": self._skills.activate(task.skills),
            }
        )
        expected = list(range(len(draft.claims)))
        observed = sorted(item.claim_index for item in report.claim_results)
        if observed != expected or len(observed) != len(set(observed)):
            raise ValueError(
                "semantic verifier must adjudicate every claim exactly once")
        return report



class RecordedStructuredModel:
    def __init__(self, model: StructuredModel, ledger: Any, *, turn_id: str) -> None:
        if not turn_id.strip():
            raise ValueError("recorded model turn id must be non-empty")
        self._model = model
        self._ledger = ledger
        self._turn_id = turn_id
        self._sequence = 0

    async def generate(
        self,
        *,
        schema: type[T],
        prompt: str,
        payload: Mapping[str, Any],
        envelope: RequestEnvelope,
    ) -> T:
        from v2.runtime.ledger import LedgerKind

        self._sequence += 1
        call_id = f"model:{self._turn_id}:{self._sequence}"
        self._ledger.append(
            LedgerKind.MODEL_REQUEST,
            turn_id=self._turn_id,
            call_id=call_id,
            data=envelope.model_dump(mode="json"),
        )
        try:
            result = await self._model.generate(
                schema=schema,
                prompt=prompt,
                payload=payload,
                envelope=envelope,
            )
            if not isinstance(result, schema):
                raise TypeError(
                    f"structured model must return {schema.__name__}")
        except BaseException as exc:
            self._ledger.append(
                LedgerKind.ASSISTANT_ATTEMPT,
                turn_id=self._turn_id,
                call_id=call_id,
                data={"status": "failed", "error": f"{type(exc).__name__}: {exc}"},
            )
            raise
        actual_provider = getattr(self._model, "last_provider", None)
        actual_model = getattr(self._model, "last_model", None)
        self._ledger.append(
            LedgerKind.ASSISTANT_ATTEMPT,
            turn_id=self._turn_id,
            call_id=call_id,
            data={
                "status": "accepted",
                "output": result.model_dump(mode="json"),
                "provider": actual_provider or envelope.provider,
                "model": actual_model or envelope.model,
                "used_fallback": (
                    (actual_provider or envelope.provider) != envelope.provider
                    or (actual_model or envelope.model) != envelope.model
                ),
            },
        )
        return result
