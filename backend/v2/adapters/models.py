from __future__ import annotations

import asyncio
import json
import hashlib
import random
import re
import time
import marshal
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol, TypeVar

from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, RateLimitError
from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.exceptions import ContentFilterError, ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings
from app.tools.rating_metrics import (TEAM_RATING_METRICS,
                                      RankedTeamConstraintError,
                                      canonical_ranking_direction,
                                      canonical_team_rating_metric,
                                      ranked_team_constraints)
from app.providers import (
    GROQ_DEFAULT,
    NVIDIA_NIM_BASE_URL,
    NVIDIA_NIM_DEFAULT,
    INCEPTION_DEFAULT,
    MISTRAL_DEFAULT,
    OPENROUTER_DEFAULT,
    ProviderName,
    fallback_order,
    _mistral_free_model,
    _nvidia_nim_model,
    _openrouter_free_model,
    is_free_model,
)
from v2.contracts import (
    ConversationTurn,
    Claim,
    DraftReport,
    EvidenceEnvelope,
    Plan,
    PlanNode,
    RequirementReview,
    TaskSpec,
    VerificationReport,
)
from v2.prompts import load_prompt
from v2.runtime.ledger import RequestEnvelope, exception_text
from v2.runtime.budget import RUN_MODEL_DEADLINE
from v2.skills import SkillLibrary, skill_hashes

T = TypeVar("T", bound=BaseModel)


def _imported_module_code_sha256() -> str:
    code = __loader__.get_code(__name__) if __loader__ is not None else None
    if code is None:
        raise RuntimeError("provider models module has no loader code identity")
    return hashlib.sha256(marshal.dumps(code)).hexdigest()


_LOADED_MODULE_CODE_SHA256 = _imported_module_code_sha256()


class StructuredModel(Protocol):
    async def generate(
        self,
        *,
        schema: type[T],
        prompt: str,
        payload: Mapping[str, Any],
        envelope: RequestEnvelope,
    ) -> T: ...


ROUTE_POLICIES: dict[str, dict[str, Any]] = {
    "intake": {"primary_attempts": 2, "attempt_timeout_s": 6.0,
               "total_budget_s": 18.0, "secondary_limit": 1,
               "transient_classes": frozenset({"timeout", "rate_limit", "network", "server_error", "provider_error"}),
               "deterministic_fallback": False},
    "requirement_review": {"primary_attempts": 2, "attempt_timeout_s": 8.0,
               "total_budget_s": 12.0, "secondary_limit": 1,
               "transient_classes": frozenset({"timeout", "rate_limit", "network", "server_error", "provider_error"}),
               "deterministic_fallback": True},
    "planner": {"primary_attempts": 2, "attempt_timeout_s": 4.0,
               "total_budget_s": 12.0, "secondary_limit": 1,
               "transient_classes": frozenset({"timeout", "rate_limit", "network", "server_error", "provider_error"}),
               "deterministic_fallback": False},
    "synthesizer": {"primary_attempts": 1, "attempt_timeout_s": 6.0,
               "total_budget_s": 6.0, "secondary_limit": 0,
               "transient_classes": frozenset(), "deterministic_fallback": True},
    "semantic_verifier": {"primary_attempts": 1, "attempt_timeout_s": 6.0,
               "total_budget_s": 6.0, "secondary_limit": 0,
               "transient_classes": frozenset(), "deterministic_fallback": True},
}
_DEFAULT_ROUTE_POLICY = {"primary_attempts": 1, "attempt_timeout_s": 6.0,
    "total_budget_s": 12.0, "secondary_limit": 1,
    "transient_classes": frozenset({"timeout", "rate_limit", "network", "server_error", "provider_error"}),
    "deterministic_fallback": False}


SAFE_FAILURE_EXCEPTION_CLASSES = frozenset({
    "UnexpectedModelBehavior", "ToolRetryError", "ValidationError",
    "ContentFilterError", "ExceptionGroup", "BaseExceptionGroup",
    "TimeoutError", "APITimeoutError", "APIConnectionError",
    "RateLimitError", "ModelHTTPError", "ConnectError", "NetworkError",
    "RuntimeError", "ValueError", "TypeError", "JSONDecodeError",
})
SAFE_FAILURE_PHASES = frozenset({"content_filter", "no_tool_or_empty",
    "json_or_schema_validation", "http", "transport", "timeout", "unknown"})
MODEL_ROUTES = frozenset(ROUTE_POLICIES)
SAFE_PYDANTIC_ERROR_TYPES = frozenset({
    "extra_forbidden", "json_invalid", "literal_error", "missing",
    "model_type", "string_type", "int_type", "int_parsing", "bool_type",
    "list_type", "dict_type", "greater_than_equal", "too_long",
    "too_short", "value_error",
    "claim_unsupported_missing_reason", "claim_supported_has_reasons",
    "verification_duplicate_claim_index", "verification_finding_empty",
    "verification_finding_duplicate", "verification_pass_with_findings",
    "verification_repair_without_findings",
})
SAFE_FAILURE_VALIDATION_SUBTYPES = frozenset({
    "unsupported_claim_missing_reason", "supported_claim_has_reasons",
    "pass_with_findings", "repair_without_findings", "duplicate_claim_index",
    "duplicate_or_empty_finding", "other_contract_invariant",
    "not_applicable",
})
_VALIDATION_SUBTYPE_BY_ERROR_TYPE = {
    "claim_unsupported_missing_reason": "unsupported_claim_missing_reason",
    "claim_supported_has_reasons": "supported_claim_has_reasons",
    "verification_pass_with_findings": "pass_with_findings",
    "verification_repair_without_findings": "repair_without_findings",
    "verification_duplicate_claim_index": "duplicate_claim_index",
    "verification_finding_empty": "duplicate_or_empty_finding",
    "verification_finding_duplicate": "duplicate_or_empty_finding",
}


def _safe_exception_name(value: type[BaseException] | str) -> str:
    name = value if isinstance(value, str) else value.__name__
    return name if name in SAFE_FAILURE_EXCEPTION_CLASSES else "<unknown-exception>"


def _safe_pydantic_error_type(value: object) -> str:
    name = str(value)
    return name if name in SAFE_PYDANTIC_ERROR_TYPES else "<unknown-error-type>"


class ProviderStructuredModel:
    def __init__(self, provider: ProviderName, model: str) -> None:
        self.provider = provider
        self.model = model
        self.last_provider: ProviderName | None = None
        self.last_model: str | None = None
        self.last_failures: list[dict[str, str]] = []

    @staticmethod
    def _failure_class(exc: BaseException) -> str:
        """Bounded provider diagnostics without payloads or raw responses."""
        name = type(exc).__name__.casefold()
        detail = str(exc).casefold()
        if "timeout" in name or "timed out" in detail:
            return "timeout"
        if any(code in detail for code in ("500", "502", "503", "504")):
            return "server_error"
        if "rate" in name or "429" in detail or "rate limit" in detail:
            return "rate_limit"
        if "auth" in name or "401" in detail or "403" in detail:
            return "authentication"
        if ("validation" in name or "schema" in detail
                or "structured" in detail or "json" in detail):
            return "structured_output"
        if "context" in detail or "token" in detail and "limit" in detail:
            return "context_limit"
        if "connect" in name or "network" in detail:
            return "network"
        return "provider_error"

    @staticmethod
    def _safe_failure_taxonomy(exc: BaseException, *, schema: type[BaseModel],
                               route: str) -> dict[str, Any]:
        """Private bounded diagnostics; never serialize messages or bodies."""
        classes: list[str] = []
        validation_errors: list[dict[str, Any]] = []
        pending: list[BaseException] = [exc]
        seen: set[int] = set()
        while pending and len(classes) < 12:
            item = pending.pop(0)
            if id(item) in seen:
                continue
            seen.add(id(item))
            classes.append(_safe_exception_name(type(item)))
            if isinstance(item, ValidationError):
                validation_errors.extend({
                    "type": _safe_pydantic_error_type(error.get("type", "unknown")),
                    "loc": [str(part)[:120] for part in error.get("loc", ())[:16]],
                } for error in item.errors(
                    include_url=False, include_context=False, include_input=False)[:16])
            cause = item.__cause__
            context = item.__context__
            if isinstance(cause, BaseException):
                pending.append(cause)
            if isinstance(context, BaseException) and context is not cause:
                pending.append(context)
            if isinstance(item, BaseExceptionGroup):
                pending.extend(child for child in item.exceptions
                               if isinstance(child, BaseException))
        names = set(classes)
        if isinstance(exc, ContentFilterError) or "ContentFilterError" in names:
            phase = "content_filter"
        elif isinstance(exc, (TimeoutError, APITimeoutError)) or names & {
                "TimeoutError", "APITimeoutError"}:
            phase = "timeout"
        elif isinstance(exc, (ModelHTTPError, RateLimitError)) or names & {
                "ModelHTTPError", "RateLimitError"}:
            phase = "http"
        elif isinstance(exc, APIConnectionError) or names & {
                "APIConnectionError", "ConnectError", "NetworkError"}:
            phase = "transport"
        elif isinstance(exc, UnexpectedModelBehavior):
            phase = ("json_or_schema_validation" if "ValidationError" in names
                     else "no_tool_or_empty")
        elif "ValidationError" in names:
            phase = "json_or_schema_validation"
        else:
            phase = "unknown"
        schema_json = schema.model_json_schema()
        known_fields: set[str] = set(schema_json.get("properties", {}))
        for definition in schema_json.get("$defs", {}).values():
            if isinstance(definition, dict):
                known_fields.update(definition.get("properties", {}))
        structural_markers = {"__root__", "union", "list", "dict"}
        for error in validation_errors:
            error["loc"] = [
                part if isinstance(part, int) else
                part if part in known_fields or part in structural_markers else
                "<unknown-field>"
                for part in error["loc"]
            ]
        schema_bytes = json.dumps(
            schema_json, sort_keys=True, separators=(",", ":")).encode()
        validation_subtypes = {
            _VALIDATION_SUBTYPE_BY_ERROR_TYPE[error["type"]]
            for error in validation_errors
            if error["type"] in _VALIDATION_SUBTYPE_BY_ERROR_TYPE
        }
        has_unrecognized_validation_error = any(
            error["type"] not in _VALIDATION_SUBTYPE_BY_ERROR_TYPE
            for error in validation_errors
        )
        if phase != "json_or_schema_validation":
            validation_subtype = "not_applicable"
        elif not validation_errors:
            validation_subtype = "other_contract_invariant"
        else:
            validation_subtype = (
                next(iter(validation_subtypes))
                if len(validation_subtypes) == 1
                and not has_unrecognized_validation_error
                else "other_contract_invariant"
            )
        return {
            "failure_top_class": _safe_exception_name(type(exc)),
            "failure_class_chain": classes,
            "failure_phase": phase,
            "failure_validation_errors": validation_errors,
            "failure_validation_subtype": validation_subtype,
            "failure_schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
            "failure_route": route,
        }

    def _models(self) -> list[tuple[ProviderName, OpenAIChatModel]]:
        configs = {
            "nvidia": (NVIDIA_NIM_BASE_URL, settings.nvidia_nim_api_key,
                       _nvidia_nim_model()),
            "mistral": ("https://api.mistral.ai/v1", settings.mistral_api_key,
                        _mistral_free_model()),
            "openrouter": ("https://openrouter.ai/api/v1", settings.openrouter_api_key,
                           _openrouter_free_model()),
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
            requested = self.model if provider == self.provider else fallback_model
            if provider == "nvidia":
                accepted_model = _nvidia_nim_model(requested)
            elif provider == "openrouter":
                accepted_model = _openrouter_free_model(requested)
            elif provider == "mistral":
                accepted_model = _mistral_free_model()
            else:
                accepted_model = settings.inception_model or INCEPTION_DEFAULT
            if (provider != "inception"
                    and not is_free_model(provider, accepted_model)):
                continue
            models.append((provider, OpenAIChatModel(
                accepted_model,
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
        self.last_failures = []
        user_prompt = json.dumps(payload, sort_keys=True, default=str)
        policy = ROUTE_POLICIES.get(envelope.route, _DEFAULT_ROUTE_POLICY)
        now = time.monotonic()
        run_deadline = RUN_MODEL_DEADLINE.get()
        deadline = min(now + float(policy["total_budget_s"]),
                       run_deadline if run_deadline is not None else float("inf"))
        budget_exhausted = False
        candidates = models[:1 + int(policy["secondary_limit"])]
        for model_index, (provider, model) in enumerate(candidates):
            max_attempts = int(policy["primary_attempts"]) if model_index == 0 else 1
            for attempt_number in range(1, max_attempts + 1):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    budget_exhausted = True
                    break
                started = time.perf_counter()
                try:
                    agent = Agent(
                        model,
                        instructions=prompt,
                        output_type=NativeOutput(schema, strict=True),
                        # PydanticAI owns one bounded schema-repair pass. Outer
                        # retries below are reserved for transient transport.
                        retries=settings.llm_max_retries,
                    )
                    run = agent.run(user_prompt)
                    result = await asyncio.wait_for(
                        run, timeout=min(float(policy["attempt_timeout_s"]), remaining))
                    self.last_provider = provider
                    self.last_model = (
                        f"mistral_free_limit:{model.model_name}"
                        if provider == "mistral" else model.model_name
                    )
                    return result.output
                except Exception as exc:
                    failure_class = self._failure_class(exc)
                    self.last_failures.append({
                        "route": envelope.route,
                        "provider": provider,
                        "model": (f"mistral_free_limit:{model.model_name}"
                                  if provider == "mistral" else model.model_name),
                        "attempt_number": attempt_number,
                        "exception_type": _safe_exception_name(type(exc)),
                        "message_class": failure_class,
                        "latency_ms": max(0, round(
                            (time.perf_counter() - started) * 1000)),
                        **self._safe_failure_taxonomy(
                            exc, schema=schema, route=envelope.route),
                    })
                    transient = failure_class in policy["transient_classes"]
                    if (attempt_number < max_attempts and transient):
                        await asyncio.sleep(random.uniform(0.04, 0.12))
                        continue
                    break
            if budget_exhausted:
                break
        budget_exhausted = (budget_exhausted or (
            time.monotonic() >= deadline and len(models) > len(candidates)))
        if budget_exhausted:
            self.last_failures.append({
                "route": envelope.route,
                "provider": envelope.route,
                "model": "deadline",
                "attempt_number": len(self.last_failures) + 1,
                "exception_type": "TimeoutError",
                "message_class": f"{envelope.route}_deadline",
                "latency_ms": 0,
            })
        summary = ", ".join(
            f"{item['provider']}:{item['exception_type']}:{item['message_class']}"
            for item in self.last_failures
        )
        raise RuntimeError(
            "all structured-output providers failed"
            + (f" [{summary}]" if summary else ""))


_PROVIDER_ROUTE_PROMPT_NAMES = {
    "intake": "intake",
    "requirement_review": "requirement_review",
    "planner": "planner",
    "synthesizer": "synthesizer",
    "repair": "repair_answer",
    "semantic_verifier": "verifier",
}
_PROVIDER_ROUTE_PROMPTS: dict[str, str] | None = None


def bind_provider_route_prompts() -> dict[str, str]:
    """Freeze the exact prompt text used by every provider route."""
    global _PROVIDER_ROUTE_PROMPTS
    if _PROVIDER_ROUTE_PROMPTS is None:
        _PROVIDER_ROUTE_PROMPTS = {
            route: load_prompt(name)
            for route, name in _PROVIDER_ROUTE_PROMPT_NAMES.items()
        }
    return dict(_PROVIDER_ROUTE_PROMPTS)


def provider_route_prompt(route: str, prompt_name: str) -> str:
    expected = _PROVIDER_ROUTE_PROMPT_NAMES.get(route)
    if expected != prompt_name:
        raise ValueError("provider route and prompt name are not registered")
    return bind_provider_route_prompts()[route]


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
        requirement_review: bool = False,
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
        self._requirement_review = requirement_review
        self.last_envelope: RequestEnvelope | None = None

    async def _generate(self, payload: Mapping[str, Any]) -> Any:
        return await self._generate_as(
            prompt_name=self.prompt_name, route=self.route,
            schema=self.schema, payload=payload,
        )

    async def _generate_as(
        self, *, prompt_name: str, route: str, schema: type[BaseModel],
        payload: Mapping[str, Any],
    ) -> Any:
        prompt = provider_route_prompt(route, prompt_name)
        envelope = RequestEnvelope.freeze(
            provider=self._provider, model=self._model_name, route=route,
            prompt=prompt, context=payload,
            tool_schemas=schema.model_json_schema(),
            planner_version=self._planner_version, budgets=self._budgets,
            skill_hashes=skill_hashes(list(payload.get("skills", []))),
        )
        self.last_envelope = envelope
        return await self._model.generate(
            schema=schema, prompt=prompt, payload=payload, envelope=envelope,
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
        payload = {
            "question": request,
            "current_date": datetime.now(UTC).date().isoformat(),
            "conversation_context": [
                turn.model_dump(mode="json") for turn in context[-8:]
            ],
            "capability_catalog": self._catalog,
            "skill_catalog": self._skills.catalog(),
        }
        task = await self._generate(payload)
        def semantic_intake_ok(candidate: TaskSpec) -> bool:
            source = request.casefold()
            referential = bool(re.search(
                r"\b(that player|that team|he|him|his|they|their)\b", source))
            context_source = " ".join(turn.content.casefold() for turn in context)
            semantic = " ".join([candidate.goal, candidate.deliverable,
                *(entity.display_name for entity in candidate.entities),
                candidate.season.value if candidate.season else ""]).casefold()
            metric_aliases = {
                "shooting": ("shoot", "shooting", "field goal", "fg%", "true shooting", "ts%"),
                "blocks": ("block", "blocks", "bpg", "rim protection"),
                "assists": ("assist", "assists", "apg", "dimes"),
                "points": ("point", "points", "ppg", "scoring"),
                "rebounds": ("rebound", "rebounds", "rpg", "boards"),
                "steals": ("steal", "steals", "spg"),
                "true shooting": ("true shooting", "ts%", "ts pct"),
                "turnovers": ("turnover", "turnovers", "tov"),
            }
            requested_metrics = [aliases for aliases in metric_aliases.values()
                if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", source)
                       for alias in aliases)]
            if any(not any(alias in semantic for alias in aliases)
                   for aliases in requested_metrics):
                return False
            source_seasons = set(re.findall(r"\b20\d{2}-\d{2}\b", source))
            if source_seasons and not source_seasons <= set(re.findall(r"\b20\d{2}-\d{2}\b", semantic)):
                return False
            # Preserve explicit operation and output shape, including N.
            number_words = {"one":"1","two":"2","three":"3","four":"4","five":"5",
                            "six":"6","seven":"7","eight":"8","nine":"9","ten":"10"}
            top = re.search(r"\btop\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b", source)
            if top:
                n = number_words.get(top.group(1), top.group(1))
                if not (re.search(rf"\btop\s+(?:{n}|" + "|".join(k for k,v in number_words.items() if v==n) + r")\b", semantic)):
                    return False
            for patterns in (("compare", "comparison", "versus", " vs "),
                             ("home and away", "home-away", "home versus away"),
                             ("last ", "recent ")):
                if any(token in source for token in patterns) and not any(token in semantic for token in patterns):
                    return False
            # Capitalized multi-token names are explicit entity anchors.
            names = re.findall(r"\b(?:[A-Z][A-Za-zÀ-ž'’-]+\s+){1,3}[A-Z][A-Za-zÀ-ž'’-]+\b", request)
            prefixes = ("Summarize ", "Compare ", "Explain ", "Assess ", "Evaluate ")
            names = [next((name[len(prefix):] for prefix in prefixes
                          if name.startswith(prefix)), name) for name in names]
            names = [name for name in names if name.casefold() not in {
                "which players", "who leads", "give the", "compare the", "national basketball association"}]
            if names and candidate.entities:
                if not any(entity.display_name.casefold() in source
                           for entity in candidate.entities) and any(
                    not any(all(part.casefold() in entity.display_name.casefold()
                                for part in name.split())
                            for entity in candidate.entities) for name in names):
                    return False
            elif any(not all(part.casefold() in semantic for part in name.split()) for name in names):
                return False
            conversational = bool(re.search(
                r"(?:sure|happy to|what(?:'s| is) your question|please (?:ask|provide)|how can i help)",
                candidate.deliverable, re.IGNORECASE))
            if conversational:
                return False
            if referential:
                # Empty context and per-type mismatches are handled by the
                # dedicated referent guard below. With context, at least one
                # candidate entity must name an antecedent; an additional
                # invented type is stripped by that guard without a model retry.
                if not context_source:
                    return True
                if not candidate.entities:
                    return True
                grounded = any(
                    entity.display_name.casefold() in context_source
                    or (len(entity.id.strip()) >= 3 and re.search(
                        rf"(?<![a-z0-9]){re.escape(entity.id.casefold())}(?![a-z0-9])",
                        context_source))
                    for entity in candidate.entities)
                # A generic failed/empty prior assistant answer establishes no
                # antecedent even if the earlier user repeated the pronoun.
                return grounded or not re.search(
                    r"unavailable|could not|failed|error", context_source)
            if requested_metrics or source_seasons or top or names:
                return True
            # Anchor-free requests need meaningful phrase similarity; pure
            # referential turns are handled by the dedicated guard below.
            stop = {"the","and","that","this","with","from","have","what","which",
                    "who","give","tell","please","nba","season","player","team","game",
                    "leaders","leader","top","rate","compare","points","how","did"}
            a={t for t in re.findall(r"[a-z0-9]+",source) if len(t)>2 and t not in stop}
            b={t for t in re.findall(r"[a-z0-9]+",semantic) if len(t)>2 and t not in stop}
            return not a or len(a & b) / len(a) >= Decimal("0.5")
        if not semantic_intake_ok(task):
            task = await self._generate({
                **payload,
                "prior_intake": task.model_dump(mode="json"),
                "resolution_feedback": {
                    "instruction": (
                        "The prior TaskSpec was schema-valid but did not preserve "
                        "the source request. Return a replacement whose goal, "
                        "entities, season, and deliverable describe the actual "
                        "request. Never return conversational filler or a question."
                    ),
                },
            })
            if not semantic_intake_ok(task):
                task = task.model_copy(update={
                    "entities": [], "required_evidence": [], "requirements": [],
                    "calculation_requirements": [],
                    "open_questions": list(dict.fromkeys([*task.open_questions,
                        "I could not preserve the requested entities, metric, season, and output shape. Could you restate the request?",
                    ])),
                })
        # Follow-up turns get one bounded typed resolution pass before the
        # runtime treats open_questions as user blockers. The first intake can
        # notice a pronoun or elliptical reference yet still fail to bind it
        # to entities in prior evidence. Re-running the same TaskSpec boundary
        # with the unresolved questions made explicit lets the intake resolve
        # from conversation evidence without weakening schema validation or
        # teaching the runtime query-specific names.
        if (context and task.open_questions
                and not any("could not preserve" in q for q in task.open_questions)):
            task = await self._generate({
                **payload,
                "prior_intake": task.model_dump(mode="json"),
                "resolution_feedback": {
                    "unresolved_questions": list(task.open_questions),
                    "instruction": (
                        "Resolve references and omitted subjects from the "
                        "bounded conversation context before leaving a user "
                        "question open. Preserve an open question only when "
                        "the context supports multiple materially different "
                        "referents or supplies none. Return a complete "
                        "replacement TaskSpec."
                    ),
                },
            })
        # Skill selection is advisory model output. Capability-like or otherwise
        # unknown names must not turn a valid evidence plan into a pre-tool
        # crash; retain only installed skills. Capability validation remains
        # strict in required_evidence and typed requirements.
        task = task.model_copy(update={
            "skills": [name for name in task.skills
                       if name in self._skills.skills],
        })
        self._skills.activate(task.skills)
        if (task.season is not None and task.season.source == "default"
                and "trade-analysis" in task.skills):
            context_seasons = [
                season for turn in context
                for season in re.findall(r"\b20\d{2}-\d{2}\b", turn.content)
            ]
            if context_seasons:
                task = task.model_copy(update={
                    "season": task.season.model_copy(update={
                        "value": context_seasons[-1], "source": "context",
                        "confidence": 1.0,
                    }),
                    "assumptions": list(dict.fromkeys([
                        *task.assumptions,
                        "Performance uses the prior context season; contracts may use the forward trade window.",
                    ])),
                })
        resolvable_questions = []
        for question in task.open_questions:
            folded = question.casefold()
            evidence_lookup = bool(set(task.required_evidence)) and any(
                token in folded for token in (
                    "team", "contract", "remaining years", "player option",
                    "roster", "role", "availability", "salary",
                ))
            analytical_assumption = any(
                token in folded for token in (
                    "risk tolerance", "front office", "preference",
                    "appetite", "willingness", "trade intent",
                ))
            optional_capability_argument = (
                "game_prediction" in task.required_evidence
                and any(token in folded for token in (
                    "specific upcoming game", "specific game date",
                    "general matchup", "which game", "game date",
                    "specific date", "date of the game",
                ))
            )
            if evidence_lookup or analytical_assumption or optional_capability_argument:
                resolvable_questions.append(question)
        if resolvable_questions:
            task = task.model_copy(update={
                "open_questions": [question for question in task.open_questions
                                   if question not in resolvable_questions],
                "assumptions": list(dict.fromkeys([
                    *task.assumptions, *resolvable_questions])),
            })
        task = task.model_copy(update={
            "required_evidence": [
                name for name in task.required_evidence
                if name not in set(task.skills)
            ],
        })
        # A referential follow-up may proceed only from an antecedent named in
        # bounded conversation text. This is reference grounding, not factual
        # verification; evidence verification remains downstream. Structured
        # validity cannot license an invented entity when context is absent.
        folded_request = request.casefold()
        referent_types = {kind for kind, patterns in {
            "player": (r"\bthat player\b", r"\bhe\b", r"\bhim\b", r"\bhis\b", r"\bdid he\b"),
            "team": (r"\bthat team\b", r"\bthey\b", r"\btheir\b", r"\bdid they\b"),
        }.items() if any(re.search(pattern, folded_request) for pattern in patterns)}
        if referent_types:
            context_text = " ".join(turn.content.casefold() for turn in context)
            grounded_types = {entity.type for entity in task.entities
                if (entity.display_name.casefold() in context_text
                    or (len(entity.id.strip()) >= 3 and re.search(
                        rf"(?<![a-z0-9]){re.escape(entity.id.casefold())}(?![a-z0-9])",
                        context_text)))}
            missing_types = sorted(referent_types - grounded_types)
            if missing_types:
                labels = " and ".join(missing_types)
                task = task.model_copy(update={
                    "entities": [entity for entity in task.entities
                                 if entity.type not in missing_types],
                    "open_questions": list(dict.fromkeys([
                        *task.open_questions, f"Which {labels} do you mean?",
                    ])),
                })
        if self._requirement_review and not task.open_questions:
            review = await self._review_requirements(request, task)
            task = task.model_copy(update={
                "subquestions": list(dict.fromkeys([
                    *task.subquestions, *review.missing_subquestions,
                ])),
                "required_evidence": task.required_evidence,
                "requirements": review.requirements,
                "calculation_requirements": review.calculation_requirements,
                "skills": list(dict.fromkeys([
                    *task.skills, *review.missing_skills,
                ])),
            })
            task = task.model_copy(update={
                "skills": [name for name in task.skills
                           if name in self._skills.skills],
            })
            self._skills.activate(task.skills)
        player_count = sum(entity.type == "player" for entity in task.entities)
        optional_evidence = set()
        if player_count < 2:
            optional_evidence.update({"player_comparison", "trade_value"})
        required_evidence = [
            name for name in task.required_evidence
            if name not in optional_evidence
        ]
        from v2.runtime.subsumption import capability_subsumes
        required_evidence = [
            name for name in required_evidence
            if not any(
                other != name and capability_subsumes(other, name)
                for other in required_evidence
            )
        ]
        if "trade-analysis" in task.skills and player_count >= 2:
            baseline = (
                "player_report", "player_evaluation", "player_comparison",
                "trade_value", "contracts", "trades",
            )
            required_evidence = list(dict.fromkeys([
                *required_evidence,
                *(name for name in baseline if name in self._catalog),
            ]))
        if ("league-ratings" in task.skills
                and "game_prediction" not in required_evidence):
            # The ratings skill is methodology, not permission to widen a
            # single-population ranking into player and playoff boards. Add
            # those boards only when the request itself names those scopes;
            # requirement review remains the authority for compound asks.
            folded_request = request.casefold()
            baseline = ["team_ratings"]
            if any(token in folded_request for token in (
                    "player", "players", "individual")):
                baseline.append("player_ratings")
            if any(token in folded_request for token in (
                    "playoff", "playoffs", "postseason")):
                baseline.append("playoff_team_ratings")
            required_evidence = list(dict.fromkeys([
                *required_evidence,
                *(name for name in baseline if name in self._catalog),
            ]))
        # Skills advise methodology; they do not widen the user's requested
        # evidence surface. Requirement review/planning may select a skill's
        # extra branch when it is material to the actual goal, but activating a
        # skill alone must not force every possible method into required data.
        if ("game_prediction" in self._catalog
                and len([entity for entity in task.entities
                         if entity.type == "team"]) == 2
                and any(token in request.casefold() for token in (
                    "who wins", "who will win", "win probability",
                    "predict", "prediction", "projected score",
                    "projected total", "pre-game", "pregame",
                ))):
            required_evidence = list(dict.fromkeys([
                *required_evidence, "game_prediction",
            ]))
        # A model-defaulted relative season is not authoritative. Pin every
        # such TaskSpec to the application's populated current-season contract,
        # not only prediction asks, before requirement arguments are rewritten.
        # Explicit user/context seasons remain untouched.
        if task.season is not None and task.season.source == "default":
            from app.tools._core import SEASON
            task = task.model_copy(update={
                "season": task.season.model_copy(update={"value": SEASON}),
            })
        task = task.model_copy(update={
            "required_evidence": required_evidence,
        })
        if task.season is not None:
            task = task.model_copy(update={
                "requirements": [
                    requirement.model_copy(update={
                        "capability_arguments": {
                            **requirement.capability_arguments,
                            "season": task.season.value,
                        },
                    })
                    if "season" in requirement.capability_arguments
                    else requirement
                    for requirement in task.requirements
                ],
            })
        unknown = sorted(set(task.required_evidence) - self._catalog.keys())
        if unknown:
            raise ValueError(f"intake selected unknown capabilities: {unknown}")
        return _canonicalize_calculation_requirements(task)

    def _capability_argument_names(self, capabilities: Sequence[str]) -> set[str] | None:
        """Return arguments accepted by every option, or None if unproven."""
        accepted: list[set[str]] = []
        for name in capabilities:
            entry = self._catalog.get(name)
            schema = entry.get("arguments") if isinstance(entry, Mapping) else None
            properties = schema.get("properties") if isinstance(schema, Mapping) else None
            if not isinstance(properties, Mapping):
                return None
            accepted.append(set(properties))
        return set.intersection(*accepted) if accepted else set()

    def _project_capability_arguments(
        self, arguments: Mapping[str, Any], capabilities: Sequence[str],
    ) -> dict[str, Any]:
        """Keep only args proven valid for every selected capability option."""
        names = self._capability_argument_names(capabilities)
        if names is None:
            return {}
        return {key: value for key, value in arguments.items() if key in names}

    def _project_mixed_requirement_arguments(
        self, review: RequirementReview,
    ) -> RequirementReview:
        """Enforce that every emitted argument is valid for every option."""
        return review.model_copy(update={"requirements": [
            item.model_copy(update={
                "capability_arguments": self._project_capability_arguments(
                    item.capability_arguments, item.capability_options),
            }) if len(item.capability_options) > 1 else item
            for item in review.requirements
        ]})

    def _strip_ranked_team_branches(
        self, review: RequirementReview,
    ) -> RequirementReview:
        """Remove only team_ratings alternatives and project shared arguments."""
        requirements = []
        for item in review.requirements:
            if "team_ratings" not in item.capability_options:
                requirements.append(item)
                continue
            remaining = [name for name in item.capability_options
                         if name != "team_ratings"]
            if remaining:
                requirements.append(item.model_copy(update={
                    "capability_options": remaining,
                    "capability_arguments": self._project_capability_arguments(
                        item.capability_arguments, remaining),
                }))
        return review.model_copy(update={"requirements": requirements})

    def _rebuild_ranked_team_branch(
        self, review: RequirementReview, task: TaskSpec,
    ) -> RequirementReview:
        """Strip lower-authority ranked branches and append at most one typed one."""
        from v2.contracts import EvidenceRequirement
        stripped = self._strip_ranked_team_branches(review)
        typed = [item for item in task.requirements
                 if "team_ratings" in item.capability_options]
        if typed:
            source = typed[0]
            ranked = source.model_copy(update={
                "capability_options": ["team_ratings"],
                "capability_arguments": self._project_capability_arguments(
                    source.capability_arguments, ["team_ratings"]),
            })
        elif "team_ratings" in task.required_evidence:
            ranked = EvidenceRequirement(
                id="required_team_ratings",
                description="Required typed intake evidence: team_ratings",
                capability_options=["team_ratings"],
                capability_arguments={})
        else:
            return stripped
        existing_ids = {item.id for item in stripped.requirements}
        if ranked.id in existing_ids:
            base = "required_team_ratings"
            candidate = base
            suffix = 2
            while candidate in existing_ids:
                candidate = f"{base}_{suffix}"
                suffix += 1
            ranked = ranked.model_copy(update={"id": candidate})
        return stripped.model_copy(update={
            "requirements": [*stripped.requirements, ranked],
        })

    def _reconcile_ranked_team_review(
        self, request: str, task: TaskSpec, review: RequirementReview,
    ) -> RequirementReview:
        """Restore trusted ranked-team constraints without widening scope."""
        if "team_ratings" not in task.required_evidence:
            return review
        review = self._project_mixed_requirement_arguments(review)
        trusted_text = " ".join([
            request, task.goal, task.deliverable, *task.subquestions,
        ])
        try:
            projected = ranked_team_constraints(
                trusted_text, season=task.season.value if task.season else None)
        except RankedTeamConstraintError:
            # Ambiguous trusted intent cannot authorize one ranked call. Strip
            # only that alternative and preserve every unrelated branch.
            return self._strip_ranked_team_branches(review)
        trusted_arguments: dict[str, Any] = {}
        for requirement in task.requirements:
            if "team_ratings" not in requirement.capability_options:
                continue
            trusted_source = self._project_capability_arguments(
                requirement.capability_arguments, ["team_ratings"])
            for key, value in trusted_source.items():
                canonical = value
                if key == "requested_metric":
                    canonical = canonical_team_rating_metric(value)
                    if canonical is None:
                        raise RankedTeamConstraintError(
                            f"unknown typed ranked-team metric alias: {value}")
                elif key == "ranking_direction":
                    canonical = canonical_ranking_direction(value)
                    if canonical is None:
                        raise RankedTeamConstraintError(
                            f"unknown typed ranked-team direction alias: {value}")
                if key in trusted_arguments and trusted_arguments[key] != canonical:
                    raise RankedTeamConstraintError(
                        f"conflicting typed intake constraint: {key}")
                trusted_arguments[key] = canonical
        if projected is None and not trusted_arguments:
            # An unranked team-ratings request has no deterministic extremum
            # contract to restore. Review arguments remain subject to the
            # closed planner/tool vocabulary.
            return review
        established = dict(trusted_arguments)
        if projected is not None:
            for key, value in projected.items():
                prior = established.get(key)
                if prior is not None and prior != value:
                    raise RankedTeamConstraintError(
                        f"typed intake conflicts with trusted question: {key}")
                established[key] = value
        ranked = [item for item in review.requirements
                  if "team_ratings" in item.capability_options]
        if (len(ranked) != 1
                or ranked[0].capability_options != ["team_ratings"]):
            review = self._rebuild_ranked_team_branch(review, task)
            ranked = [item for item in review.requirements
                      if "team_ratings" in item.capability_options]
        if not ranked:
            from v2.contracts import EvidenceRequirement
            return review.model_copy(update={"requirements": [
                *review.requirements,
                EvidenceRequirement(
                    id="required_team_ratings",
                    description="Required typed intake evidence: team_ratings",
                    capability_options=["team_ratings"],
                    capability_arguments=established),
            ]})
        reconciled = []
        for requirement in review.requirements:
            if "team_ratings" not in requirement.capability_options:
                reconciled.append(requirement)
                continue
            arguments = dict(requirement.capability_arguments)
            raw_metric = arguments.get("requested_metric")
            if raw_metric is not None:
                metric = canonical_team_rating_metric(raw_metric)
                if metric is None:
                    raise RankedTeamConstraintError(
                        f"unknown ranked-team metric alias: {raw_metric}")
                if "requested_metric" in established and metric != established["requested_metric"]:
                    raise RankedTeamConstraintError(
                        "review metric conflicts with trusted ranked-team metric")
            raw_direction = arguments.get("ranking_direction")
            if raw_direction is not None:
                direction = canonical_ranking_direction(raw_direction)
                if direction is None:
                    raise RankedTeamConstraintError(
                        f"unknown ranked-team direction alias: {raw_direction}")
                if "ranking_direction" in established and direction != established["ranking_direction"]:
                    raise RankedTeamConstraintError(
                        "review direction conflicts with trusted ranked-team extremum")
            if "season" in established and arguments.get("season") not in (None, established["season"]):
                raise RankedTeamConstraintError(
                    "review season conflicts with trusted typed season")
            for key, expected in established.items():
                if key in {"requested_metric", "ranking_direction", "season"}:
                    continue
                if key in arguments and arguments[key] != expected:
                    raise RankedTeamConstraintError(
                        f"review {key} conflicts with trusted typed scope")
            arguments.update(established)
            reconciled.append(requirement.model_copy(update={
                "capability_arguments": arguments,
            }))
        return review.model_copy(update={"requirements": reconciled})

    async def _review_requirements(
        self, request: str, task: TaskSpec,
    ) -> RequirementReview:
        payload = {
            "question": request,
            "draft_task": task.model_dump(mode="json"),
            "capability_catalog": self._catalog,
            "skill_catalog": self._skills.catalog(),
        }
        try:
            review = await self._generate_as(
                prompt_name="requirement_review", route="requirement_review",
                schema=RequirementReview, payload=payload,
            )
        except RuntimeError as exc:
            if not str(exc).startswith("all structured-output providers failed"):
                raise
            # Intake already crossed the typed boundary. On exhausted transient
            # review providers, retain exactly its evidence and calculations;
            # do not invent resolver requirements or user-visible blockers.
            from v2.contracts import EvidenceRequirement
            requirements = list(task.requirements)
            existing_capabilities = {capability for item in requirements
                                     for capability in item.capability_options}
            entities = [item.display_name for item in task.entities]
            for capability in task.required_evidence:
                if capability in existing_capabilities:
                    continue
                arguments: dict[str, Any] = {}
                if task.season is not None:
                    arguments["season"] = task.season.value
                if capability == "player_comparison" and len(entities) >= 2:
                    arguments.update({"a": entities[0], "b": entities[1]})
                elif capability.startswith("player_") and entities:
                    arguments["player"] = entities[0]
                requirement_id = f"required_{re.sub(r'[^a-z0-9]+', '_', capability.casefold()).strip('_')}"
                requirements.append(EvidenceRequirement(
                    id=requirement_id,
                    description=f"Required intake evidence: {capability}",
                    capability_options=[capability],
                    capability_arguments=arguments))
            review = RequirementReview(
                requirements=requirements,
                calculation_requirements=list(task.calculation_requirements),
                missing_subquestions=[], missing_skills=[])
        try:
            review = self._reconcile_ranked_team_review(request, task, review)
        except RankedTeamConstraintError:
            # Requirement review is lower authority than typed intake. Strip
            # only conflicting ranked alternatives, rebuild at most one trusted
            # branch, then reconcile through the same projector. If trusted
            # intake is invalid, leave only unrelated alternatives as typed gaps.
            safe_review = self._rebuild_ranked_team_branch(review, task)
            try:
                review = self._reconcile_ranked_team_review(
                    request, task, safe_review)
            except RankedTeamConstraintError:
                review = self._strip_ranked_team_branches(safe_review)
        unknown_evidence = sorted(
            {capability for requirement in review.requirements
             for capability in requirement.capability_options}
            - self._catalog.keys()
        )
        if unknown_evidence:
            raise ValueError(
                f"requirement review selected unknown capabilities: {unknown_evidence}"
            )
        # Close requirement choices over evidence-producing refinements and
        # declared broader capabilities. This lets one successful broad report
        # satisfy a narrow branch (for the same subject/season) instead of
        # forcing a redundant narrow call whose failure can falsely downgrade
        # the complete evidence.
        from v2.runtime.subsumption import capability_subsumes
        # A combined home/away game-log requirement with a null filter cannot
        # preserve split populations. Expand it into two typed requirements
        # before planning so execution never dispatches home_away=None.
        scope = " ".join([request, task.goal, task.deliverable, *task.subquestions]).casefold()
        expanded = []
        for requirement in review.requirements:
            args = requirement.capability_arguments
            if ("game_logs" in requirement.capability_options
                    and "home" in scope and "away" in scope
                    and args.get("home_away") not in {"home", "away"}):
                for split in ("home", "away"):
                    expanded.append(requirement.model_copy(update={
                        "id": f"{requirement.id}_{split}",
                        "description": f"{split.title()} split: {requirement.description}",
                        "capability_arguments": {**args, "home_away": split},
                    }))
            else:
                expanded.append(requirement)
        review = review.model_copy(update={"requirements": expanded})
        requirements = [
            requirement.model_copy(update={
                "capability_options": list(dict.fromkeys([
                    *requirement.capability_options,
                    *(["web_fetch"] if "web_search" in requirement.capability_options
                      else []),
                    *(candidate for candidate in self._catalog
                      if any(capability_subsumes(candidate, narrower)
                             for narrower in requirement.capability_options)),
                    *(["player_report"]
                      if "game_logs" in requirement.capability_options
                      and requirement.capability_arguments.get("playoffs") is False
                      and "player" in requirement.capability_arguments
                      and "player_report" in self._catalog else []),
                ])),
            })
            for requirement in review.requirements
        ]
        return review.model_copy(update={"requirements": requirements})


class ModelPlanner(ModelStage):
    prompt_name = "planner"
    route = "planner"
    schema = Plan

    def __init__(self, *args: Any, capability_catalog: Mapping[str, str], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._catalog = dict(capability_catalog)

    async def plan(self, task: TaskSpec) -> Plan:
        payload = {
            "task": task.model_dump(mode="json"),
            "capability_catalog": self._catalog,
            "skills": self._skills.activate(task.skills),
        }
        plan = await self._generate(payload)
        plan = self._normalize_plan(
            task, self._normalize_requirement_coverage(task, plan))
        feedback = self._coverage_feedback(task, plan)
        if not feedback:
            return plan
        replacement = await self._generate({
            **payload,
            "coverage_feedback": {
                **feedback, "instruction": "Return a complete replacement plan.",
            },
        })
        replacement = self._normalize_plan(
            task, self._normalize_requirement_coverage(task, replacement))
        remaining = self._coverage_feedback(task, replacement)
        if remaining:
            original_remaining = self._coverage_feedback(task, plan)
            if not original_remaining:
                return plan
            def issue_count(feedback: Mapping[str, Any]) -> int:
                return sum(
                    len(value) if isinstance(value, (list, dict)) else 1
                    for value in feedback.values()
                )
            return replacement if issue_count(remaining) <= issue_count(original_remaining) else plan
        return replacement

    def _normalize_plan(self, task: TaskSpec, plan: Plan) -> Plan:
        """Coalesce duplicate and capability-subsumed semantic calls."""
        import json
        from v2.runtime.subsumption import (
            arguments_share_subject, capability_subsumes,
        )

        requirements = {item.id: item for item in task.requirements}
        # Dependent identity calls must never run as unbound roots. Providers
        # may omit an explicit resolver even when intake has a clear entity;
        # normalize that plan shape by adding one resolver parent per distinct
        # typed subject. The executor then enforces exact canonical agreement.
        if "entity_resolution" in self._catalog:
            existing = {node.id for node in plan.nodes}
            added = []
            normalized_nodes = []
            resolver_for: dict[tuple[str, str], str] = {}
            for node in plan.nodes:
                selected_name = next((name for name in node.capability_hints
                                      if name in self._catalog), None)
                entry = self._catalog.get(selected_name, {}) if selected_name else {}
                declarations = (entry.get("dependent_entity_arguments", {})
                                if isinstance(entry, Mapping) else {})
                dependencies = list(node.depends_on)
                for argument, entity_type in declarations.items():
                    value = node.arguments.get(argument)
                    if value is None or (isinstance(value, str) and not value.strip()):
                        continue
                    has_resolver = any(
                        parent in existing and any(
                            candidate.id == parent
                            and "entity_resolution" in candidate.capability_hints
                            for candidate in plan.nodes)
                        for parent in dependencies)
                    if has_resolver:
                        continue
                    key = (str(entity_type), str(value).strip().casefold())
                    resolver_id = resolver_for.get(key)
                    if resolver_id is None:
                        base = f"resolve_{str(entity_type).replace('-', '_')}"
                        resolver_id = base
                        suffix = 2
                        while resolver_id in existing:
                            resolver_id = f"{base}_{suffix}"
                            suffix += 1
                        existing.add(resolver_id)
                        resolver_for[key] = resolver_id
                        added.append(PlanNode(
                            id=resolver_id,
                            description=f"Resolve {entity_type} identity for dependent tools",
                            capability_hints=["entity_resolution"],
                            arguments={"query": value},
                        ))
                    dependencies.append(resolver_id)
                normalized_nodes.append(node.model_copy(update={
                    "depends_on": list(dict.fromkeys(dependencies))}))
            if added:
                plan = plan.model_copy(update={"nodes": [*added, *normalized_nodes]})
        # Entity resolution accepts one query string. Requirement review can
        # preserve a pair as a list; normalize that shape before execution so
        # an auxiliary resolver cannot crash a valid direct comparison plan.
        plan = plan.model_copy(update={"nodes": [
            node.model_copy(update={
                "arguments": {**node.arguments, "query": ", ".join(
                    str(value) for value in node.arguments["query"])}
            })
            if ("entity_resolution" in node.capability_hints
                and isinstance(node.arguments.get("query"), list))
            else node
            for node in plan.nodes
        ]})
        # Canonicalize ranked team metric arguments from typed requirement
        # constraints before dispatch. Provider plans may omit direction or use
        # human synonyms; only the closed tool enum reaches execution. When no
        # mapping is supported, leave the arguments untouched so the graceful
        # A3 fallback reports the typed gap rather than guessing.
        ranked_directions = {
            "DEF_RATING": "asc", "TM_TOV_PCT": "asc",
            "OFF_RATING": "desc", "NET_RATING": "desc",
            "PACE": "desc", "TS_PCT": "desc",
        }
        canonical_nodes = []
        for node in plan.nodes:
            if "team_ratings" not in node.capability_hints:
                canonical_nodes.append(node)
                continue
            args = dict(node.arguments)
            requirement_args = [
                requirements[rid].capability_arguments
                for rid in node.covers_requirement_ids if rid in requirements
            ]
            requirement_metric = next((item.get("requested_metric")
                                       for item in requirement_args
                                       if item.get("requested_metric") is not None), None)
            raw_metric = (requirement_metric if requirement_metric is not None
                          else args.get("requested_metric"))
            key = str(raw_metric or "").strip()
            metric = canonical_team_rating_metric(key)
            if metric in TEAM_RATING_METRICS:
                args["requested_metric"] = metric
                requirement_direction = next((item.get("ranking_direction")
                                                for item in requirement_args
                                                if item.get("ranking_direction") is not None), None)
                raw_direction = (requirement_direction
                                 if requirement_direction is not None
                                 else args.get("ranking_direction"))
                direction = canonical_ranking_direction(raw_direction)
                args["ranking_direction"] = (direction if direction is not None
                                               else ranked_directions[metric])
            canonical_nodes.append(node.model_copy(update={"arguments": args}))
        plan = plan.model_copy(update={"nodes": canonical_nodes})

        # A non-playoff player-stat clause can be answered more directly by the
        # season aggregate report than by scanning game logs. When requirement
        # review admits that alternative, normalize only the typed regular-
        # season node; playoff=True logs remain separate and untouched.
        plan = plan.model_copy(update={"nodes": [
            node.model_copy(update={
                "capability_hints": ["player_report"],
                "arguments": {
                    key: value for key, value in node.arguments.items()
                    if key in {"player", "season"}
                },
            })
            if ("game_logs" in node.capability_hints
                and node.arguments.get("playoffs") is False
                and node.arguments.get("player") is not None
                and "player_report" in self._catalog
                and any(
                    requirement_id in requirements
                    and "player_report" in requirements[requirement_id].capability_options
                    for requirement_id in node.covers_requirement_ids
                ))
            else node
            for node in plan.nodes
        ]})
        selected = {
            node.id: next((name for name in node.capability_hints
                           if name in self._catalog), None)
            for node in plan.nodes
        }
        subsumed: dict[str, str] = {}
        for narrower in plan.nodes:
            narrow_name = selected[narrower.id]
            if narrow_name is None:
                continue
            for broader in plan.nodes:
                broad_name = selected[broader.id]
                if (broader.id == narrower.id or broad_name is None
                        or not capability_subsumes(broad_name, narrow_name)
                        or not arguments_share_subject(
                            broader.arguments, narrower.arguments)):
                    continue
                transferable = all(
                    requirement_id in requirements
                    and broad_name in requirements[requirement_id].capability_options
                    for requirement_id in narrower.covers_requirement_ids
                )
                if transferable:
                    subsumed[narrower.id] = broader.id
                    break
        if subsumed:
            kept_nodes = []
            for node in plan.nodes:
                if node.id in subsumed:
                    continue
                absorbed = [
                    item for item in plan.nodes
                    if subsumed.get(item.id) == node.id
                ]
                kept_nodes.append(node.model_copy(update={
                    "covers_requirement_ids": list(dict.fromkeys([
                        *node.covers_requirement_ids,
                        *(requirement_id for item in absorbed
                          for requirement_id in item.covers_requirement_ids),
                    ])),
                    "depends_on": list(dict.fromkeys(
                        subsumed.get(parent, parent) for parent in node.depends_on
                        if subsumed.get(parent, parent) != node.id
                    )),
                }))
            plan = plan.model_copy(update={"nodes": [
                node.model_copy(update={
                    "depends_on": list(dict.fromkeys(
                        subsumed.get(parent, parent) for parent in node.depends_on
                        if subsumed.get(parent, parent) != node.id
                    ))
                }) for node in kept_nodes
            ]})

        canonical: dict[tuple[str, str, tuple[str, ...]], PlanNode] = {}
        aliases: dict[str, str] = {}
        kept: list[PlanNode] = []
        for node in plan.nodes:
            selected = tuple(sorted(
                name for name in node.capability_hints if name in self._catalog))
            dependencies = tuple(aliases.get(parent, parent)
                                 for parent in node.depends_on)
            key = ("|".join(selected), json.dumps(
                node.arguments, sort_keys=True, separators=(",", ":"),
                default=str), dependencies)
            previous = canonical.get(key)
            if previous is None:
                normalized = node.model_copy(update={"depends_on": list(dependencies)})
                canonical[key] = normalized
                kept.append(normalized)
                continue
            aliases[node.id] = previous.id
            merged = list(dict.fromkeys([
                *previous.covers_requirement_ids, *node.covers_requirement_ids]))
            replacement = previous.model_copy(
                update={"covers_requirement_ids": merged})
            canonical[key] = replacement
            kept[kept.index(previous)] = replacement

        if aliases:
            kept = [node.model_copy(update={
                "depends_on": list(dict.fromkeys(
                    aliases.get(parent, parent) for parent in node.depends_on))
            }) for node in kept]
        return plan.model_copy(update={"nodes": kept})

    @staticmethod
    def _arguments_cover(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
        """Whether actual arguments satisfy a typed requirement constraint.

        This is deliberately capability-agnostic: requirement review names the
        provider-facing argument and exact value. Lists mean any acceptable
        value; nested objects use recursive subset matching.
        """
        for key, wanted in expected.items():
            if key not in actual:
                return False
            got = actual[key]
            if isinstance(wanted, Mapping):
                if not isinstance(got, Mapping) or not ModelPlanner._arguments_cover(wanted, got):
                    return False
            elif isinstance(wanted, list):
                if got not in wanted:
                    return False
            elif isinstance(wanted, str) and isinstance(got, str):
                if wanted.strip().casefold() != got.strip().casefold():
                    return False
            elif wanted != got:
                return False
        return True

    def _normalize_requirement_coverage(
        self, task: TaskSpec, plan: Plan,
    ) -> Plan:
        requirements = {item.id: item for item in task.requirements}
        nodes = []
        for node in plan.nodes:
            selected = set(node.capability_hints) & self._catalog.keys()
            valid = [
                requirement_id for requirement_id in node.covers_requirement_ids
                if requirement_id in requirements
                and selected & set(requirements[requirement_id].capability_options)
                and self._arguments_cover(
                    requirements[requirement_id].capability_arguments, node.arguments)
            ]
            nodes.append(node.model_copy(update={"covers_requirement_ids": valid}))
        return plan.model_copy(update={"nodes": nodes})

    def _missing_required_arguments(
        self, node: PlanNode, plan: Plan | None = None,
    ) -> list[str]:
        selected = [name for name in node.capability_hints if name in self._catalog]
        if len(selected) != 1:
            return []
        catalog_entry = self._catalog.get(selected[0])
        if not isinstance(catalog_entry, Mapping):
            return []
        schema = catalog_entry.get("arguments")
        if not isinstance(schema, Mapping):
            return []
        required = schema.get("required", [])
        if not isinstance(required, list):
            return []
        declarations = catalog_entry.get("dependent_entity_arguments", {})
        return sorted(
            key for key in required
            if isinstance(key, str) and key not in node.arguments
            and not (plan is not None and node.depends_on
                     and isinstance(declarations, Mapping)
                     and key in declarations)
        )

    def _coverage_feedback(self, task: TaskSpec, plan: Plan) -> dict[str, Any]:
        invalid_arguments = {
            node.id: self._missing_required_arguments(node, plan)
            for node in plan.nodes
            if self._missing_required_arguments(node, plan)
        }
        valid_nodes = [
            node for node in plan.nodes if node.id not in invalid_arguments
        ]
        selected = {
            name for node in valid_nodes for name in node.capability_hints
            if name in self._catalog
        }
        missing_evidence = sorted(set(task.required_evidence) - selected)
        requirements = {item.id: item for item in task.requirements}
        covered: set[str] = set()
        mismatched: list[str] = []
        for node in valid_nodes:
            node_capabilities = set(node.capability_hints) & self._catalog.keys()
            for requirement_id in node.covers_requirement_ids:
                requirement = requirements.get(requirement_id)
                if requirement is None:
                    mismatched.append(f"unknown:{requirement_id}")
                elif node_capabilities & set(requirement.capability_options):
                    covered.add(requirement_id)
                else:
                    mismatched.append(requirement_id)
        missing_requirements = sorted(requirements.keys() - covered)
        feedback: dict[str, Any] = {}
        if missing_evidence:
            feedback["missing_required_evidence"] = missing_evidence
        if missing_requirements:
            feedback["missing_requirement_ids"] = missing_requirements
        if mismatched:
            feedback["mismatched_requirement_ids"] = sorted(set(mismatched))
        if invalid_arguments:
            feedback["missing_required_arguments"] = invalid_arguments
        return feedback


_CANONICAL_CALCULATIONS = {
    "home_mean": ("home_mean", "Canonical home points-per-game mean"),
    "away_mean": ("away_mean", "Canonical away points-per-game mean"),
    "home_away_delta": ("home_away_delta", "Canonical home-minus-away points-per-game difference"),
    "ppg_margin": ("ppg_margin", "Canonical points-per-game margin"),
    "ts_margin": ("ts_margin", "Canonical true-shooting percentage-point margin"),
}


def _canonicalize_calculation_requirements(task: TaskSpec) -> TaskSpec:
    """Normalize arithmetic intent once, while preserving provider-owned IDs."""
    from v2.contracts import CalculationRequirement
    scope = " ".join([task.goal, task.deliverable, *task.subquestions,
                      *(item.description for item in task.calculation_requirements)]).casefold()
    evidence_caps = {cap for requirement in task.requirements
                     for cap in requirement.capability_options}
    split_shape = ("home" in scope and "away" in scope
                   and ("game_logs" in evidence_caps or "scor" in scope or "average" in scope))
    pair_shape = ("player_comparison" in evidence_caps
                  or sum(entity.type == "player" for entity in task.entities) >= 2
                  or ("compare" in scope and any(token in scope for token in ("points", "scor", "true shooting"))))
    requested = []
    if split_shape:
        requested.extend(["home_mean", "away_mean"])
        if any(token in scope for token in ("difference", "minus", "margin", "gap")):
            requested.append("home_away_delta")
    elif pair_shape:
        if any(token in scope for token in ("who scores more", "by how much", "point", "ppg", "scor")):
            requested.append("ppg_margin")
        explicit_ts_delta = any(
            ("true shooting" in item.description.casefold() or "ts%" in item.description.casefold())
            and any(token in item.description.casefold() for token in ("difference", "margin", "gap"))
            for item in task.calculation_requirements)
        if "true shooting" in scope and (explicit_ts_delta or "differences" in scope):
            requested.append("ts_margin")
    if not requested:
        return task
    kinds: set[str] = set()
    unused = list(task.calculation_requirements)
    def classify(description: str) -> str | None:
        text = description.casefold()
        if ("sample size" in text or "number of games" in text or "game count" in text):
            return "observed_sample_size"
        if "home" in text and "away" not in text and any(x in text for x in ("average", "mean", "ppg")):
            return "home_mean"
        if "away" in text and "home" not in text and any(x in text for x in ("average", "mean", "ppg")):
            return "away_mean"
        if "home" in text and "away" in text and any(x in text for x in ("difference", "minus", "margin", "gap", "subtract")):
            return "home_away_delta"
        if "true shooting" in text or "ts%" in text:
            return "ts_margin"
        if any(x in text for x in ("point", "ppg", "scor")):
            return "ppg_margin"
        return None
    for requirement in list(unused):
        kind = classify(requirement.description)
        if kind == "observed_sample_size":
            unused.remove(requirement)
        elif kind in requested:
            kinds.add(kind)
            unused.remove(requirement)
    # Canonical identities own the DraftReport boundary. Provider IDs are
    # provenance only and cannot create duplicate semantic ownership.
    kinds.update(requested)
    normalized = [CalculationRequirement(
        id=_CANONICAL_CALCULATIONS[kind][0],
        description=_CANONICAL_CALCULATIONS[kind][1])
        for kind in requested if kind in kinds]
    # Preserve only genuinely unrelated arithmetic work. Same-kind duplicates
    # and observed sample-size artifacts were consumed above.
    normalized.extend(unused)
    return task.model_copy(update={"calculation_requirements": normalized})


class InvalidDraftCalculation(ValueError):
    def __init__(self, message: str, requirement_ids: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.requirement_ids = tuple(requirement_ids)


def _validate_draft(
    draft: DraftReport, evidence: Sequence[EvidenceEnvelope],
    task: TaskSpec | None = None,
) -> DraftReport:
    known = {item.evidence_id for item in evidence}
    unknown = sorted({evidence_id for claim in draft.claims
                      for evidence_id in claim.evidence_ids
                      if evidence_id not in known})
    if unknown:
        raise ValueError(f"draft cites unknown evidence ids: {unknown}")
    from v2.domain.evidence import EvidenceIndex
    from v2.domain.calculations import Calculation
    index = EvidenceIndex(evidence)
    for declared in draft.calculations:
        calculation = Calculation.model_validate({key: value for key, value in declared.model_dump().items()
                                                  if key != "requirement_id"})
        try:
            from v2.domain.calculations import recompute
            recompute(calculation, index)
        except (KeyError, ValueError) as exc:
            requirement_ids = ([declared.requirement_id]
                               if declared.requirement_id is not None else [])
            raise InvalidDraftCalculation(
                f"draft calculation path is outside admitted evidence: {exc}",
                requirement_ids) from exc
    if task is not None:
        required = {item.id for item in task.calculation_requirements}
        declared = {item.requirement_id for item in draft.calculations
                    if item.requirement_id is not None}
        blocked = set(draft.blocked_calculation_requirement_ids)
        # blocked_calculation_requirement_ids is a model-authored convenience
        # field, not authority to reclassify ordinary evidence requirements as
        # calculations. Ignore non-calculation IDs here; ordinary requirement
        # coverage is owned by the typed plan/execution boundary. A declared
        # calculation linked to an unknown ID remains malformed and fails.
        unknown_declared = declared - required
        if unknown_declared:
            # A model may attach an arithmetic result to the evidence
            # requirement whose rows supplied its inputs. Preserve the
            # calculation and lineage, but do not let that class mismatch
            # terminate an otherwise publishable supported-partial run.
            # Only calculation requirements own requirement_id.
            draft = draft.model_copy(update={
                "calculations": [
                    calculation.model_copy(update={"requirement_id": None})
                    if calculation.requirement_id in unknown_declared
                    else calculation
                    for calculation in draft.calculations
                ],
            })
            declared -= unknown_declared
        blocked &= required
        if blocked != set(draft.blocked_calculation_requirement_ids):
            draft = draft.model_copy(update={
                "blocked_calculation_requirement_ids": sorted(blocked),
            })
        missing = required - declared - blocked
        if missing:
            raise ValueError(f"draft omits required calculations without a blocking gap: {sorted(missing)}")
    return draft


def _deterministic_game_log_draft(
    task: TaskSpec, evidence: Sequence[EvidenceEnvelope],
) -> DraftReport | None:
    """Build typed split aggregates and signed differences from admitted logs."""
    from decimal import Decimal
    logs = [item for item in evidence
            if item.capability == "game_logs" and isinstance(item.rows, Mapping)]
    home = next((item for item in logs if item.rows.get("filters") == "home games"), None)
    away = next((item for item in logs if item.rows.get("filters") == "away games"), None)
    if not (home and away and task.calculation_requirements):
        return None
    try:
        home_avg = Decimal(str(home.rows["average_pts"]))
        away_avg = Decimal(str(away.rows["average_pts"]))
        home_n = int(home.rows["total"]); away_n = int(away.rows["total"])
    except (KeyError, TypeError, ValueError):
        return None
    home_ids, away_ids, delta_ids, unknown_ids = [], [], [], []
    descriptions = {value[1]: kind for kind, value in _CANONICAL_CALCULATIONS.items()}
    for requirement in task.calculation_requirements:
        kind = descriptions.get(requirement.description)
        if kind == "home_mean": home_ids.append(requirement.id)
        elif kind == "away_mean": away_ids.append(requirement.id)
        elif kind == "home_away_delta": delta_ids.append(requirement.id)
        else: unknown_ids.append(requirement.id)
    if not (home_ids or away_ids or delta_ids):
        return None
    delta = home_avg - away_avg
    player = home.rows.get("player") or away.rows.get("player") or "The player"
    season = home.season or away.season or "the selected season"
    def one(value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.1'))}"
    calculations, claims = [], []
    def add_mean(label, item, value, count, requirement_ids):
        ids = requirement_ids or [None]
        for index, requirement_id in enumerate(ids):
            calculation_id = f"{label}_mean_pts" + (f"_{index + 1}" if index else "")
            calculations.append({"calculation_id":calculation_id,
                "requirement_id":requirement_id, "operation":"mean",
                "inputs":[{"evidence_id":item.evidence_id,"path":"rows.matches[].pts"}],
                "result":value, "unit":"points_per_game"})
            if index == 0:
                claims.append(Claim(
                    text=f"{player} averaged {one(value)} points per game in {count} {label} games in {season}.",
                    kind="derived", evidence_ids=[item.evidence_id], calculation_id=calculation_id))
    add_mean("home", home, home_avg, home_n, home_ids)
    add_mean("away", away, away_avg, away_n, away_ids)
    for index, requirement_id in enumerate(delta_ids):
        calculation_id = "home_minus_away" + (f"_{index + 1}" if index else "")
        calculations.append({"calculation_id":calculation_id,
            "requirement_id":requirement_id, "operation":"subtract",
            "inputs":[{"evidence_id":home.evidence_id,"path":"rows.average_pts"},
                      {"evidence_id":away.evidence_id,"path":"rows.average_pts"}],
            "result":delta, "unit":"points_per_game"})
        if index == 0:
            claims.append(Claim(
                text=f"The home-minus-away scoring difference was {one(delta)} points per game.",
                kind="derived", evidence_ids=[home.evidence_id, away.evidence_id],
                calculation_id=calculation_id))
    return DraftReport(sections=["Home and away scoring"], claims=claims,
        calculations=calculations,
        blocked_calculation_requirement_ids=unknown_ids,
        gaps=(["Some requested calculations could not be mapped to the admitted split evidence."]
              if unknown_ids else []))


def _deterministic_player_comparison_draft(
    task: TaskSpec, evidence: Sequence[EvidenceEnvelope],
) -> DraftReport | None:
    """Project comparison facts and typed differences from canonical evidence."""
    from decimal import Decimal
    item = next((ev for ev in evidence
                 if ev.capability == "player_comparison"
                 and isinstance(ev.rows, Mapping)), None)
    if item is None or not task.calculation_requirements:
        return None
    descriptions = {value[1]: kind for kind, value in _CANONICAL_CALCULATIONS.items()}
    ppg_ids, ts_ids, leader_ids, unknown_ids = [], [], [], []
    for requirement in task.calculation_requirements:
        kind = descriptions.get(requirement.description)
        if kind == "ppg_margin": ppg_ids.append(requirement.id)
        elif kind == "ts_margin": ts_ids.append(requirement.id)
        else: unknown_ids.append(requirement.id)
    if not (ppg_ids or ts_ids or leader_ids):
        return None
    try:
        a = item.rows["a"]; b = item.rows["b"]
        a_ppg, b_ppg = Decimal(str(a["ppg"])), Decimal(str(b["ppg"]))
    except (KeyError, TypeError, ValueError):
        return None
    shooting = [ev for ev in evidence if ev.capability == "shooting_efficiency"
                and isinstance(ev.rows, Mapping) and ev.rows.get("PLAYER_NAME")
                and ev.rows.get("TS_PCT") is not None]
    def display_name(raw):
        raw_text = str(raw)
        key = raw_text.casefold().replace("_", " ").replace("č", "c").replace("ć", "c")
        candidates = [entity.display_name for entity in task.entities]
        candidates += [str(ev.rows["PLAYER_NAME"]) for ev in shooting]
        return next((name for name in candidates
                     if name.casefold().replace("č", "c").replace("ć", "c") == key), raw_text)
    a_name, b_name = display_name(a.get("name")), display_name(b.get("name"))
    high_name, high_ppg, high_path = ((a_name, a_ppg, "rows.a.ppg")
                                      if a_ppg >= b_ppg else (b_name, b_ppg, "rows.b.ppg"))
    low_name, low_ppg, low_path = ((b_name, b_ppg, "rows.b.ppg")
                                   if a_ppg >= b_ppg else (a_name, a_ppg, "rows.a.ppg"))
    calculations = []
    claims = [
        Claim(text=f"{a_name} averaged {a_ppg} points per game in {item.season or 'the selected season'}.",
              kind="observed", evidence_ids=[item.evidence_id]),
        Claim(text=f"{b_name} averaged {b_ppg} points per game in {item.season or 'the selected season'}.",
              kind="observed", evidence_ids=[item.evidence_id]),
    ]
    for index, rid in enumerate(leader_ids):
        cid = "ppg_leader_rank" + (f"_{index + 1}" if index else "")
        calculations.append({"calculation_id":cid, "requirement_id":rid,
            "operation":"rank_desc", "inputs":[
                {"evidence_id":item.evidence_id,"path":high_path},
                {"evidence_id":item.evidence_id,"path":low_path}],
            "result":1, "unit":"rank", "subject_input":0})
        if index == 0:
            claims.append(Claim(text=f"{high_name} scored more points per game than {low_name}.",
                kind="derived", evidence_ids=[item.evidence_id], calculation_id=cid))
    if ppg_ids:
        claims.append(Claim(text=f"{high_name} scored more points per game than {low_name}.",
                            kind="observed", evidence_ids=[item.evidence_id]))
    for index, rid in enumerate(ppg_ids):
        cid = "ppg_difference" + (f"_{index + 1}" if index else "")
        margin = high_ppg - low_ppg
        calculations.append({"calculation_id":cid, "requirement_id":rid,
            "operation":"subtract", "inputs":[
                {"evidence_id":item.evidence_id,"path":high_path},
                {"evidence_id":item.evidence_id,"path":low_path}],
            "result":margin,"unit":"points per game"})
        if index == 0:
            claims.append(Claim(text=f"{high_name} scored {margin} points per game more than {low_name}.",
                kind="derived", evidence_ids=[item.evidence_id], calculation_id=cid))
    by_name = {str(ev.rows["PLAYER_NAME"]): ev for ev in shooting}
    matched = [(name, next((ev for candidate, ev in by_name.items()
                            if display_name(candidate) == name), None))
               for name in (a_name, b_name)]
    def percent_value(raw: Any) -> Decimal:
        value = Decimal(str(raw))
        return value * 100 if abs(value) <= 1 else value
    for name, ev in matched:
        if ev is not None:
            value = percent_value(ev.rows["TS_PCT"]).normalize()
            claims.append(Claim(text=f"{name} had a {value}% true shooting percentage.",
                                kind="observed", evidence_ids=[ev.evidence_id]))
    if len(matched) == 2 and all(ev is not None for _, ev in matched):
        (name_a, ev_a), (name_b, ev_b) = matched
        ts_a, ts_b = percent_value(ev_a.rows["TS_PCT"]), percent_value(ev_b.rows["TS_PCT"])
        hi_name, hi_ev, hi_ts, lo_name, lo_ev, lo_ts = ((name_a, ev_a, ts_a, name_b, ev_b, ts_b)
            if ts_a >= ts_b else (name_b, ev_b, ts_b, name_a, ev_a, ts_a))
        for index, rid in enumerate(ts_ids):
            cid = "ts_difference" + (f"_{index + 1}" if index else "")
            calculations.append({"calculation_id":cid, "requirement_id":rid,
                "operation":"subtract", "inputs":[
                    {"evidence_id":hi_ev.evidence_id,"path":"rows.TS_PCT"},
                    {"evidence_id":lo_ev.evidence_id,"path":"rows.TS_PCT"}],
                "result":hi_ts-lo_ts,"unit":"percentage points"})
            if index == 0:
                claims.append(Claim(text=f"{hi_name}'s true shooting was {hi_ts-lo_ts} percentage points higher than {lo_name}'s.",
                    kind="derived", evidence_ids=[hi_ev.evidence_id, lo_ev.evidence_id], calculation_id=cid))
    elif ts_ids:
        unknown_ids.extend(ts_ids)
    return DraftReport(sections=["Player comparison"], claims=claims,
        calculations=calculations, blocked_calculation_requirement_ids=unknown_ids,
        gaps=(["Some requested calculations could not be mapped to admitted comparison evidence."]
              if unknown_ids else []))


def _deterministic_rank_draft(
    task: TaskSpec, evidence: Sequence[EvidenceEnvelope],
) -> DraftReport | None:
    """Project one typed team-rating extremum from the requested metric only."""
    from v2.domain.evidence import decimal_value
    labels = {"DEF_RATING": "defensive rating",
              "TS_PCT": "true shooting percentage",
              "TM_TOV_PCT": "turnover percentage"}
    metric_terms = {
        "DEF_RATING": ("defensive rating", "def rating", "def_rating"),
        "TS_PCT": ("true shooting percentage", "true shooting", "ts%", "ts_pct"),
        "TM_TOV_PCT": ("turnover percentage", "turnover rate", "tm_tov_pct"),
    }
    directions = {"asc": "lowest", "desc": "highest"}
    for item in evidence:
        if item.capability != "team_ratings" or not isinstance(item.rows, list) or not item.rows:
            continue
        metric = item.metric_definitions.get("__requested_metric__")
        if metric not in labels:
            continue
        owner = next((requirement for requirement in task.requirements
                      if "team_ratings" in requirement.capability_options
                      and requirement.capability_arguments.get("requested_metric") == metric), None)
        if owner is None:
            continue
        direction = owner.capability_arguments.get("ranking_direction")
        direction = direction if direction in directions else (
            "asc" if metric in {"DEF_RATING", "TM_TOV_PCT"} else "desc")
        numeric = []
        for row_index, candidate in enumerate(item.rows):
            value = decimal_value(candidate.get(metric))
            team = candidate.get("TEAM_NAME") or candidate.get("TEAM")
            if value is not None and team:
                numeric.append((row_index, value, str(team)))
        if not numeric:
            continue
        extreme = (min(value for _, value, _ in numeric) if direction == "asc"
                   else max(value for _, value, _ in numeric))
        winners = [(index, value, team) for index, value, team in numeric if value == extreme]

        # Calculation requirements are not typed to a subject. If the task
        # carries any team entity, fail closed: prose cannot prove that an
        # extremum request is global rather than scoped to that team.
        has_team_subject = any(entity.type == "team" for entity in task.entities)
        eligible, blocked = [], []
        for requirement in task.calculation_requirements:
            text = " ".join(requirement.description.casefold().split())
            names_different_metric = any(
                any(term in text for term in terms)
                for other, terms in metric_terms.items() if other != metric)
            names_metric = any(term in text for term in metric_terms[metric])
            asks_low = any(token in text for token in ("lowest", "minimum", " min "))
            asks_high = any(token in text for token in ("highest", "maximum", " max "))
            asks_leader = ("leader" in text or "rank first" in text or "rank #1" in text)
            conflicting = asks_low and asks_high
            agrees = ((direction == "asc" and asks_low and not asks_high)
                      or (direction == "desc" and asks_high and not asks_low)
                      or (asks_leader and not asks_low and not asks_high))
            if (not has_team_subject and names_metric and agrees
                    and not conflicting and not names_different_metric):
                eligible.append(requirement)
            else:
                blocked.append(requirement.id)

        # A tied extremum does not identify one team. Refuse to fabricate a
        # unique winner or attach a one-subject calculation to a plural fact.
        if len(winners) != 1:
            return DraftReport(
                sections=["Team rating leader"], claims=[], calculations=[],
                blocked_calculation_requirement_ids=[item.id for item in task.calculation_requirements],
                gaps=[f"The requested {labels[metric]} extremum is tied across {len(winners)} teams."])

        winner_index, value, team = winners[0]
        inputs = [{"evidence_id": item.evidence_id, "path": f"rows[{row_index}].{metric}"}
                  for row_index, _, _ in numeric]
        subject_input = next(index for index, (row_index, _, _) in enumerate(numeric)
                             if row_index == winner_index)
        calculations = [{
            "calculation_id": f"requested_metric_rank_{index + 1}",
            "requirement_id": requirement.id,
            "operation": "rank_asc" if direction == "asc" else "rank_desc",
            "inputs": inputs, "subject_input": subject_input, "result": 1, "unit": "rank",
        } for index, requirement in enumerate(eligible)]
        calculation_id = calculations[0]["calculation_id"] if calculations else None
        return DraftReport(
            sections=["Team rating leader"],
            claims=[Claim(
                text=(f"{team} had the {directions[direction]} {labels[metric]} "
                      f"in {item.season or 'the selected season'}: {value}."),
                kind="derived" if calculation_id else "observed",
                evidence_ids=[item.evidence_id], calculation_id=calculation_id)],
            calculations=calculations,
            blocked_calculation_requirement_ids=blocked,
            gaps=(["Some requested calculations do not match the admitted metric and direction."]
                  if blocked else []))
    return None


class ModelSynthesizer(ModelStage):
    prompt_name = "synthesizer"
    route = "synthesizer"
    schema = DraftReport

    async def synthesize(
        self, task: TaskSpec, evidence: Sequence[EvidenceEnvelope]
    ) -> DraftReport:
        task = _canonicalize_calculation_requirements(task)
        canonical = (_deterministic_rank_draft(task, evidence)
                     or _deterministic_game_log_draft(task, evidence)
                     or _deterministic_player_comparison_draft(task, evidence))
        if canonical is not None:
            return _validate_draft(canonical, evidence, task)
        payload = {
            "task": task.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "skills": self._skills.activate(task.skills),
        }
        try:
            draft = await self._generate(payload)
        except RuntimeError as exc:
            if not str(exc).startswith("all structured-output providers failed"):
                raise
            # Execution is already complete at this stage. Give a transient
            # structured-output outage one fresh bounded attempt rather than
            # discarding all successfully collected evidence. The accepted
            # result still crosses the same DraftReport boundary and the
            # independent publication verifiers remain authoritative.
            try:
                draft = await self._generate(payload)
            except RuntimeError as retry_exc:
                if not str(retry_exc).startswith("all structured-output providers failed"):
                    raise
                # Tools already succeeded. Preserve evidence through a typed
                # partial rather than throwing it away; deterministic builders
                # above still publish any canonical projections they own.
                draft = DraftReport(
                    sections=["Available evidence"], claims=[], calculations=[],
                    blocked_calculation_requirement_ids=[
                        item.id for item in task.calculation_requirements],
                    gaps=["Answer synthesis provider was unavailable; admitted evidence is preserved."])
        try:
            return _validate_draft(draft, evidence, task)
        except InvalidDraftCalculation as exc:
            invalid_ids = set(exc.requirement_ids)
            invalid_calculations = {
                item.calculation_id for item in draft.calculations
                if item.requirement_id in invalid_ids or not invalid_ids
            }
            safe_claims = [claim for claim in draft.claims
                           if claim.calculation_id not in invalid_calculations]
            safe_calculations = [item for item in draft.calculations
                                 if item.calculation_id not in invalid_calculations]
            blocked = sorted(set(draft.blocked_calculation_requirement_ids)
                             | invalid_ids)
            partial = draft.model_copy(update={
                "claims": safe_claims,
                "calculations": safe_calculations,
                "blocked_calculation_requirement_ids": blocked,
                "gaps": list(dict.fromkeys([
                    *draft.gaps, str(exc),
                ])),
            })
            return _validate_draft(partial, evidence, task)


class ModelRepairer(ModelStage):
    prompt_name = "repair_answer"
    route = "repair"
    schema = DraftReport

    @staticmethod
    def _key(claim: Claim) -> tuple[Any, ...]:
        return (claim.text, claim.kind, tuple(claim.evidence_ids),
                claim.calculation_id, claim.confidence)

    @classmethod
    def _missing_replacements(
        cls, original: DraftReport, repaired: DraftReport,
        verification: VerificationReport,
    ) -> list[dict[str, Any]]:
        supported_keys = {
            cls._key(original.claims[result.claim_index])
            for result in verification.claim_results
            if result.supported and result.claim_index < len(original.claims)
        }
        rejected_keys = {
            cls._key(original.claims[result.claim_index])
            for result in verification.claim_results
            if not result.supported and result.claim_index < len(original.claims)
        }
        candidates = [claim for claim in repaired.claims
                      if cls._key(claim) not in supported_keys
                      and cls._key(claim) not in rejected_keys]
        assigned: set[int] = set()
        requirements: list[dict[str, Any]] = []
        for result in verification.claim_results:
            if result.supported or result.claim_index >= len(original.claims):
                continue
            claim = original.claims[result.claim_index]
            match = next((index for index, item in enumerate(candidates)
                          if index not in assigned
                          and set(item.evidence_ids) & set(claim.evidence_ids)
                          and (claim.calculation_id is None
                               or item.calculation_id == claim.calculation_id)), None)
            if match is not None:
                assigned.add(match)
                continue
            requirements.append({
                "claim_index": result.claim_index,
                "kind": claim.kind.value,
                "evidence_ids": claim.evidence_ids,
                "calculation_id": claim.calculation_id,
            })
        return requirements

    def _merge_supported(
        self, original: DraftReport, repaired: DraftReport,
        verification: VerificationReport,
    ) -> DraftReport:
        supported = [
            original.claims[result.claim_index]
            for result in verification.claim_results
            if result.supported and result.claim_index < len(original.claims)
        ]
        supported_keys = {self._key(claim) for claim in supported}
        rejected_keys = {
            self._key(original.claims[result.claim_index])
            for result in verification.claim_results
            if not result.supported and result.claim_index < len(original.claims)
        }
        claims = [
            *supported,
            *[claim for claim in repaired.claims
              if self._key(claim) not in supported_keys
              and self._key(claim) not in rejected_keys],
        ]
        # Repair can rewrite claims, but it cannot author new publication gaps.
        # Gaps come from execution or independent verification; carrying the
        # repair model's diagnosis forward can leave a stale limitation after
        # the rejected branch has been replaced and reverified.
        return DraftReport.model_validate(repaired.model_copy(
            update={"claims": claims, "calculations": list(original.calculations),
                    "blocked_calculation_requirement_ids": list(original.blocked_calculation_requirement_ids), "gaps": list(original.gaps)}).model_dump())

    async def repair(
        self,
        task: TaskSpec,
        draft: DraftReport,
        evidence: Mapping[str, EvidenceEnvelope],
        verification: VerificationReport,
    ) -> DraftReport:
        payload = {
            "task": task.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
            "skills": self._skills.activate(task.skills),
            "admitted_evidence": [
                item.model_dump(mode="json") for item in evidence.values()
            ],
        }
        repaired = _validate_draft(
            await self._generate(payload), list(evidence.values()))
        repaired = self._merge_supported(draft, repaired, verification)
        missing = self._missing_replacements(draft, repaired, verification)
        if missing:
            repaired = _validate_draft(await self._generate({
                **payload,
                "previous_repair": repaired.model_dump(mode="json"),
                "required_replacements": missing,
            }), list(evidence.values()))
            repaired = self._merge_supported(draft, repaired, verification)
            missing = self._missing_replacements(draft, repaired, verification)
        if missing:
            repaired = repaired.model_copy(update={
                "gaps": list(dict.fromkeys([
                    *repaired.gaps,
                    "A rejected evidence branch could not be corrected from the available data.",
                ])),
            })
        return DraftReport.model_validate(repaired.model_dump())


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
        payload = {
            "task": task.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "evidence": compact,
            "skills": self._skills.activate(task.skills),
        }
        report = await self._generate(payload)
        expected = set(range(len(draft.claims)))
        observed = [item.claim_index for item in report.claim_results]
        if (len(observed) != len(set(observed))
                or any(index not in expected for index in observed)):
            raise ValueError(
                "semantic verifier returned duplicate or unknown claim indices")
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
            result = schema.model_validate(result.model_dump())
        except BaseException as exc:
            self._ledger.append(
                LedgerKind.ASSISTANT_ATTEMPT,
                turn_id=self._turn_id,
                call_id=call_id,
                data={"status": "failed", "error": exception_text(exc),
                      "provider_attempts": list(getattr(
                          self._model, "last_failures", []))},
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
                "provider_attempts": list(getattr(
                    self._model, "last_failures", [])),
            },
        )
        return result
