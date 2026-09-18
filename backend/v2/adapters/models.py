from __future__ import annotations

import json
import re
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
        self.last_failures: list[dict[str, str]] = []

    @staticmethod
    def _failure_class(exc: BaseException) -> str:
        """Bounded provider diagnostics without payloads or raw responses."""
        name = type(exc).__name__.casefold()
        detail = str(exc).casefold()
        if "timeout" in name or "timed out" in detail:
            return "timeout"
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
        self.last_failures = []
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
                self.last_failures.append({
                    "provider": provider,
                    "exception_type": type(exc).__name__[:120],
                    "message_class": self._failure_class(exc),
                })
                continue
        summary = ", ".join(
            f"{item['provider']}:{item['exception_type']}:{item['message_class']}"
            for item in self.last_failures
        )
        raise RuntimeError(
            "all structured-output providers failed"
            + (f" [{summary}]" if summary else ""))


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
        prompt = load_prompt(prompt_name)
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
        # Follow-up turns get one bounded typed resolution pass before the
        # runtime treats open_questions as user blockers. The first intake can
        # notice a pronoun or elliptical reference yet still fail to bind it
        # to entities in prior evidence. Re-running the same TaskSpec boundary
        # with the unresolved questions made explicit lets the intake resolve
        # from conversation evidence without weakening schema validation or
        # teaching the runtime query-specific names.
        if context and task.open_questions:
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
        if self._requirement_review:
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
        return task

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
            # A transient provider failure after a successful intake used to
            # terminate the run before planning. Match the bounded recovery
            # already owned by planner, synthesizer, and semantic verification:
            # retry the same typed boundary once, never parse or repair text.
            review = await self._generate_as(
                prompt_name="requirement_review", route="requirement_review",
                schema=RequirementReview, payload=payload,
            )
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
        try:
            plan = await self._generate(payload)
        except RuntimeError as exc:
            if not str(exc).startswith("all structured-output providers failed"):
                raise
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
        metric_aliases = {
            "def_rating": "DEF_RATING", "defensive_rating": "DEF_RATING",
            "defense": "DEF_RATING", "defensive rating": "DEF_RATING",
            "ts_pct": "TS_PCT", "true_shooting": "TS_PCT",
            "true shooting": "TS_PCT", "true shooting percentage": "TS_PCT",
            "tm_tov_pct": "TM_TOV_PCT", "turnover_percentage": "TM_TOV_PCT",
            "turnover percentage": "TM_TOV_PCT", "turnover rate": "TM_TOV_PCT",
        }
        ranked_metrics = {"DEF_RATING", "TS_PCT", "TM_TOV_PCT"}
        ranked_directions = {"DEF_RATING": "asc", "TS_PCT": "desc",
                             "TM_TOV_PCT": "asc"}
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
            metric = (key if key in ranked_metrics
                      else metric_aliases.get(key.casefold().replace("-", "_")))
            if metric in ranked_metrics:
                args["requested_metric"] = metric
                requirement_direction = next((item.get("ranking_direction")
                                                for item in requirement_args
                                                if item.get("ranking_direction") is not None), None)
                raw_direction = (requirement_direction
                                 if requirement_direction is not None
                                 else args.get("ranking_direction"))
                direction_aliases = {"ascending":"asc", "lowest":"asc",
                                     "minimum":"asc", "descending":"desc",
                                     "highest":"desc", "maximum":"desc"}
                direction = str(raw_direction or "").strip().casefold()
                direction = direction_aliases.get(direction, direction)
                args["ranking_direction"] = (direction if direction in {"asc", "desc"}
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
    """Build typed home/away scoring aggregates from admitted log evidence."""
    from decimal import Decimal
    logs = [item for item in evidence
            if item.capability == "game_logs" and isinstance(item.rows, Mapping)]
    home = next((item for item in logs if item.rows.get("filters") == "home games"), None)
    away = next((item for item in logs if item.rows.get("filters") == "away games"), None)
    asks_delta = any("home" in item.description.casefold()
                     and "away" in item.description.casefold()
                     for item in task.calculation_requirements)
    if not (home and away and asks_delta):
        return None
    try:
        home_avg = Decimal(str(home.rows["average_pts"]))
        away_avg = Decimal(str(away.rows["average_pts"]))
        home_n = int(home.rows["total"]); away_n = int(away.rows["total"])
    except (KeyError, TypeError, ValueError):
        return None
    delta = home_avg - away_avg
    requirement_id = next(item.id for item in task.calculation_requirements
                          if "home" in item.description.casefold()
                          and "away" in item.description.casefold())
    player = home.rows.get("player") or away.rows.get("player") or "The player"
    season = home.season or away.season or "the selected season"
    def one(value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.1'))}"
    calculations = [
        {"calculation_id":"home_mean_pts", "operation":"mean",
         "inputs":[{"evidence_id":home.evidence_id,"path":"rows.matches[].pts"}],
         "result":home_avg, "unit":"points_per_game"},
        {"calculation_id":"away_mean_pts", "operation":"mean",
         "inputs":[{"evidence_id":away.evidence_id,"path":"rows.matches[].pts"}],
         "result":away_avg, "unit":"points_per_game"},
        {"calculation_id":"home_minus_away", "requirement_id":requirement_id,
         "operation":"subtract",
         "inputs":[{"evidence_id":home.evidence_id,"path":"rows.average_pts"},
                   {"evidence_id":away.evidence_id,"path":"rows.average_pts"}],
         "result":delta, "unit":"points_per_game"},
    ]
    claims = [
        Claim(text=f"{player} averaged {one(home_avg)} points per game in {home_n} home games in {season}.",
              kind="derived", evidence_ids=[home.evidence_id], calculation_id="home_mean_pts"),
        Claim(text=f"{player} averaged {one(away_avg)} points per game in {away_n} away games in {season}.",
              kind="derived", evidence_ids=[away.evidence_id], calculation_id="away_mean_pts"),
        Claim(text=f"The home-minus-away scoring difference was {one(delta)} points per game.",
              kind="derived", evidence_ids=[home.evidence_id,away.evidence_id], calculation_id="home_minus_away"),
    ]
    return DraftReport(sections=["Home and away scoring"], claims=claims,
        calculations=calculations, blocked_calculation_requirement_ids=[], gaps=[])


def _deterministic_player_comparison_draft(
    task: TaskSpec, evidence: Sequence[EvidenceEnvelope],
) -> DraftReport | None:
    """Project comparison facts and typed margin from canonical pair evidence."""
    from decimal import Decimal
    item = next((ev for ev in evidence
                 if ev.capability == "player_comparison"
                 and isinstance(ev.rows, Mapping)), None)
    if item is None:
        return None
    requirements = {req.id: req.description.casefold()
                    for req in task.calculation_requirements}
    difference_id = next((rid for rid, text in requirements.items()
                          if any(word in text for word in ("margin", "difference", "by how much"))), None)
    leader_id = next((rid for rid, text in requirements.items()
                      if any(word in text for word in ("higher", "leader", "scores more"))), None)
    if not (difference_id or leader_id):
        return None
    try:
        a = item.rows["a"]; b = item.rows["b"]
        a_name, b_name = str(a["name"]), str(b["name"])
        a_ppg, b_ppg = Decimal(str(a["ppg"])), Decimal(str(b["ppg"]))
    except (KeyError, TypeError, ValueError):
        return None
    high_name, high_ppg, high_path = ((a_name, a_ppg, "rows.a.ppg")
                                      if a_ppg >= b_ppg
                                      else (b_name, b_ppg, "rows.b.ppg"))
    low_name, low_ppg, low_path = ((b_name, b_ppg, "rows.b.ppg")
                                   if a_ppg >= b_ppg
                                   else (a_name, a_ppg, "rows.a.ppg"))
    calculations = []
    claims = [
        Claim(text=f"{a_name} averaged {a_ppg} points per game in {item.season or 'the selected season'}.",
              kind="observed", evidence_ids=[item.evidence_id]),
        Claim(text=f"{b_name} averaged {b_ppg} points per game in {item.season or 'the selected season'}.",
              kind="observed", evidence_ids=[item.evidence_id]),
    ]
    if leader_id:
        calculations.append({"calculation_id":"ppg_leader_rank",
            "requirement_id":leader_id, "operation":"rank_desc",
            "inputs":[{"evidence_id":item.evidence_id,"path":high_path},
                      {"evidence_id":item.evidence_id,"path":low_path}],
            "result":1, "unit":"rank", "subject_input":0})
        claims.append(Claim(text=f"{high_name} scored more points per game than {low_name}.",
                            kind="derived", evidence_ids=[item.evidence_id],
                            calculation_id="ppg_leader_rank"))
    if difference_id:
        margin = high_ppg - low_ppg
        calculations.append({"calculation_id":"ppg_difference",
            "requirement_id":difference_id, "operation":"subtract",
            "inputs":[{"evidence_id":item.evidence_id,"path":high_path},
                      {"evidence_id":item.evidence_id,"path":low_path}],
            "result":margin,"unit":"points per game"})
        claims.append(Claim(
            text=f"{high_name} scored {margin} points per game more than {low_name}.",
            kind="derived", evidence_ids=[item.evidence_id],
            calculation_id="ppg_difference"))
    shooting = {str(ev.rows.get("PLAYER_NAME")): ev for ev in evidence
                if ev.capability == "shooting_efficiency"
                and isinstance(ev.rows, Mapping)
                and ev.rows.get("PLAYER_NAME") and ev.rows.get("TS_PCT") is not None}
    for name in (a_name, b_name):
        ev = shooting.get(name)
        if ev is not None:
            claims.append(Claim(text=f"{name} had a {ev.rows['TS_PCT']}% true shooting percentage.",
                                kind="observed", evidence_ids=[ev.evidence_id]))
    return DraftReport(sections=["Player comparison"], claims=claims,
        calculations=calculations,
        blocked_calculation_requirement_ids=[], gaps=[])


def _deterministic_rank_draft(
    task: TaskSpec, evidence: Sequence[EvidenceEnvelope],
) -> DraftReport | None:
    """Project one typed team-rating rank into a canonical claim.

    The tool result is already sorted by the requested direction and carries
    the requested metric identity. Publication uses only the first row's named
    metric, never free-form synthesis over the expanded row.
    """
    labels = {"DEF_RATING": "defensive rating",
              "TS_PCT": "true shooting percentage",
              "TM_TOV_PCT": "turnover percentage"}
    directions = {"asc": "lowest", "desc": "highest"}
    for item in evidence:
        if item.capability != "team_ratings" or not isinstance(item.rows, list) or not item.rows:
            continue
        metric = item.metric_definitions.get("__requested_metric__")
        if metric not in labels:
            continue
        row = item.rows[0]
        team = row.get("TEAM_NAME") or row.get("TEAM")
        value = row.get(metric)
        if not team or value is None:
            continue
        direction = next((
            requirement.capability_arguments.get("ranking_direction")
            for requirement in task.requirements
            if "team_ratings" in requirement.capability_options
            and requirement.capability_arguments.get("requested_metric") == metric
        ), None)
        direction = direction if direction in directions else (
            "asc" if metric in {"DEF_RATING", "TM_TOV_PCT"} else "desc")
        return DraftReport(
            sections=["Team rating leader"],
            claims=[Claim(
                text=(f"{team} had the {directions[direction]} "
                      f"{labels[metric]} in {item.season or 'the selected season'}: "
                      f"{value}."),
                kind="observed", evidence_ids=[item.evidence_id])],
            calculations=[], blocked_calculation_requirement_ids=[], gaps=[])
    return None


class ModelSynthesizer(ModelStage):
    prompt_name = "synthesizer"
    route = "synthesizer"
    schema = DraftReport

    async def synthesize(
        self, task: TaskSpec, evidence: Sequence[EvidenceEnvelope]
    ) -> DraftReport:
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
        return _validate_draft(draft, evidence, task)


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
        try:
            report = await self._generate(payload)
        except RuntimeError as exc:
            if not str(exc).startswith("all structured-output providers failed"):
                raise
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
                data={"status": "failed", "error": exception_text(exc)},
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
