from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.providers import ProviderName, invoke_with_fallback
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

    async def generate(
        self,
        *,
        schema: type[T],
        prompt: str,
        payload: Mapping[str, Any],
        envelope: RequestEnvelope,
    ) -> T:
        response = await invoke_with_fallback(
            self.provider,
            self.model,
            [
                SystemMessage(content=prompt),
                HumanMessage(content=json.dumps(payload, sort_keys=True, default=str)),
            ],
            response_format={"type": "json_object"},
        )
        content = response.content
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in content
            )
        return schema.model_validate_json(_json_object(str(content)))


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


class ModelSynthesizer(ModelStage):
    prompt_name = "synthesizer"
    route = "synthesizer"
    schema = DraftReport

    async def synthesize(
        self, task: TaskSpec, evidence: Sequence[EvidenceEnvelope]
    ) -> DraftReport:
        return await self._generate(
            {
                "task": task.model_dump(mode="json"),
                "evidence": [item.model_dump(mode="json") for item in evidence],
                "skills": self._skills.activate(task.skills),
            }
        )


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
        return await self._generate({
            "task": task.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
            "skills": self._skills.activate(task.skills),
            "admitted_evidence": [
                item.model_dump(mode="json") for item in evidence.values()
            ],
        })


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
                "season": item.season,
                "vintages": item.vintages,
                "task_season_scoped": item.task_season_scoped,
                "qualification": item.qualification,
                "coverage": item.coverage,
                "rows": item.rows,
            }
            for item in evidence.values()
        ]
        return await self._generate(
            {
                "task": task.model_dump(mode="json"),
                "draft": draft.model_dump(mode="json"),
                "evidence": compact,
                "skills": self._skills.activate(task.skills),
            }
        )


def _json_object(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("model did not return a JSON object")
    return text[start : end + 1]

class RecordedStructuredModel:
    def __init__(self, model: StructuredModel, ledger: Any, *, turn_id: str) -> None:
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
        except BaseException as exc:
            self._ledger.append(
                LedgerKind.ASSISTANT_ATTEMPT,
                turn_id=self._turn_id,
                call_id=call_id,
                data={"status": "failed", "error": f"{type(exc).__name__}: {exc}"},
            )
            raise
        self._ledger.append(
            LedgerKind.ASSISTANT_ATTEMPT,
            turn_id=self._turn_id,
            call_id=call_id,
            data={"status": "accepted", "output": result.model_dump(mode="json")},
        )
        return result
