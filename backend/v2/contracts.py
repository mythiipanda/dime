from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
import calendar
import math
import re
from typing import Any, Literal, Mapping

from pydantic import (AfterValidator, BaseModel, ConfigDict, Field, StrictBool,
                    StrictFloat, StrictInt, field_validator, model_validator)
from pydantic_core import PydanticCustomError
from typing import Annotated
from v2.arguments import CapabilityArgumentSet

class RunMode(StrEnum):
    QUICK = "quick"
    DEEP_DIVE = "deep_dive"
    PROJECT = "project"

class PlanStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"

class ClaimKind(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"
    PROJECTION = "projection"
    JUDGMENT = "judgment"

class VerificationStatus(StrEnum):
    PASS = "pass"
    REPAIR = "repair"
    PARTIAL = "partial"

class PreconditionCheck(StrEnum):
    NUMERAL = "numeral"
    ENTITY = "entity"
    UNIT = "unit"
    SCOPE = "scope"

class NodePrecondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check: PreconditionCheck
    node_id: str = Field(min_length=1, max_length=256)
    requirement_id: str | None = Field(default=None, max_length=64)
    output_id: str | None = None
    column: str | None = None
    expected_unit: str | None = None
    resolvable: StrictBool = True
    detail: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def validate_precondition(self) -> "NodePrecondition":
        if not self.node_id.strip() or not self.detail.strip():
            raise ValueError("precondition node and detail must be non-empty")
        if self.check == PreconditionCheck.NUMERAL and self.output_id is None:
            raise ValueError("numeral precondition requires an output id")
        if not self.resolvable and self.check != PreconditionCheck.NUMERAL:
            raise ValueError("only numeral preconditions may be unresolvable")
        if self.column is not None and not self.column.strip():
            raise ValueError("precondition column must be non-empty when present")
        if self.expected_unit is not None and not self.expected_unit.strip():
            raise ValueError("precondition unit must be non-empty when present")
        return self

def precondition_repair_instruction(
    check: PreconditionCheck | str,
    node_id: str,
    requirement_id: str | None,
    detail: str,
) -> str:
    requirement = requirement_id if requirement_id is not None else "task"
    return (
        f"precondition {str(check)} failed for node {node_id!r} "
        f"requirement {requirement!r}: {detail}; fix the plan, not the prose"
    )

class GapKind(StrEnum):
    MISSING_EVIDENCE = "missing_evidence"
    SOURCE_CONFLICT = "source_conflict"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    EXECUTION_FAILURE = "execution_failure"
    SYNTHESIS_INCOMPLETE = "synthesis_incomplete"
    PROFILE_NAME_RESOLUTION_UNAVAILABLE = "profile/name_resolution_unavailable"
    JUDGE_UNAVAILABLE = "judge_unavailable"

MAX_INTAKE_CONTEXT_TURNS = 8
CanonicalDimensionId = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Z][A-Z0-9_]*$")]
RequirementKind = Literal["evidence", "calculation", "task"]

class EntityRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(max_length=256)
    type: Literal["player", "team", "game", "league"]
    display_name: str = Field(max_length=512)

    @model_validator(mode="after")
    def validate_identity(self) -> "EntityRef":
        if not self.id.strip() or not self.display_name.strip():
            raise ValueError("entity id and display name must be non-empty")
        return self

def canonical_entity_id(entity_type: str, entity_id: str, display_name: str = "") -> str:
    try:
        from shared.tools._core import coerce_team_id
        from shared.tools.player import coerce_player_id
        resolver = {"team": coerce_team_id, "player": coerce_player_id}.get(entity_type)
        if resolver is not None:
            for candidate in (entity_id, display_name):
                try:
                    return str(resolver(candidate))
                except (TypeError, ValueError):
                    continue
    except ImportError:
        pass
    return " ".join(entity_id.casefold().replace("-", " ").replace("_", " ").split())

def canonical_entity_ref(entity) -> tuple[str, str]:
    return (entity.type, canonical_entity_id(entity.type, entity.id, entity.display_name))

def _is_canonical_season(value: str) -> bool:
    parts = value.split("-")
    return (len(parts) == 2 and len(parts[0]) == 4 and len(parts[1]) == 2
            and all(part.isdigit() for part in parts)
            and int(parts[1]) == (int(parts[0]) + 1) % 100)

WINDOW_ARGUMENT_NAMES = frozenset({"start_date", "end_date", "month"})

def _parse_window_bound(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text.split("T", 1)[0])
    except ValueError:
        return None

def _parse_month_number(month: Any) -> tuple[int | None, int | None]:
    if month is None:
        return None, None
    text = str(month).strip().lower()
    if not text:
        return None, None
    if "-" in text:
        parts = text.split("-")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            year, number = int(parts[0]), int(parts[1])
            if len(parts[0]) == 4 and 1 <= number <= 12:
                return year, number
        return None, None
    if text.isdigit() and 1 <= int(text) <= 12:
        return None, int(text)
    names = {name.lower(): index for index, name in enumerate(calendar.month_name) if name}
    names.update({name.lower(): index for index, name in enumerate(calendar.month_abbr) if name})
    number = names.get(text)
    return None, number

def _month_window(month: Any, season: str | None) -> tuple[date | None, date | None]:
    year, number = _parse_month_number(month)
    if number is None:
        return None, None
    if year is None:
        if season is None or not _is_canonical_season(str(season)):
            return None, None
        start_year = int(str(season).split("-")[0])
        year = start_year if number >= 8 else start_year + 1
    last_day = calendar.monthrange(year, number)[1]
    return date(year, number, 1), date(year, number, last_day)

def window_of_arguments(
    arguments: Mapping[str, Any],
    season: str | None = None,
) -> tuple[date | None, date | None]:
    start = _parse_window_bound(arguments.get("start_date"))
    end = _parse_window_bound(arguments.get("end_date"))
    if start is None and end is None and arguments.get("month") not in (None, ""):
        start, end = _month_window(arguments.get("month"), season)
    return start, end

def format_window(start: date | None, end: date | None) -> str:
    if start is not None and end is not None:
        return f"{start.isoformat()} to {end.isoformat()}"
    if start is not None:
        return f"{start.isoformat()} onward"
    if end is not None:
        return f"through {end.isoformat()}"
    return "full season"

def validate_window_order(start: date | None, end: date | None) -> None:
    if start is not None and end is not None and start > end:
        raise ValueError("window start must not be after window end")

class SeasonRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(max_length=7)
    source: Literal["user", "context", "default", "resolved"]
    confidence: StrictFloat = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_identity(self) -> "SeasonRef":
        if not self.value.strip():
            raise ValueError("season value must be non-empty")
        if not _is_canonical_season(self.value):
            raise ValueError("season must use consecutive YYYY-YY format")
        return self

class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_content(self) -> "ConversationTurn":
        if not self.content.strip():
            raise ValueError("conversation content must be non-empty")
        return self

class CalculationRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1, max_length=1000)
    metric_ids: list[CanonicalDimensionId] = Field(default_factory=list, max_length=16)
    requested_outputs: list[CanonicalDimensionId] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_dimensions(self) -> "CalculationRequirement":
        for field_name in ("metric_ids", "requested_outputs"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        return self

class EvidenceRequirement(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "description":
                "A single evidence requirement. Task scope lives ONLY on the "
                "enclosing TaskSpec: season, as_of, window_start and window_end "
                "are NOT fields of this object and any other unlisted key is "
                "rejected as an extra field. Per-capability inputs go in "
                "capability_argument_sets[].arguments, which is a typed "
                "arguments object containing an \"entries\" array - never a flat "
                "{\"key\": \"value\"} map."
        },
    )

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1, max_length=1000)
    capability_options: list[str] = Field(min_length=1, max_length=8)

    capability_arguments: dict[str, Any] = Field(default_factory=dict, max_length=32)
    capability_argument_sets: list[CapabilityArgumentSet] = Field(default_factory=list, max_length=8)
    metric_ids: list[CanonicalDimensionId] = Field(default_factory=list, max_length=16)
    requested_outputs: list[CanonicalDimensionId] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_requirement(self) -> "EvidenceRequirement":
        if not self.description.strip():
            raise ValueError("requirement description must be non-empty")
        if any(not value.strip() for value in self.capability_options):
            raise ValueError("requirement capabilities must be non-empty")
        if len(self.capability_options) != len(set(self.capability_options)):
            raise ValueError("requirement capabilities must not contain duplicates")
        if self.capability_argument_sets:
            ids = [item.capability_id for item in self.capability_argument_sets]
            if len(ids) != len(set(ids)) or set(ids) != set(self.capability_options):
                raise ValueError("capability argument sets must uniquely cover options")
            self.capability_argument_sets.sort(key=lambda item: item.capability_id)
        for field_name in ("metric_ids", "requested_outputs"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        return self

def _drop_ranked_argument_conflicts_from_schema(schema: dict) -> dict:
    properties = schema.get("properties")
    if isinstance(properties, dict):
        properties.pop("ranked_argument_conflicts", None)
    required = schema.get("required")
    if isinstance(required, list) and "ranked_argument_conflicts" in required:
        required.remove("ranked_argument_conflicts")
    return schema

class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(max_length=2000)
    mode: RunMode
    deliverable: str = Field(max_length=1000)
    metric_ids: list[CanonicalDimensionId] = Field(default_factory=list, max_length=32)
    requested_outputs: list[CanonicalDimensionId] = Field(default_factory=list, max_length=32)
    entities: list[EntityRef] = Field(default_factory=list, max_length=64)
    season: SeasonRef | None = Field(
        default=None,
        description="Task-wide season scope, set HERE on the TaskSpec and nowhere "
                    "else. Object form: {\"value\": \"2025-26\", \"source\": "
                    "\"user\"|\"context\"|\"default\"|\"resolved\", \"confidence\": "
                    "0.0-1.0}. Do not repeat season inside requirements[] entries: "
                    "requirements forbid extra fields and will reject it.")
    as_of: date | None = Field(
        default=None,
        description="Task-wide as-of date (YYYY-MM-DD), set HERE on the TaskSpec "
                    "only. Never place as_of on a requirements[] entry; "
                    "requirements forbid extra fields and will reject it.")
    window_start: date | None = Field(
        default=None,
        description="Inclusive start of the task-wide time window (YYYY-MM-DD), "
                    "set HERE on the TaskSpec only. Never place window_start on a "
                    "requirements[] entry; requirements forbid extra fields and "
                    "will reject it.")
    window_end: date | None = Field(
        default=None,
        description="Inclusive end of the task-wide time window (YYYY-MM-DD), not "
                    "before window_start, set HERE on the TaskSpec only. Never "
                    "place window_end on a requirements[] entry; requirements "
                    "forbid extra fields and will reject it.")

    subject_entity_type: str | None = Field(default=None, max_length=64)
    subquestions: list[str] = Field(default_factory=list, max_length=32)
    required_evidence: list[str] = Field(default_factory=list, max_length=32)
    requirements: list[EvidenceRequirement] = Field(
        default_factory=list, max_length=32)
    calculation_requirements: list[CalculationRequirement] = Field(
        default_factory=list, max_length=32)
    assumptions: list[str] = Field(default_factory=list, max_length=32)
    open_questions: list[str] = Field(default_factory=list, max_length=32)
    skills: list[str] = Field(default_factory=list, max_length=16)

    ranked_argument_conflicts: list[dict[str, str]] = Field(
        default_factory=list, max_length=32)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return _drop_ranked_argument_conflicts_from_schema(handler(core_schema))

    @field_validator("ranked_argument_conflicts")
    @classmethod
    def _validate_ranked_argument_conflicts(
        cls, rows: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        for row in rows:
            if (set(row) != {"route", "capability_id", "key", "rule"}
                    or row["rule"] != "ranked-argument-conflict"
                    or not row["capability_id"].strip()
                    or not row["key"].strip()):
                raise ValueError(
                    "ranked_argument_conflicts rows must carry exact "
                    "{route, capability_id, key, rule} keys with rule "
                    "'ranked-argument-conflict'")
        return rows

    @model_validator(mode="after")
    def validate_scope(self) -> "TaskSpec":
        validate_window_order(self.window_start, self.window_end)
        if not self.goal.strip() or not self.deliverable.strip():
            raise ValueError("task goal and deliverable must be non-empty")
        for field_name in ("subquestions", "required_evidence", "assumptions",
                           "open_questions", "skills", "metric_ids", "requested_outputs"):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError(f"{field_name} must not contain empty values")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        requirement_ids = [item.id for item in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("requirements must not contain duplicate ids")
        calculation_ids = [item.id for item in self.calculation_requirements]
        if len(calculation_ids) != len(set(calculation_ids)):
            raise ValueError("calculation requirements must not contain duplicate ids")
        overlap = set(requirement_ids) & set(calculation_ids)
        if overlap:
            raise ValueError(f"evidence and calculation requirement ids overlap: {sorted(overlap)}")
        entity_keys = [(item.type, item.id) for item in self.entities]
        if len(entity_keys) != len(set(entity_keys)):
            raise ValueError("entities must not contain duplicate identities")
        return self

class RequirementReview(BaseModel):

    model_config = ConfigDict(extra="forbid")

    requirements: list[EvidenceRequirement] = Field(
        default_factory=list, max_length=32)
    calculation_requirements: list[CalculationRequirement] = Field(
        default_factory=list, max_length=32)
    missing_subquestions: list[str] = Field(default_factory=list, max_length=32)
    missing_skills: list[str] = Field(default_factory=list, max_length=16)

    ranked_argument_conflicts: list[dict[str, str]] = Field(
        default_factory=list, max_length=32)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return _drop_ranked_argument_conflicts_from_schema(handler(core_schema))

    @model_validator(mode="after")
    def validate_review(self) -> "RequirementReview":
        requirement_ids = [item.id for item in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("requirements must not contain duplicate ids")
        calculation_ids = [item.id for item in self.calculation_requirements]
        if len(calculation_ids) != len(set(calculation_ids)):
            raise ValueError("calculation requirements must not contain duplicate ids")
        for field_name in ("missing_subquestions", "missing_skills"):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError(f"{field_name} must not contain empty values")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        return self

class PlanNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=2000)
    depends_on: list[str] = Field(default_factory=list, max_length=32)
    capability_hints: list[str] = Field(default_factory=list, max_length=16)
    covers_requirement_ids: list[str] = Field(default_factory=list, max_length=32)
    arguments: dict[str, Any] = Field(default_factory=dict, max_length=64)
    max_attempts: StrictInt = Field(default=1, ge=1, le=5)
    status: PlanStatus = PlanStatus.PENDING

    @model_validator(mode="after")
    def validate_selection(self) -> "PlanNode":
        if not self.id.strip() or not self.description.strip():
            raise ValueError("plan node id and description must be non-empty")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("plan node dependencies must not contain duplicates")
        if len(self.capability_hints) != len(set(self.capability_hints)):
            raise ValueError("plan node capability hints must not contain duplicates")
        if any(not value.strip() for value in self.capability_hints):
            raise ValueError("plan node capability hints must be non-empty")
        if len(self.covers_requirement_ids) != len(
            set(self.covers_requirement_ids)
        ):
            raise ValueError("covered requirement ids must not contain duplicates")
        if any(not value.strip() for value in self.covers_requirement_ids):
            raise ValueError("covered requirement ids must be non-empty")

        def validate_finite(value: Any) -> None:
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("plan node arguments must contain only finite numbers")
            if isinstance(value, Decimal) and not value.is_finite():
                raise ValueError("plan node arguments must contain only finite numbers")
            if isinstance(value, dict):
                for child in value.values():
                    validate_finite(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    validate_finite(child)

        validate_finite(self.arguments)
        return self

class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[PlanNode] = Field(max_length=32)

    @model_validator(mode="after")
    def validate_dependencies(self) -> Plan:
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("plan node ids must be unique")
        known = set(ids)
        for node in self.nodes:
            missing = set(node.depends_on) - known
            if missing:
                raise ValueError(f"unknown dependencies for {node.id}: {sorted(missing)}")
            if node.id in node.depends_on:
                raise ValueError(f"plan node {node.id} cannot depend on itself")
        visiting: set[str] = set()
        visited: set[str] = set()
        graph = {node.id: node.depends_on for node in self.nodes}

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError("plan dependencies must be acyclic")
            if node_id in visited:
                return
            visiting.add(node_id)
            for parent in graph[node_id]:
                visit(parent)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in ids:
            visit(node_id)
        return self

class WarehouseSourceIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["warehouse"] = "warehouse"
    warehouse_id: Literal["frozen-eval", "configured-runtime"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

class LiveSourceIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["live"] = "live"
    source: Literal["nba_api", "basketball_reference", "espn", "fixture"]

class CompositeSourceIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["composite"] = "composite"
    warehouse_id: Literal["frozen-eval", "configured-runtime"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    live_sources: list[Literal["nba_api", "basketball_reference", "espn"]] = Field(
        min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_sources(self):
        if len(self.live_sources) != len(set(self.live_sources)):
            raise ValueError("composite live sources must be unique")
        return self

SourceIdentity = Annotated[
    WarehouseSourceIdentity | LiveSourceIdentity | CompositeSourceIdentity,
    Field(discriminator="kind"),
]

class LiveFallback(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    warehouse_table: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    requested_season: str = Field(pattern=r"^\d{4}-\d{2}$")
    warehouse_seasons: list[str] = Field(default_factory=list, max_length=64)
    live_source: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    outcome: Literal["served", "stale", "empty"]

    @model_validator(mode="after")
    def validate_seasons(self):
        if any(re.fullmatch(r"\d{4}-\d{2}", season) is None
               for season in self.warehouse_seasons):
            raise ValueError("warehouse seasons must be YYYY-YY")
        if len(self.warehouse_seasons) != len(set(self.warehouse_seasons)):
            raise ValueError("warehouse seasons must be unique")
        return self

class EvidenceEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=256)
    capability: str = Field(max_length=256)
    source: str = Field(max_length=2000)
    observed_at: datetime
    season: str | None = Field(default=None, max_length=7)
    vintages: dict[str, str] = Field(default_factory=dict, max_length=64)
    task_season_scoped: StrictBool = True
    as_of: date | None = None
    window_start: date | None = None
    window_end: date | None = None
    entities: list[EntityRef] = Field(default_factory=list, max_length=64)
    rows: list[dict[str, Any]] | dict[str, Any]
    units: dict[str, str] = Field(default_factory=dict, max_length=256)
    metric_definitions: dict[str, str] = Field(default_factory=dict, max_length=256)
    qualification: str | None = Field(default=None, max_length=4000)
    coverage: str | None = Field(default=None, max_length=4000)
    lineage: list[str] = Field(default_factory=list, max_length=32)
    source_identity: SourceIdentity | None = None
    live_fallback: LiveFallback | None = None
    warnings: list[str] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def validate_identity(self) -> "EvidenceEnvelope":
        validate_window_order(self.window_start, self.window_end)
        if (not self.evidence_id.strip() or not self.capability.strip()
                or not self.source.strip()):
            raise ValueError("evidence identity, capability, and source must be non-empty")
        if self.observed_at.utcoffset() is None:
            raise ValueError("evidence observed_at must include timezone")
        for field_name in ("season", "qualification", "coverage"):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise ValueError(f"evidence {field_name} must be non-empty when present")
        if self.season is not None and not _is_canonical_season(self.season):
            raise ValueError("evidence season must use consecutive YYYY-YY format")
        for field_name in ("vintages", "units", "metric_definitions"):
            values = getattr(self, field_name)
            if any(not str(key).strip() or not str(value).strip()
                   for key, value in values.items()):
                raise ValueError(f"evidence {field_name} must be non-empty")
        for field_name in ("lineage", "warnings"):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError(f"evidence {field_name} must not contain empty values")
            if len(values) != len(set(values)):
                raise ValueError(f"evidence {field_name} must not contain duplicates")
        entity_keys = [(item.type, item.id) for item in self.entities]
        if len(entity_keys) != len(set(entity_keys)):
            raise ValueError("evidence entities must not contain duplicate identities")

        visited = 0

        def validate_rows(value: Any, *, depth: int = 0) -> None:
            nonlocal visited
            visited += 1
            if visited > 100_000:
                raise ValueError("evidence rows cannot exceed 100000 values")
            if depth > 16:
                raise ValueError("evidence rows cannot exceed 16 levels")
            if isinstance(value, str) and len(value) > 200_000:
                raise ValueError("evidence row text cannot exceed 200000 characters")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("evidence rows must contain only finite numbers")
            if isinstance(value, Decimal) and not value.is_finite():
                raise ValueError("evidence rows must contain only finite numbers")
            if isinstance(value, dict):
                if len(value) > 256:
                    raise ValueError("evidence row objects cannot exceed 256 fields")
                if any(len(key) > 1000 for key in value):
                    raise ValueError("evidence row keys cannot exceed 1000 characters")
                for child in value.values():
                    validate_rows(child, depth=depth + 1)
            elif isinstance(value, list):
                if len(value) > 10_000:
                    raise ValueError("evidence row arrays cannot exceed 10000 items")
                for child in value:
                    validate_rows(child, depth=depth + 1)

        validate_rows(self.rows)
        return self

class BooleanOutputValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["boolean"] = "boolean"
    value: StrictBool

class IntegerOutputValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["integer"] = "integer"
    value: StrictInt

    @model_validator(mode="before")
    @classmethod
    def exact_integer_type(cls, value: Any) -> Any:
        raw = value.get("value") if isinstance(value, dict) else None
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ValueError("integer output value requires an integer input")
        return value

class FloatOutputValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["float"] = "float"
    value: StrictFloat

    @model_validator(mode="before")
    @classmethod
    def exact_float_type(cls, value: Any) -> Any:
        raw = value.get("value") if isinstance(value, dict) else None
        if not isinstance(raw, float):
            raise ValueError("float output value requires a float input")
        return value

    @model_validator(mode="after")
    def finite(self) -> "FloatOutputValue":
        if not math.isfinite(self.value):
            raise ValueError("float output value must be finite")
        return self

DECIMAL_TEXT_PATTERN = (
    r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$")

def _finite_decimal_text(value: str) -> str:
    if not Decimal(value).is_finite():
        raise ValueError("decimal text must be finite")
    return value

FiniteDecimalText = Annotated[
    str,
    Field(min_length=1, max_length=1000, pattern=DECIMAL_TEXT_PATTERN),
    AfterValidator(_finite_decimal_text),
]

class DecimalOutputValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["decimal"] = "decimal"
    value: FiniteDecimalText

class StringOutputValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["string"] = "string"
    value: str = Field(max_length=200000)

AdmittedOutputValue = Annotated[
    BooleanOutputValue | IntegerOutputValue | FloatOutputValue |
    DecimalOutputValue | StringOutputValue,
    Field(discriminator="kind"),
]

class DeclaredOutputUnit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["declared"] = "declared"
    value: str = Field(min_length=1, max_length=256)

class UnitlessOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["unitless"] = "unitless"

OutputUnitAuthority = Annotated[
    DeclaredOutputUnit | UnitlessOutput, Field(discriminator="kind")]

class EvidenceOutputBinding(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_kind: Literal["evidence", "task"] = "evidence"
    requirement_id: str | None = Field(default=None, min_length=1, max_length=64)
    output_id: CanonicalDimensionId
    node_id: str = Field(min_length=1, max_length=256)
    evidence_id: str = Field(min_length=1, max_length=256)
    selector: str = Field(min_length=1, max_length=1000)
    row_selector: str | None = Field(default=None, min_length=1, max_length=1000)
    value: AdmittedOutputValue
    subject_entity_type: str | None = Field(default=None, min_length=1, max_length=64)
    subject_entity_id: str | None = Field(default=None, min_length=1, max_length=256)
    subject_selector: str | None = Field(default=None, min_length=1, max_length=1000)
    unit: OutputUnitAuthority
    domain: str = Field(min_length=1, max_length=256, description="the exact capability name of the cited evidence envelope")

    @model_validator(mode="after")
    def validate_scope(self) -> "EvidenceOutputBinding":
        if self.requirement_kind == "task" and self.requirement_id is not None:
            return self.model_copy(update={"requirement_id": None})
        if self.requirement_kind == "evidence" and self.requirement_id is None:
            raise ValueError("evidence binding requires requirement id")
        subject_fields = (self.subject_entity_type, self.subject_entity_id,
                          self.subject_selector, self.row_selector)
        if any(value is None for value in subject_fields) and any(
                value is not None for value in subject_fields):
            raise ValueError("binding subject type, id, and selector must be supplied together")
        return self

class CalculationOutputBinding(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_kind: Literal["calculation"] = "calculation"
    requirement_id: str = Field(min_length=1, max_length=64)
    output_id: CanonicalDimensionId
    calculation_id: str = Field(min_length=1, max_length=256)

ClaimOutputBinding = Annotated[
    EvidenceOutputBinding | CalculationOutputBinding,
    Field(discriminator="requirement_kind"),
]

class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)
    kind: ClaimKind
    evidence_ids: list[str] = Field(default_factory=list, max_length=32)
    calculation_id: str | None = Field(default=None, max_length=256)
    confidence: StrictFloat | None = Field(default=None, ge=0, le=1)
    output_bindings: list[ClaimOutputBinding] = Field(default_factory=list, max_length=64)
    artifact_id: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def validate_support(self) -> Claim:
        if not self.text.strip():
            raise ValueError("claim text must be non-empty")
        if any(not evidence_id.strip() for evidence_id in self.evidence_ids):
            raise ValueError("claim evidence_ids must not contain empty values")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("claim evidence_ids must not contain duplicates")
        binding_ids = [
            (item.requirement_kind, item.requirement_id, item.output_id)
            for item in self.output_bindings
        ]
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("claim output bindings must be unique")
        if any(isinstance(item, EvidenceOutputBinding)
               and item.evidence_id not in self.evidence_ids
               for item in self.output_bindings):
            raise ValueError("claim output binding must cite claim evidence")
        if any(isinstance(item, CalculationOutputBinding)
               and item.calculation_id != self.calculation_id
               for item in self.output_bindings):
            raise ValueError("claim calculation binding must cite claim calculation")
        if self.kind in (ClaimKind.OBSERVED, ClaimKind.DERIVED):
            if not self.evidence_ids:
                raise ValueError("observed and derived claims require evidence")
        if (self.kind == ClaimKind.DERIVED
                and (self.calculation_id is None or not self.calculation_id.strip())):
            raise ValueError("derived claims require a non-empty calculation id")
        if self.kind != ClaimKind.DERIVED and self.calculation_id is not None:
            raise ValueError("only derived claims may name a calculation id")
        if self.kind == ClaimKind.PROJECTION and self.confidence is None:
            raise ValueError("projection claims require confidence")
        if self.kind == ClaimKind.PROJECTION and not self.evidence_ids:
            raise ValueError("projection claims require evidence")
        if self.kind != ClaimKind.PROJECTION and self.confidence is not None:
            raise ValueError("only projection claims may name confidence")
        return self

class DeclaredCalculationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_id: str = Field(min_length=1, max_length=256)
    path: str = Field(min_length=1, max_length=1000)

class DeclaredCalculation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    calculation_id: str = Field(min_length=1, max_length=256)
    requirement_id: str | None = Field(default=None, max_length=64)
    operation: Literal["add", "subtract", "multiply", "divide", "percent",
                       "mean", "rank_desc", "rank_asc"]
    inputs: list[DeclaredCalculationInput] = Field(min_length=1, max_length=256)
    result: FiniteDecimalText
    unit: str | None = Field(default=None, max_length=256)
    subject_input: StrictInt | None = Field(default=None, ge=0)

class ArtifactKind(StrEnum):
    CHART = "chart"
    SHOT_CHART = "shot_chart"
    TABLE = "table"
    COMPARE = "compare"


class ArtifactPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    x: str = Field(min_length=1, max_length=256)
    output_id: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_point(self) -> "ArtifactPoint":
        if not self.x.strip() or not self.output_id.strip():
            raise ValueError("artifact point x and output_id must be non-empty")
        return self


class ArtifactSeries(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=256)
    points: list[ArtifactPoint] = Field(max_length=512)

    @model_validator(mode="after")
    def validate_series(self) -> "ArtifactSeries":
        if not self.name.strip():
            raise ValueError("artifact series name must be non-empty")
        labels = [point.x for point in self.points]
        if len(labels) != len(set(labels)):
            raise ValueError("artifact series points must have distinct x")
        return self


class ArtifactIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=256)
    kind: ArtifactKind
    title: str = Field(min_length=1, max_length=256)
    footnote: str | None = Field(default=None, max_length=512)
    series: list[ArtifactSeries] = Field(max_length=32)

    @model_validator(mode="after")
    def validate_intent(self) -> "ArtifactIntent":
        if not self.title.strip():
            raise ValueError("artifact title must be non-empty")
        if not self.id.strip():
            raise ValueError("artifact id must be non-empty")
        if self.kind in {ArtifactKind.CHART, ArtifactKind.SHOT_CHART} \
                and not any(series.points for series in self.series):
            raise ValueError(
                f"a {self.kind.value} artifact needs at least one point")
        return self


class DraftReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[str] = Field(max_length=32)
    claims: list[Claim] = Field(max_length=128)
    artifacts: list[ArtifactIntent] = Field(default_factory=list, max_length=8)
    calculations: list[DeclaredCalculation] = Field(default_factory=list, max_length=128)
    blocked_calculation_requirement_ids: list[str] = Field(default_factory=list, max_length=32)
    gaps: list[str] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def validate_content(self) -> "DraftReport":
        calculation_ids = [item.calculation_id for item in self.calculations]
        if len(calculation_ids) != len(set(calculation_ids)):
            raise ValueError("draft calculation ids must be unique")
        requirement_ids = [item.requirement_id for item in self.calculations
                           if item.requirement_id is not None]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("draft calculations must not duplicate requirement ids")
        if len(self.blocked_calculation_requirement_ids) != len(
                set(self.blocked_calculation_requirement_ids)):
            raise ValueError("blocked calculation requirement ids must be unique")
        for field_name in ("sections", "gaps"):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError(f"draft {field_name} must not contain empty values")
            if len(values) != len(set(values)):
                raise ValueError(f"draft {field_name} must not contain duplicates")
        return self

class Gap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: GapKind
    message: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=32)
    blocks: list[str] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def validate_references(self) -> "Gap":
        if not self.message.strip():
            raise ValueError("gap message must be non-empty")
        for field_name in ("evidence_ids", "blocks"):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError(f"gap {field_name} must not contain empty values")
            if len(values) != len(set(values)):
                raise ValueError(f"gap {field_name} must not contain duplicates")
        return self

class OutputFinalStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    requirement_kind: RequirementKind
    requirement_id: str | None = Field(default=None, max_length=64)
    output_id: CanonicalDimensionId
    status: Literal["complete", "missing", "rejected"]
    claim_index: StrictInt | None = Field(default=None, ge=0)
    binding: ClaimOutputBinding | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "OutputFinalStatus":
        if self.status == "complete":
            if self.binding is None or self.claim_index is None:
                raise ValueError("complete output requires admitted binding and claim")
        elif self.binding is not None or self.claim_index is not None:
            raise ValueError("incomplete output cannot carry publication authority")
        if self.binding is not None:
            if (self.binding.requirement_kind != self.requirement_kind
                    or self.binding.requirement_id != self.requirement_id
                    or self.binding.output_id != self.output_id):
                raise ValueError("output status identity must match admitted binding")
        return self

class ClaimSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(max_length=256)
    source: str = Field(max_length=2000)
    capability: str = Field(max_length=256)
    observed_at: datetime | None = None
    as_of: date | None = None
    vintages: dict[str, str] = Field(default_factory=dict, max_length=64)

    @model_validator(mode="after")
    def validate_identity(self) -> "ClaimSource":
        if not all(value.strip() for value in (
            self.evidence_id, self.source, self.capability
        )):
            raise ValueError("claim source identity must be non-empty")
        if self.observed_at is not None and self.observed_at.utcoffset() is None:
            raise ValueError("claim source observed_at must include timezone")
        if any(not str(key).strip() or not str(value).strip()
               for key, value in self.vintages.items()):
            raise ValueError("claim source vintages must be non-empty")
        return self

class VerifiedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_index: StrictInt = Field(ge=0)
    claim: Claim
    evidence_ids: list[str] = Field(default_factory=list, max_length=32)
    sources: list[ClaimSource] = Field(default_factory=list, max_length=32)
    output_bindings: list[ClaimOutputBinding] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def validate_references(self) -> "VerifiedClaim":
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("verified claim evidence_ids must not contain duplicates")
        source_ids = [item.evidence_id for item in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("verified claim sources must not contain duplicates")
        if self.evidence_ids != self.claim.evidence_ids:
            raise ValueError("verified claim evidence must match the claim")
        if not set(source_ids) <= set(self.evidence_ids):
            raise ValueError("verified claim sources must belong to its evidence")
        identities = [
            (item.requirement_kind, item.requirement_id, item.output_id)
            for item in self.output_bindings
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("verified claim output bindings must be unique")
        if any(isinstance(item, EvidenceOutputBinding)
               and item.evidence_id not in self.evidence_ids
               for item in self.output_bindings):
            raise ValueError("verified claim binding must cite claim evidence")
        if any(isinstance(item, CalculationOutputBinding)
               and item.calculation_id != self.claim.calculation_id
               for item in self.output_bindings):
            raise ValueError("verified calculation binding must cite claim calculation")
        return self

class ClaimResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_index: StrictInt = Field(ge=0)
    supported: StrictBool
    reasons: list[str] = Field(default_factory=list, max_length=64)
    evidence_spans: list[str] = Field(default_factory=list, max_length=32)
    uncertain: StrictBool = False

    @model_validator(mode="after")
    def validate_reason(self) -> "ClaimResult":
        if not self.supported and not self.reasons:
            raise PydanticCustomError("claim_unsupported_missing_reason", "unsupported claim result requires a reason")
        if self.supported and self.reasons:
            raise PydanticCustomError("claim_supported_has_reasons", "supported claim result cannot carry rejection reasons")
        if any(not reason.strip() for reason in self.reasons):
            raise ValueError("claim result reasons must not contain empty values")
        if len(self.reasons) != len(set(self.reasons)):
            raise ValueError("claim result reasons must not contain duplicates")
        if any(not span.strip() for span in self.evidence_spans):
            raise ValueError("claim result evidence spans must not contain empty values")
        if len(self.evidence_spans) != len(set(self.evidence_spans)):
            raise ValueError("claim result evidence spans must not contain duplicates")
        return self

class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VerificationStatus
    claim_results: list[ClaimResult] = Field(default_factory=list, max_length=128)
    missing_branches: list[str] = Field(default_factory=list, max_length=128)
    contradictions: list[str] = Field(default_factory=list, max_length=128)
    repair_instructions: list[str] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def validate_status(self) -> "VerificationReport":
        indices = [item.claim_index for item in self.claim_results]
        if len(indices) != len(set(indices)):
            raise PydanticCustomError("verification_duplicate_claim_index", "verification claim indices must be unique")
        for field_name in ("missing_branches", "contradictions",
                           "repair_instructions"):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise PydanticCustomError(
                    "verification_finding_empty",
                    f"{field_name} must not contain empty values")
            if len(values) != len(set(values)):
                raise PydanticCustomError(
                    "verification_finding_duplicate",
                    f"{field_name} must not contain duplicates")
        findings = (
            any(not item.supported for item in self.claim_results)
            or bool(self.missing_branches)
            or bool(self.contradictions)
            or bool(self.repair_instructions)
        )
        if self.status == VerificationStatus.PASS and findings:
            raise PydanticCustomError("verification_pass_with_findings", "pass status contradicts verification findings")
        if self.status == VerificationStatus.REPAIR and not findings:
            raise PydanticCustomError("verification_repair_without_findings", "repair status requires an actionable finding")
        return self

