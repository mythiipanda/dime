from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

from v2.contracts import (
    ConversationTurn,
    DraftReport,
    EvidenceEnvelope,
    Plan,
    PlanNode,
    TaskSpec,
    VerificationReport,
)

class FrozenList(list):
    def _reject(self, action: str) -> None:
        raise TypeError(f"verifier view is read-only: cannot {action}")

    def __setitem__(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("assign item")

    def __delitem__(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("delete item")

    def append(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("append")

    def extend(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("extend")

    def insert(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("insert")

    def remove(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("remove")

    def pop(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("pop")

    def clear(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("clear")

    def __iadd__(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("in-place add")

    def __imul__(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("in-place multiply")

    def sort(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("sort")

    def reverse(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("reverse")

class FrozenDict(dict):
    def _reject(self, action: str) -> None:
        raise TypeError(f"verifier view is read-only: cannot {action}")

    def __setitem__(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("assign item")

    def __delitem__(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("delete item")

    def pop(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("pop")

    def popitem(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("popitem")

    def clear(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("clear")

    def update(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("update")

    def setdefault(self, *args: Any, **kwargs: Any) -> Any:
        self._reject("setdefault")

def freeze_value(value: Any) -> Any:
    if isinstance(value, FrozenList | FrozenDict):
        return value
    if isinstance(value, dict):
        return FrozenDict({key: freeze_value(child) for key, child in value.items()})
    if isinstance(value, list):
        return FrozenList([freeze_value(child) for child in value])
    if isinstance(value, tuple):
        return tuple(freeze_value(child) for child in value)
    return value

@dataclass(frozen=True)
class EntityView:
    type: str
    id: str
    display_name: str

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        return {"type": self.type, "id": self.id, "display_name": self.display_name}

@dataclass(frozen=True)
class SeasonView:
    value: str
    source: str
    confidence: float

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        return {"value": self.value, "source": self.source, "confidence": self.confidence}

@dataclass(frozen=True)
class RequirementView:
    id: str
    description: str
    capability_options: tuple[str, ...]
    capability_arguments: Any
    capability_argument_sets: tuple[Any, ...]
    metric_ids: tuple[str, ...]
    requested_outputs: tuple[str, ...]

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "capability_options": list(self.capability_options),
            "capability_arguments": dict(self.capability_arguments) if isinstance(self.capability_arguments, Mapping) else self.capability_arguments,
            "capability_argument_sets": [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in self.capability_argument_sets],
            "metric_ids": list(self.metric_ids),
            "requested_outputs": list(self.requested_outputs),
        }

@dataclass(frozen=True)
class CalcReqView:
    id: str
    description: str
    metric_ids: tuple[str, ...]
    requested_outputs: tuple[str, ...]

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "metric_ids": list(self.metric_ids),
            "requested_outputs": list(self.requested_outputs),
        }

@dataclass(frozen=True)
class TaskView:
    goal: str
    mode: Any
    deliverable: str
    metric_ids: tuple[str, ...]
    requested_outputs: tuple[str, ...]
    entities: tuple[EntityView, ...]
    season: SeasonView | None
    as_of: Any
    window_start: Any
    window_end: Any
    subject_entity_type: str | None
    subquestions: tuple[str, ...]
    required_evidence: tuple[str, ...]
    requirements: tuple[RequirementView, ...]
    calculation_requirements: tuple[CalcReqView, ...]
    assumptions: tuple[str, ...]
    open_questions: tuple[str, ...]
    skills: tuple[str, ...]
    ranked_argument_conflicts: tuple[Any, ...]

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "mode": self.mode.value if hasattr(self.mode, "value") else self.mode,
            "deliverable": self.deliverable,
            "metric_ids": list(self.metric_ids),
            "requested_outputs": list(self.requested_outputs),
            "entities": [item.model_dump() for item in self.entities],
            "season": self.season.model_dump() if self.season is not None else None,
            "as_of": self.as_of.isoformat() if hasattr(self.as_of, "isoformat") and self.as_of is not None else self.as_of,
            "window_start": self.window_start.isoformat() if hasattr(self.window_start, "isoformat") and self.window_start is not None else self.window_start,
            "window_end": self.window_end.isoformat() if hasattr(self.window_end, "isoformat") and self.window_end is not None else self.window_end,
            "subject_entity_type": self.subject_entity_type,
            "subquestions": list(self.subquestions),
            "required_evidence": list(self.required_evidence),
            "requirements": [item.model_dump() for item in self.requirements],
            "calculation_requirements": [item.model_dump() for item in self.calculation_requirements],
            "assumptions": list(self.assumptions),
            "open_questions": list(self.open_questions),
            "skills": list(self.skills),
            "ranked_argument_conflicts": list(self.ranked_argument_conflicts),
        }

    def model_copy(self, update: Mapping[str, Any] | None = None) -> TaskView:
        raise TypeError("verifier view is read-only: cannot copy task into mutable form")

@dataclass(frozen=True)
class ClaimView:
    text: str
    kind: Any
    evidence_ids: tuple[str, ...]
    calculation_id: str | None
    confidence: float | None
    output_bindings: tuple[Any, ...]

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        return {
            "text": self.text,
            "kind": self.kind.value if hasattr(self.kind, "value") else self.kind,
            "evidence_ids": list(self.evidence_ids),
            "calculation_id": self.calculation_id,
            "confidence": self.confidence,
            "output_bindings": [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in self.output_bindings],
        }

@dataclass(frozen=True)
class DraftView:
    sections: tuple[str, ...]
    claims: tuple[ClaimView, ...]
    calculations: tuple[Any, ...]
    blocked_calculation_requirement_ids: tuple[str, ...]
    gaps: tuple[str, ...]

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        return {
            "sections": list(self.sections),
            "claims": [item.model_dump() for item in self.claims],
            "calculations": [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in self.calculations],
            "blocked_calculation_requirement_ids": list(self.blocked_calculation_requirement_ids),
            "gaps": list(self.gaps),
        }

    def model_copy(self, update: Mapping[str, Any] | None = None) -> DraftView:
        data = self.model_dump()
        if update:
            data.update(dict(update))
        return freeze_draft(DraftReport.model_validate(data))

@dataclass(frozen=True)
class EvidenceView:
    evidence_id: str
    capability: str
    source: str
    observed_at: Any
    season: str | None
    vintages: Any
    task_season_scoped: bool
    as_of: Any
    window_start: Any
    window_end: Any
    entities: tuple[EntityView, ...]
    rows: Any
    units: Any
    metric_definitions: Any
    qualification: str | None
    coverage: str | None
    lineage: tuple[str, ...]
    source_identity: Any
    live_fallback: Any
    warnings: tuple[str, ...]

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        import copy

        def plain(value: Any) -> Any:
            if isinstance(value, FrozenDict):
                return {key: plain(child) for key, child in dict.items(value)}
            if isinstance(value, FrozenList):
                return [plain(child) for child in list(value)]
            if isinstance(value, tuple):
                return [plain(child) for child in value]
            if isinstance(value, EntityView):
                return value.model_dump()
            if hasattr(value, "model_dump"):
                return value.model_dump(mode="json" if mode == "json" else None) if "mode" in getattr(value.model_dump, "__code__", {}).co_varnames else value.model_dump()
            return copy.deepcopy(value)

        return {
            "evidence_id": self.evidence_id,
            "capability": self.capability,
            "source": self.source,
            "observed_at": self.observed_at.isoformat() if hasattr(self.observed_at, "isoformat") else self.observed_at,
            "season": self.season,
            "vintages": plain(self.vintages),
            "task_season_scoped": self.task_season_scoped,
            "as_of": self.as_of.isoformat() if hasattr(self.as_of, "isoformat") and self.as_of is not None else self.as_of,
            "window_start": self.window_start.isoformat() if hasattr(self.window_start, "isoformat") and self.window_start is not None else self.window_start,
            "window_end": self.window_end.isoformat() if hasattr(self.window_end, "isoformat") and self.window_end is not None else self.window_end,
            "entities": [item.model_dump() for item in self.entities],
            "rows": plain(self.rows),
            "units": plain(self.units),
            "metric_definitions": plain(self.metric_definitions),
            "qualification": self.qualification,
            "coverage": self.coverage,
            "lineage": list(self.lineage),
            "source_identity": self.source_identity.model_dump(mode="json") if hasattr(self.source_identity, "model_dump") else self.source_identity,
            "live_fallback": self.live_fallback.model_dump(mode="json") if hasattr(self.live_fallback, "model_dump") else self.live_fallback,
            "warnings": list(self.warnings),
        }

    def model_copy(self, update: Mapping[str, Any] | None = None) -> Any:
        raise TypeError("verifier view is read-only: cannot copy evidence into mutable form")

def freeze_task(task: TaskSpec) -> TaskView:
    entities = tuple(EntityView(type=item.type, id=item.id, display_name=item.display_name) for item in task.entities)
    season = None if task.season is None else SeasonView(value=task.season.value, source=task.season.source, confidence=task.season.confidence)
    requirements = tuple(
        RequirementView(
            id=item.id,
            description=item.description,
            capability_options=tuple(item.capability_options),
            capability_arguments=freeze_value(dict(item.capability_arguments)),
            capability_argument_sets=tuple(item.capability_argument_sets),
            metric_ids=tuple(item.metric_ids),
            requested_outputs=tuple(item.requested_outputs),
        )
        for item in task.requirements
    )
    calc_reqs = tuple(
        CalcReqView(id=item.id, description=item.description, metric_ids=tuple(item.metric_ids), requested_outputs=tuple(item.requested_outputs))
        for item in task.calculation_requirements
    )
    return TaskView(
        goal=task.goal,
        mode=task.mode,
        deliverable=task.deliverable,
        metric_ids=tuple(task.metric_ids),
        requested_outputs=tuple(task.requested_outputs),
        entities=entities,
        season=season,
        as_of=task.as_of,
        window_start=task.window_start,
        window_end=task.window_end,
        subject_entity_type=task.subject_entity_type,
        subquestions=tuple(task.subquestions),
        required_evidence=tuple(task.required_evidence),
        requirements=requirements,
        calculation_requirements=calc_reqs,
        assumptions=tuple(task.assumptions),
        open_questions=tuple(task.open_questions),
        skills=tuple(task.skills),
        ranked_argument_conflicts=tuple(task.ranked_argument_conflicts),
    )

def freeze_claim(claim: Any) -> ClaimView:
    return ClaimView(
        text=claim.text,
        kind=claim.kind,
        evidence_ids=tuple(claim.evidence_ids),
        calculation_id=claim.calculation_id,
        confidence=claim.confidence,
        output_bindings=tuple(claim.output_bindings),
    )

def freeze_draft(draft: DraftReport) -> DraftView:
    return DraftView(
        sections=tuple(draft.sections),
        claims=tuple(freeze_claim(item) for item in draft.claims),
        calculations=tuple(draft.calculations),
        blocked_calculation_requirement_ids=tuple(draft.blocked_calculation_requirement_ids),
        gaps=tuple(draft.gaps),
    )

def freeze_evidence(envelope: EvidenceEnvelope) -> EvidenceView:
    return EvidenceView(
        evidence_id=envelope.evidence_id,
        capability=envelope.capability,
        source=envelope.source,
        observed_at=envelope.observed_at,
        season=envelope.season,
        vintages=freeze_value(dict(envelope.vintages)),
        task_season_scoped=envelope.task_season_scoped,
        as_of=envelope.as_of,
        window_start=envelope.window_start,
        window_end=envelope.window_end,
        entities=tuple(EntityView(type=item.type, id=item.id, display_name=item.display_name) for item in envelope.entities),
        rows=freeze_value(envelope.rows),
        units=freeze_value(dict(envelope.units)),
        metric_definitions=freeze_value(dict(envelope.metric_definitions)),
        qualification=envelope.qualification,
        coverage=envelope.coverage,
        lineage=tuple(envelope.lineage),
        source_identity=envelope.source_identity,
        live_fallback=envelope.live_fallback,
        warnings=tuple(envelope.warnings),
    )

def freeze_evidence_map(evidence: Mapping[str, EvidenceEnvelope]) -> Mapping[str, EvidenceView]:
    return MappingProxyType({key: freeze_evidence(item) for key, item in evidence.items()})

_SELF_VERIFY_FIELDS = frozenset({"status", "claim_results", "verification", "verified", "verified_claims", "supported", "verification_status"})

def reject_self_verified_draft(raw: Any) -> None:
    from v2.contracts import VerificationReport

    if isinstance(raw, VerificationReport):
        raise ValueError("synthesizer cannot mark its own claims verified: returned VerificationReport")
    dump: Any = raw.model_dump() if hasattr(raw, "model_dump") else raw
    if isinstance(dump, dict):
        found = sorted(set(dump) & _SELF_VERIFY_FIELDS)
        if found:
            raise ValueError(f"synthesizer cannot mark its own claims verified: forbidden fields {found}")
        claims = dump.get("claims")
        if isinstance(claims, list):
            for claim in claims:
                if isinstance(claim, dict):
                    inner = sorted(set(claim) & _SELF_VERIFY_FIELDS)
                    if inner:
                        raise ValueError(f"synthesizer cannot mark its own claims verified: claim fields {inner}")

class RepairAddsEvidenceError(ValueError):
    pass

def _cited_evidence_ids(repaired: DraftReport) -> set[str]:
    cited: set[str] = set()
    for claim in repaired.claims:
        cited.update(claim.evidence_ids)
        for binding in claim.output_bindings:
            evidence_id = getattr(binding, "evidence_id", None)
            if evidence_id is not None:
                cited.add(evidence_id)
    for calculation in repaired.calculations:
        for item in calculation.inputs:
            cited.add(item.evidence_id)
    return cited


def _check_binding_selector(binding: Any, by_id: Mapping[str, EvidenceEnvelope]) -> None:
    if getattr(binding, "requirement_kind", None) == "calculation":
        return
    evidence_id = getattr(binding, "evidence_id", None)
    if evidence_id is None:
        return
    envelope = by_id.get(evidence_id)
    if envelope is None:
        return
    selector = getattr(binding, "selector", None)
    if selector is None:
        return
    from v2.runtime.models import AmbiguousSelector, ResolvedSelector, UnresolvedSelector, resolve_selector

    subject_row = getattr(binding, "row_selector", None)
    resolution = resolve_selector(envelope, selector, row=subject_row)
    if isinstance(resolution, UnresolvedSelector):
        raise RepairAddsEvidenceError(f"repair introduced unknown row: {selector} for evidence {evidence_id}")
    if isinstance(resolution, AmbiguousSelector):
        raise RepairAddsEvidenceError(f"repair introduced ambiguous row: {selector} for evidence {evidence_id}")
    if isinstance(resolution, ResolvedSelector):
        declared = getattr(binding, "value", None)
        if declared is not None:
            from v2.runtime.models import _declared_value_matches

            if not _declared_value_matches(declared, resolution.value):
                raise RepairAddsEvidenceError(f"repair introduced unknown value for {selector} on evidence {evidence_id}: {getattr(declared, 'value', declared)!r}")


def validate_repair_evidence_closed(
    admitted: Mapping[str, EvidenceEnvelope],
    repaired: DraftReport,
) -> None:
    admitted_ids = set(admitted)
    extra = sorted(_cited_evidence_ids(repaired) - admitted_ids)
    if extra:
        raise RepairAddsEvidenceError(f"repair introduced unknown evidence ids: {extra}")
    by_id = dict(admitted)
    for claim in repaired.claims:
        for binding in claim.output_bindings:
            _check_binding_selector(binding, by_id)

class Intake(Protocol):
    async def understand(
        self, request: str, context: Sequence[ConversationTurn] = ()
    ) -> TaskSpec: ...

class Planner(Protocol):
    async def plan(
        self, task: TaskSpec, failure_context: dict | None = None
    ) -> Plan: ...

class Capability(Protocol):
    name: str
    task_season_scoped: bool

    def validate_arguments(self, node: PlanNode) -> None: ...

    async def execute(
        self,
        node: PlanNode,
        task: TaskSpec,
        evidence: Sequence[EvidenceEnvelope],
    ) -> EvidenceEnvelope: ...

class Synthesizer(Protocol):
    async def synthesize(
        self, task: TaskSpec, evidence: Sequence[EvidenceEnvelope]
    ) -> DraftReport: ...

class Verifier(Protocol):
    async def verify(
        self,
        task: TaskView,
        draft: DraftView,
        evidence: Mapping[str, EvidenceView],
    ) -> VerificationReport: ...

class Repairer(Protocol):
    async def repair(
        self,
        task: TaskView,
        draft: DraftReport,
        evidence: Mapping[str, EvidenceView],
        verification: VerificationReport,
    ) -> DraftReport: ...

