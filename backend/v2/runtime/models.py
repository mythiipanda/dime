from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from v2.contracts import (
    DraftReport,
    EvidenceEnvelope,
    Plan,
    TaskSpec,
    Gap,
    VerificationReport,
    VerifiedClaim,
    OutputFinalStatus,
    canonical_entity_id,
)

_IDENTITY_KEYS = {
    "player": {"PLAYER_ID", "player_id", "PLAYER", "player",
               "PLAYER_NAME", "player_name", "winner", "coach", "COACH"},
    "team": {"TEAM_ID", "team_id", "TeamID", "TEAM", "team"},
}

_VALUE_TOLERANCE = 1e-9

def _coerce_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        try:
            result = float(value)
        except (ArithmeticError, ValueError):
            return None
        return result if math.isfinite(result) else None
    return None

def _declared_value_matches(declared, selected) -> bool:
    if declared.kind == "boolean":
        return isinstance(selected, bool) and selected is declared.value
    if declared.kind == "string":
        return isinstance(selected, str) and selected == declared.value
    if not isinstance(selected, bool) and selected == declared.value:
        return True
    target = _coerce_number(selected)
    if target is None:
        return False
    try:
        if declared.kind == "decimal":
            wanted = float(Decimal(declared.value))
        else:
            wanted = float(declared.value)
    except (ArithmeticError, ValueError, TypeError):
        return False
    if not math.isfinite(wanted):
        return False
    scale = max(1.0, abs(target), abs(wanted))
    return abs(target - wanted) <= _VALUE_TOLERANCE * scale

_UNIT_WORD_FORMS = {
    "points per game": "per_game",
    "rebounds per game": "per_game",
    "assists per game": "per_game",
    "steals per game": "per_game",
    "blocks per game": "per_game",
    "minutes per game": "minutes",
}

def _canonical_unit(value):
    words = " ".join(str(value).lower().split())
    if words in _UNIT_WORD_FORMS:
        return _UNIT_WORD_FORMS[words]
    return "_".join(words.split())

def _canonical_domain(value):
    return "_".join(str(value).lower().split())

def _row_index(row_selector):
    prefix = "rows["
    if not row_selector.startswith(prefix):
        return None
    rest = row_selector[len(prefix):]
    digits, sep, _ = rest.partition("]")
    if not sep or not digits.isdigit():
        return None
    return int(digits)

@dataclass(frozen=True)
class ResolvedSelector:
    path: str
    value: Any

@dataclass(frozen=True)
class UnresolvedSelector:
    selector: str

@dataclass(frozen=True)
class AmbiguousSelector:
    selector: str
    paths: tuple[str, ...]

SelectorResolution = ResolvedSelector | UnresolvedSelector | AmbiguousSelector

@dataclass(frozen=True)
class _ColumnLeaf:
    path: str
    value: Any
    row: str | None
    position: int | None

def _column_leaves(rows, key):
    def walk(value, path, position, row, row_position, own_key):
        if isinstance(value, Mapping):
            holds = key in value
            for index, (name, child) in enumerate(value.items()):
                yield from walk(child, f"{path}.{name}" if path else str(name),
                                index, path if holds else row,
                                position if holds else row_position, name)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk(child, f"{path}[{index}]", index, row,
                                row_position, own_key)
        elif own_key == key:
            yield _ColumnLeaf(path, value, row, row_position)

    yield from walk(rows, "rows", None, None, None, None)

def _flat_row_field(selector: str) -> tuple[int, str] | None:
    row, sep, key = selector.partition(".")
    if not sep or not key or "." in key or "[" in key:
        return None
    if not row.startswith("rows[") or not row.endswith("]"):
        return None
    digits = row[len("rows["):-1]
    if not digits.isdigit():
        return None
    return int(digits), key

def _row_of(path: str) -> str:
    return path.rsplit(".", 1)[0]

def _inside_row(path: str, row: str) -> bool:
    return (path == row or path.startswith(row + ".")
            or path.startswith(row + "["))

def _selects_within_row(selector: str, root: str) -> bool:
    return selector.startswith(root + ".") or selector.startswith(root + "[")

def resolve_selector(
    envelope: EvidenceEnvelope,
    selector: str,
    *,
    row: str | None = None,
    preferred: Callable[[Any], bool] | None = None,
) -> SelectorResolution:
    from v2.domain.evidence import iter_values

    literal = [item for item in iter_values(envelope) if item.path == selector]
    if len(literal) > 1:
        return AmbiguousSelector(selector, tuple(item.path for item in literal))
    if literal:
        return ResolvedSelector(literal[0].path, literal[0].value)
    flat = _flat_row_field(selector)
    if flat is None:
        return UnresolvedSelector(selector)
    index, key = flat
    leaves = [leaf for leaf in _column_leaves(envelope.rows, key)
              if row is None or leaf.row == row]
    if not leaves:
        return UnresolvedSelector(selector)
    if preferred is not None:
        declared = [leaf for leaf in leaves if preferred(leaf.value)]
        if not declared:
            return UnresolvedSelector(selector)
        leaves = declared
    positional = [leaf for leaf in leaves if leaf.position == index]
    leaves = positional or leaves
    if len(leaves) == 1:
        return ResolvedSelector(leaves[0].path, leaves[0].value)
    return AmbiguousSelector(selector, tuple(leaf.path for leaf in leaves))

def resolve_subject_row(
    envelope: EvidenceEnvelope, binding, identity: str) -> str | None:
    def names_subject(value) -> bool:
        return canonical_entity_id(
            binding.subject_entity_type, str(value)) == identity

    resolution = resolve_selector(
        envelope, binding.subject_selector, preferred=names_subject)
    if not isinstance(resolution, ResolvedSelector) \
            or not names_subject(resolution.value):
        return None
    return _row_of(resolution.path)

def resolve_evidence_binding(
    envelope: EvidenceEnvelope, binding, subject_row: str | None) -> SelectorResolution:
    resolution = resolve_selector(
        envelope, binding.selector, row=subject_row,
        preferred=lambda value: _declared_value_matches(binding.value, value))
    if isinstance(resolution, ResolvedSelector) and subject_row is not None \
            and not _inside_row(resolution.path, subject_row):
        return UnresolvedSelector(binding.selector)
    return resolution

def _reanchor_binding(binding, evidence):
    from v2.contracts import EvidenceOutputBinding, canonical_entity_id
    if not isinstance(binding, EvidenceOutputBinding):
        return None
    if evidence is None:
        return None
    if (binding.row_selector is None or binding.subject_selector is None
            or binding.subject_entity_id is None
            or binding.subject_entity_type is None):
        return None
    if not isinstance(evidence.rows, list):
        return None
    row_root = binding.row_selector
    claimed = _row_index(row_root)
    if claimed is None:
        return None
    identity_keys = _IDENTITY_KEYS.get(binding.subject_entity_type)
    if identity_keys is None:
        return None
    if binding.subject_selector != f"{row_root}." + binding.subject_selector.rsplit(".", 1)[-1]:
        return None
    leaf = binding.subject_selector.rsplit(".", 1)[-1]
    if leaf not in identity_keys:
        return None
    if not (binding.selector.startswith(row_root + ".")
            or binding.selector.startswith(row_root + "[")):
        return None
    subject = canonical_entity_id(
        binding.subject_entity_type, binding.subject_entity_id)
    match = None
    for index, row in enumerate(evidence.rows):
        if not isinstance(row, dict):
            continue
        if leaf not in row or row[leaf] is None:
            continue
        if canonical_entity_id(
                binding.subject_entity_type, str(row[leaf])) == subject:
            match = index
            break
    if match is None or match == claimed:
        return None
    new_root = f"rows[{match}]"
    new_selector = new_root + binding.selector[len(row_root):]
    new_subject_selector = f"{new_root}.{leaf}"
    resolution = resolve_selector(evidence, new_selector)
    if not isinstance(resolution, ResolvedSelector) or resolution.value is None:
        return None
    if not _declared_value_matches(binding.value, resolution.value):
        return None
    return binding.model_copy(update={
        "selector": new_selector,
        "row_selector": new_root,
        "subject_selector": new_subject_selector,
    })

def reanchor_verified_claim_bindings(execution, verified_claim):
    evidence_by_id = {item.evidence_id: item for item in execution.evidence}
    fixed = []
    changed = False
    for binding in verified_claim.output_bindings:
        candidate = _reanchor_binding(
            binding, evidence_by_id.get(binding.evidence_id)
            if hasattr(binding, "evidence_id") else None)
        if candidate is not None:
            fixed.append(candidate)
            changed = True
        else:
            fixed.append(binding)
    if not changed:
        return verified_claim
    return verified_claim.model_copy(update={"output_bindings": fixed})

class ExecutionErrorCode(StrEnum):
    PROFILE_NAME_RESOLUTION_UNAVAILABLE = "profile/name_resolution_unavailable"

class ExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: Plan
    evidence_by_node: dict[str, EvidenceEnvelope] = Field(default_factory=dict, max_length=32)

    @property
    def evidence(self) -> list[EvidenceEnvelope]:
        return list(self.evidence_by_node.values())
    attempts: dict[str, StrictInt] = Field(default_factory=dict, max_length=32)
    errors: dict[str, list[str]] = Field(default_factory=dict, max_length=32)
    error_codes: dict[str, list[ExecutionErrorCode]] = Field(
        default_factory=dict, max_length=32)

    @model_validator(mode="after")
    def validate_execution(self) -> "ExecutionResult":
        _check_execution_node_references(self)
        _check_execution_evidence(self)
        _check_execution_attempts(self)
        _check_execution_error_codes(self)
        for node in self.plan.nodes:
            _check_execution_node(self, node)
        return self


def _check_execution_node_references(result: "ExecutionResult") -> None:
    node_ids = {node.id for node in result.plan.nodes}
    unknown = (set(result.attempts) | set(result.errors)
               | set(result.error_codes)) - node_ids
    if unknown:
        raise ValueError(f"execution references unknown nodes: {sorted(unknown)}")
    unknown_evidence_nodes = set(result.evidence_by_node) - node_ids
    if unknown_evidence_nodes:
        raise ValueError(
            f"execution evidence has unknown owners: {sorted(unknown_evidence_nodes)}")


def _check_execution_evidence(result: "ExecutionResult") -> None:
    nodes = {node.id: node for node in result.plan.nodes}
    evidence_ids = [item.evidence_id for item in result.evidence_by_node.values()]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("execution evidence ids must be unique")
    for node_id, item in result.evidence_by_node.items():
        node = nodes[node_id]
        if node.status.value != "complete":
            raise ValueError("execution evidence owner must be complete")
        if item.capability not in node.capability_hints:
            raise ValueError(
                f"execution evidence capability does not match node {node.id!r}")
        expected_lineage = [
            result.evidence_by_node[parent].evidence_id
            for parent in node.depends_on
            if parent in result.evidence_by_node
        ]
        if item.lineage != expected_lineage:
            raise ValueError(
                f"execution evidence lineage does not match node {node.id!r}")


def _check_execution_attempts(result: "ExecutionResult") -> None:
    if any(isinstance(count, bool) or not isinstance(count, int)
           for count in result.attempts.values()):
        raise ValueError("execution attempt counts must be integers")
    if any(count < 0 for count in result.attempts.values()):
        raise ValueError("execution attempt counts must be non-negative")


def _check_execution_error_codes(result: "ExecutionResult") -> None:
    for node_id, codes in result.error_codes.items():
        if len(codes) != len(set(codes)):
            raise ValueError(f"execution node {node_id!r} has duplicate error codes")
        if node_id not in result.errors:
            raise ValueError(f"execution error codes require node errors for {node_id!r}")


def _check_execution_node(result: "ExecutionResult", node) -> None:
    count = result.attempts.get(node.id, 0)
    status = node.status.value
    if count > node.max_attempts:
        raise ValueError(
            f"execution attempts exceed max_attempts for node {node.id!r}")
    if status in {"complete", "failed"} and count == 0:
        raise ValueError(
            f"execution node {node.id!r} reached terminal state without an attempt")
    _check_execution_node_errors(node, result.errors.get(node.id, []))
    if status == "failed" and not result.errors.get(node.id, []):
        raise ValueError(f"failed node {node.id!r} requires errors")
    if status == "failed" and count != node.max_attempts:
        raise ValueError(f"failed node {node.id!r} must exhaust its attempt budget")
    if status in {"pending", "running"} and count >= node.max_attempts:
        raise ValueError(f"execution node {node.id!r} has no attempts remaining")
    if status == "skipped" and result.errors.get(node.id, []):
        raise ValueError(f"skipped node {node.id!r} cannot carry errors")
    if status == "skipped" and count:
        raise ValueError(f"skipped node {node.id!r} cannot carry attempts")


def _check_execution_node_errors(node, node_errors) -> None:
    if len(node_errors) > 5:
        raise ValueError(f"execution node {node.id!r} has too many errors")
    if any(not error.strip() for error in node_errors):
        raise ValueError(f"execution node {node.id!r} has empty errors")
    if any(len(error) > 4000 for error in node_errors):
        raise ValueError(f"execution node {node.id!r} has oversized errors")
    if len(node_errors) != len(set(node_errors)):
        raise ValueError(f"execution node {node.id!r} has duplicate errors")

class RuntimeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: TaskSpec
    execution: ExecutionResult
    draft: DraftReport
    verification: VerificationReport
    repaired: StrictBool = False
    structural_flags: list[str] = Field(default_factory=list, max_length=32)
    verified_claims: list[VerifiedClaim] = Field(default_factory=list, max_length=128)
    gaps: list[Gap] = Field(default_factory=list, max_length=256)
    output_statuses: list[OutputFinalStatus] = Field(default_factory=list, max_length=256)
    binding_diagnostics: list[dict[str, Any]] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def validate_publication(self) -> "RuntimeResult":
        _check_structural_flags(self.structural_flags)
        by_index = {item.claim_index: item for item in self.verification.claim_results}
        _check_claim_indices(by_index, len(self.draft.claims))
        evidence = {item.evidence_id: item for item in self.execution.evidence}
        _check_evidence_season(self.task, evidence)
        seen = _check_publication_gaps(self)
        _check_verified_claims(self, by_index, evidence, seen)
        supported = {index for index, result in by_index.items()
                     if result.supported and not result.uncertain}
        if seen != supported:
            raise ValueError("verified claims must match supported adjudications")
        expected_status = (
            "partial" if self.gaps or len(supported) != len(self.draft.claims)
            else "pass"
        )
        if self.verification.status.value != expected_status:
            raise ValueError(
                "verification status does not match runtime publication state")
        computed = build_output_statuses(self.task, self.verified_claims, self.gaps)
        if self.output_statuses and self.output_statuses != computed:
            raise ValueError("stored output status matrix does not match authority")
        self.output_statuses = computed
        return self


def _check_structural_flags(structural_flags) -> None:
    if any(not flag.strip() for flag in structural_flags):
        raise ValueError("runtime structural flags must not be empty")
    if len(structural_flags) != len(set(structural_flags)):
        raise ValueError("runtime structural flags must not contain duplicates")


def _check_claim_indices(by_index, claim_count) -> None:
    invalid_indices = [index for index in by_index if index >= claim_count]
    if invalid_indices:
        raise ValueError(
            f"verification claim indices are outside the draft: {invalid_indices}")


def _check_evidence_season(task, evidence) -> None:
    if task.season is None:
        return
    wrong_season = [
        item.evidence_id for item in evidence.values()
        if item.task_season_scoped
        and item.season != task.season.value
    ]
    if wrong_season:
        raise ValueError(f"runtime evidence does not match task season: {wrong_season}")


def _check_gap_block(result, gap, block) -> None:
    if block.startswith("claim:"):
        suffix = block.removeprefix("claim:")
        if not suffix.isdigit() or int(suffix) >= len(result.draft.claims):
            raise ValueError(f"gap blocks unknown claim: {block}")
    elif block.startswith("node:"):
        if block.removeprefix("node:") not in {
            node.id for node in result.execution.plan.nodes
        }:
            raise ValueError(f"gap blocks unknown node: {block}")
    elif block.startswith("requirement:"):
        if block.removeprefix("requirement:") not in {
            item.id for item in result.task.requirements
        }:
            raise ValueError(f"gap blocks unknown requirement: {block}")


def _check_publication_gaps(result) -> set[int]:
    evidence_ids = {item.evidence_id for item in result.execution.evidence}
    seen_gaps: set[tuple] = set()
    for gap in result.gaps:
        identity = (gap.kind, gap.message, tuple(gap.evidence_ids), tuple(gap.blocks))
        if identity in seen_gaps:
            raise ValueError("runtime gaps must not contain duplicates")
        seen_gaps.add(identity)
        unknown = set(gap.evidence_ids) - evidence_ids
        if unknown:
            raise ValueError(f"gap cites unknown evidence ids: {sorted(unknown)}")
        for block in gap.blocks:
            _check_gap_block(result, gap, block)
    return set()


def _check_verified_claim(result, item, by_index, evidence, seen) -> None:
    evidence_ids = set(evidence)
    if item.claim_index in seen:
        raise ValueError("verified claim indices must be unique")
    seen.add(item.claim_index)
    if item.claim_index >= len(result.draft.claims):
        raise ValueError("verified claim index is outside the draft")
    if item.claim != result.draft.claims[item.claim_index]:
        raise ValueError("verified claim does not match the draft")
    adjudication = by_index.get(item.claim_index)
    if adjudication is None or not adjudication.supported or adjudication.uncertain:
        raise ValueError("verified claim lacks supported adjudication")
    if item.evidence_ids != item.claim.evidence_ids:
        raise ValueError("verified claim evidence does not match its claim")
    unknown_claim_evidence = set(item.evidence_ids) - evidence_ids
    if unknown_claim_evidence:
        raise ValueError(
            "verified claim cites unknown execution evidence ids: "
            f"{sorted(unknown_claim_evidence)}"
        )
    expected_sources = [
        (evidence_id, evidence[evidence_id].source,
         evidence[evidence_id].capability)
        for evidence_id in item.evidence_ids
        if evidence_id in evidence
    ]
    actual_sources = [
        (source.evidence_id, source.source, source.capability)
        for source in item.sources
    ]
    if actual_sources != expected_sources:
        raise ValueError("verified claim sources do not match execution evidence")
    try:
        admit_verified_claim_bindings(
            result.task, result.execution, result.draft, item)
    except ValueError as exc:
        raise ValueError(
            f"verified claim carries invalid output authority: {exc}") from exc


def _check_verified_claims(result, by_index, evidence, seen) -> None:
    for item in result.verified_claims:
        _check_verified_claim(result, item, by_index, evidence, seen)

def withheld_claim_indices(gaps) -> set[int]:
    return {
        int(block.removeprefix("claim:"))
        for gap in gaps
        if gap.kind.value == "synthesis_incomplete"
        for block in gap.blocks
        if block.startswith("claim:") and block.removeprefix("claim:").isdigit()
    }

def build_output_statuses(task, verified_claims, gaps):
    from v2.contracts import OutputFinalStatus
    admitted = {}
    rejected = set()
    withheld = withheld_claim_indices(gaps)
    for claim in verified_claims:
        if claim.claim_index in withheld:
            rejected.update((binding.requirement_kind, binding.requirement_id,
                             binding.output_id)
                            for binding in claim.claim.output_bindings)
        for binding in claim.output_bindings:
            key = (binding.requirement_kind, binding.requirement_id,
                   binding.output_id)
            if key in admitted:
                raise ValueError("multiple claims own one requested output")
            admitted[key] = (claim.claim_index, binding)
    requested = [
        *(('task', None, output) for output in task.requested_outputs),
        *(('evidence', req.id, output) for req in task.requirements
          for output in req.requested_outputs),
        *(('calculation', req.id, output) for req in task.calculation_requirements
          for output in req.requested_outputs),
    ]
    if len(requested) != len(set(requested)):
        raise ValueError("requested output identities must be unique")
    rows = []
    for kind, requirement_id, output_id in requested:
        key = (kind, requirement_id, output_id)
        owned = admitted.get(key)
        rows.append(OutputFinalStatus(
            requirement_kind=kind, requirement_id=requirement_id,
            output_id=output_id,
            status=("complete" if owned else
                    "rejected" if key in rejected else "missing"),
            claim_index=owned[0] if owned else None,
            binding=owned[1] if owned else None))
    return rows

class _EvidencePropagation:
    def __init__(self, task, execution, draft, admitted) -> None:
        from v2.contracts import canonical_entity_ref
        self.task = task
        self.execution = execution
        self.draft = draft
        self.admitted = admitted
        self.task_entities = {canonical_entity_ref(item) for item in task.entities}
        self.league_scoped = bool(self.task_entities) and all(
            kind == "league" for kind, _ in self.task_entities)
        self.owner_by_evidence_id = {
            envelope.evidence_id: envelope for envelope in execution.evidence}
        self.owned = {(binding.requirement_kind, binding.requirement_id,
                       binding.output_id)
                      for claim in admitted for binding in claim.output_bindings}
        self.accepted: dict[int, list] = {}

    def _binding_envelope(self, binding):
        envelope = self.owner_by_evidence_id.get(binding.evidence_id)
        if envelope is None:
            envelope = self.execution.evidence_by_node.get(binding.node_id)
        if envelope is None:
            raise ValueError("propagation could not resolve binding evidence")
        return envelope

    def _subject_admissible(self, binding, subject) -> bool:
        from v2.contracts import canonical_entity_ref
        if subject in self.task_entities:
            return True
        if not self.task_entities or self.league_scoped:
            envelope_entities = {
                canonical_entity_ref(item)
                for item in self._binding_envelope(binding).entities
            }
            return subject in envelope_entities
        return False

    def _collect_candidates(self) -> dict[str, list]:
        from v2.contracts import EvidenceOutputBinding, canonical_entity_id
        candidates: dict[str, list] = {}
        for claim in self.admitted:
            for binding in claim.output_bindings:
                if not isinstance(binding, EvidenceOutputBinding):
                    continue
                if binding.requirement_kind != "evidence":
                    continue
                if binding.output_id not in self.task.requested_outputs:
                    continue
                if binding.subject_entity_type is None \
                        or binding.subject_entity_id is None:
                    continue
                subject = (binding.subject_entity_type, canonical_entity_id(
                    binding.subject_entity_type, binding.subject_entity_id))
                if not self._subject_admissible(binding, subject):
                    continue
                candidates.setdefault(binding.output_id, []).append((claim, binding))
        return candidates

    def admit_alias(self, claim, binding, update, key) -> None:
        if key in self.owned:
            return
        clone = binding.model_copy(update=update)
        trial = claim.model_copy(update={
            "output_bindings": [*claim.output_bindings, clone]})
        try:
            admit_verified_claim_bindings(self.task, self.execution, self.draft, trial)
        except ValueError:
            return
        self.accepted.setdefault(claim.claim_index, []).append(clone)
        self.owned.add(key)

    def _admit_task_level_aliases(self, candidates) -> None:
        for output_id, competing in candidates.items():
            if len(competing) != 1:
                continue
            claim, binding = competing[0]
            self.admit_alias(claim, binding,
                             {"requirement_kind": "task", "requirement_id": None},
                             ("task", None, output_id))

    def _admit_requirement_level_aliases(self) -> None:
        from v2.contracts import EvidenceOutputBinding
        for claim in self.admitted:
            for binding in [
                    *claim.output_bindings,
                    *self.accepted.get(claim.claim_index, [])]:
                if not isinstance(binding, EvidenceOutputBinding):
                    continue
                if binding.requirement_kind != "task":
                    continue
                for requirement in self.task.requirements:
                    if binding.output_id not in requirement.requested_outputs:
                        continue
                    self.admit_alias(
                        claim, binding,
                        {"requirement_kind": "evidence",
                         "requirement_id": requirement.id},
                        ("evidence", requirement.id, binding.output_id))

    def run(self):
        self._admit_task_level_aliases(self._collect_candidates())
        self._admit_requirement_level_aliases()
        if not self.accepted:
            return list(self.admitted)
        return [claim.model_copy(update={"output_bindings": [
            *claim.output_bindings, *self.accepted.get(claim.claim_index, [])]})
            if claim.claim_index in self.accepted else claim
            for claim in self.admitted]


def propagate_evidence_to_task(task, execution, draft, admitted):
    return _EvidencePropagation(task, execution, draft, admitted).run()

class BindingFormMismatch(ValueError):
    pass

class _BindingAdmission:
    def __init__(
        self,
        task: TaskSpec,
        execution: ExecutionResult,
        draft: DraftReport,
        verified_claim: VerifiedClaim,
    ) -> None:
        from v2.contracts import canonical_entity_ref
        self.task = task
        self.execution = execution
        self.claim = reanchor_verified_claim_bindings(execution, verified_claim)
        self.evidence_requirements = {item.id: item for item in task.requirements}
        self.calculation_requirements = {
            item.id: item for item in task.calculation_requirements}
        self.evidence_by_id = {item.evidence_id: (node_id, item)
                               for node_id, item in execution.evidence_by_node.items()}
        self.calculations = {item.calculation_id: item for item in draft.calculations}
        self.task_entities = {canonical_entity_ref(item) for item in task.entities}
        self.league_scoped = bool(self.task_entities) and all(
            kind == "league" for kind, _ in self.task_entities)

    def run(self) -> VerifiedClaim:
        from v2.contracts import EvidenceOutputBinding
        self.claim = self._remap_evidence_ids()
        for binding in self.claim.output_bindings:
            if isinstance(binding, EvidenceOutputBinding):
                self._admit_evidence_binding(binding)
            else:
                self._admit_calculation_binding(binding)
        return self.claim

    def _fallback_evidence_id(self, binding) -> str | None:
        if binding.evidence_id in self.evidence_by_id:
            return None
        if not ((binding.requirement_kind == "task"
                 and binding.requirement_id is None)
                or binding.requirement_kind == "evidence"):
            return None
        envelope = self.execution.evidence_by_node.get(binding.node_id)
        return None if envelope is None else envelope.evidence_id

    def _collect_fallback_map(self) -> dict[str, str]:
        from v2.contracts import EvidenceOutputBinding
        fallback_map: dict[str, str] = {}
        for binding in self.claim.output_bindings:
            if not isinstance(binding, EvidenceOutputBinding):
                continue
            real_id = self._fallback_evidence_id(binding)
            if real_id is None or binding.evidence_id == real_id:
                continue
            previous = fallback_map.get(binding.evidence_id)
            if previous is not None and previous != real_id:
                raise ValueError("binding evidence ownership is invalid")
            fallback_map[binding.evidence_id] = real_id
        return fallback_map

    def _remap_evidence_ids(self) -> VerifiedClaim:
        from v2.contracts import EvidenceOutputBinding
        fallback_map = self._collect_fallback_map()
        if not fallback_map:
            return self.claim
        fixed_bindings = [
            item.model_copy(update={"evidence_id": fallback_map[item.evidence_id]})
            if isinstance(item, EvidenceOutputBinding) and item.evidence_id in fallback_map
            else item
            for item in self.claim.output_bindings
        ]
        remapped_ids: list[str] = []
        for evidence_id in self.claim.evidence_ids:
            mapped = fallback_map.get(evidence_id, evidence_id)
            if mapped not in remapped_ids:
                remapped_ids.append(mapped)
        remapped_sources = []
        seen_source_ids: set[str] = set()
        for source in self.claim.sources:
            mapped = fallback_map.get(source.evidence_id, source.evidence_id)
            if mapped in seen_source_ids:
                continue
            seen_source_ids.add(mapped)
            remapped_sources.append(
                source.model_copy(update={"evidence_id": mapped})
                if mapped != source.evidence_id else source
            )
        return self.claim.model_copy(update={
            "output_bindings": fixed_bindings,
            "evidence_ids": remapped_ids,
            "sources": remapped_sources,
        })

    def _evidence_owner(self, binding):
        owned = self.evidence_by_id.get(binding.evidence_id)
        if owned is not None:
            return owned
        if not ((binding.requirement_kind == "task"
                 and binding.requirement_id is None)
                or binding.requirement_kind == "evidence"):
            return None
        envelope = self.execution.evidence_by_node.get(binding.node_id)
        if envelope is None:
            return None
        return (binding.node_id, envelope)

    def _requirement_arguments(self, requirement, evidence):
        if not requirement.capability_argument_sets:
            return requirement.capability_arguments
        return dict(next(item.arguments for item in requirement.capability_argument_sets
                         if item.capability_id == evidence.capability))

    def _check_requirement_scope(self, binding, node, evidence, requirement) -> None:
        if binding.requirement_id not in node.covers_requirement_ids:
            raise ValueError("binding node does not cover requirement")
        if evidence.capability not in requirement.capability_options:
            raise ValueError("binding capability is outside requirement")
        if any(node.arguments.get(key) != value for key, value
               in self._requirement_arguments(requirement, evidence).items()):
            raise ValueError("binding node scope does not match requirement")

    def _check_metric_binding(self, binding, capability, evidence) -> None:
        from v2.adapters.capabilities import resolve_metric_column
        leaf = binding.selector.rsplit(".", 1)[-1].split("[", 1)[0]
        if leaf == binding.output_id:
            metric_column = leaf
        else:
            resolved = resolve_metric_column(capability, binding.output_id)
            if resolved is None or resolved != leaf:
                raise BindingFormMismatch("binding selector metric does not match output")
            metric_column = resolved
        catalog_unit = (None if capability.open_vocabulary
                        else capability.units.get(metric_column))
        evidence_unit = evidence.units.get(metric_column)
        if catalog_unit is not None and evidence_unit is not None \
                and catalog_unit != evidence_unit:
            raise ValueError("catalog and evidence units disagree")
        authoritative_unit = evidence_unit or catalog_unit
        if authoritative_unit is None:
            if binding.unit.kind != "unitless":
                raise ValueError("unitless output must be explicit")
        elif binding.unit.kind != "declared" \
                or _canonical_unit(binding.unit.value) != _canonical_unit(
                    authoritative_unit):
            raise ValueError("binding unit does not match output authority")

    def _check_domain(self, binding, capability) -> None:
        if _canonical_domain(binding.domain) not in {
                _canonical_domain(capability.domain),
                _canonical_domain(capability.name),
                _canonical_domain(capability.tool_name),
        }:
            raise ValueError("binding domain does not match capability")

    def _check_task_scope(self, evidence) -> None:
        if self.task.season is not None and evidence.task_season_scoped \
                and evidence.season != self.task.season.value:
            raise ValueError("binding evidence season is outside task scope")
        if self.task.as_of is not None and evidence.as_of != self.task.as_of:
            raise ValueError("binding evidence as_of is outside task scope")

    def _check_subject_scope(self, evidence, subject) -> None:
        from v2.contracts import canonical_entity_ref
        scoped = self.task_entities
        if subject not in scoped and not (
                (self.league_scoped or not scoped)
                and any(canonical_entity_ref(item) == subject for item in evidence.entities)):
            raise ValueError("binding subject is outside requested scope")
        if evidence.entities and not any(
                canonical_entity_ref(entity) == subject
                for entity in evidence.entities):
            raise ValueError("binding subject is outside evidence scope")

    def _check_subject_selector(self, binding) -> str:
        identity_keys = _IDENTITY_KEYS.get(binding.subject_entity_type)
        if identity_keys is None:
            raise ValueError("binding subject type lacks identity authority")
        subject_leaf = binding.subject_selector.rsplit(".", 1)[-1]
        if subject_leaf not in identity_keys:
            raise ValueError("binding subject selector has wrong entity type")
        row_root = binding.row_selector
        if binding.subject_selector != f"{row_root}.{subject_leaf}":
            raise ValueError("binding subject must be a direct row child")
        if row_root is None:
            raise ValueError("entity binding requires explicit row selector")
        return row_root

    def _subject_row(self, binding, evidence) -> str | None:
        from v2.contracts import canonical_entity_id
        if self.task_entities and binding.subject_entity_id is None:
            raise ValueError("entity-scoped binding requires selector-local subject")
        if binding.subject_entity_id is None:
            return None
        subject = (binding.subject_entity_type, canonical_entity_id(
            binding.subject_entity_type, binding.subject_entity_id))
        self._check_subject_scope(evidence, subject)
        row_root = self._check_subject_selector(binding)
        if not _selects_within_row(binding.selector, row_root) \
                or not _selects_within_row(binding.subject_selector, row_root):
            raise ValueError("binding selectors are outside declared row")
        subject_row = resolve_subject_row(evidence, binding, subject[1])
        if subject_row is None:
            raise ValueError("binding selector row does not match subject")
        return subject_row

    def _check_selector(self, binding, evidence, subject_row) -> None:
        resolution = resolve_evidence_binding(evidence, binding, subject_row)
        if isinstance(resolution, AmbiguousSelector):
            raise ValueError(
                f"binding selector names {len(resolution.paths)} values")
        if not isinstance(resolution, ResolvedSelector) or resolution.value is None:
            raise ValueError("binding selector must locate exactly one value")
        if not _declared_value_matches(binding.value, resolution.value):
            raise ValueError("binding value does not exactly match selected evidence")
        if binding.evidence_id not in self.claim.evidence_ids:
            raise ValueError("binding evidence is not cited by claim")

    def _admit_evidence_binding(self, binding) -> None:
        from v2.adapters.capabilities import CAPABILITIES
        requirement = (self.evidence_requirements.get(binding.requirement_id)
                       if binding.requirement_kind == "evidence" else None)
        if binding.requirement_kind == "evidence" and requirement is None:
            raise ValueError("binding names unknown evidence requirement")
        allowed_outputs = (requirement.requested_outputs if requirement is not None
                           else self.task.requested_outputs)
        if binding.output_id not in allowed_outputs:
            raise ValueError("binding output is outside its authority")
        owned = self._evidence_owner(binding)
        if owned is None:
            raise ValueError("binding evidence ownership is invalid")
        node = next(item for item in self.execution.plan.nodes if item.id == owned[0])
        evidence = owned[1]
        if requirement is not None:
            self._check_requirement_scope(binding, node, evidence, requirement)
        capability = CAPABILITIES.get(evidence.capability)
        if capability is None:
            raise ValueError("binding capability lacks catalog authority")
        if capability.units or capability.metric_definitions \
                or capability.output_aliases:
            self._check_metric_binding(binding, capability, evidence)
        self._check_domain(binding, capability)
        self._check_task_scope(evidence)
        self._check_selector(binding, evidence, self._subject_row(binding, evidence))

    def _calculation_recomputation_error(self, calculation):
        from v2.domain.calculations import Calculation, validate_calculation
        from v2.domain.evidence import EvidenceIndex
        checked = Calculation.model_validate({
            "calculation_id": calculation.calculation_id,
            "operation": calculation.operation,
            "inputs": [item.model_dump() for item in calculation.inputs],
            "result": calculation.result, "unit": calculation.unit,
            "subject_input": calculation.subject_input})
        return validate_calculation(checked, EvidenceIndex(self.execution.evidence))

    def _check_calculation_unit(self, calculation) -> None:
        unit_text = (calculation.unit or "").strip().casefold()
        if str(calculation.operation) in ("rank_desc", "rank_asc"):
            if unit_text not in ("", "rank", "unitless"):
                raise ValueError("rank calculation unit must be rank or unitless")
        elif unit_text == "rank":
            raise ValueError("non-rank calculation cannot carry rank unit")

    def _admit_calculation_binding(self, binding) -> None:
        requirement = self.calculation_requirements.get(binding.requirement_id)
        if requirement is None or binding.output_id not in requirement.requested_outputs:
            raise ValueError("binding calculation output is outside requirement")
        calculation = self.calculations.get(binding.calculation_id)
        if calculation is None or calculation.requirement_id != binding.requirement_id:
            raise ValueError("binding calculation authority is invalid")
        if self.claim.claim.calculation_id != binding.calculation_id:
            raise ValueError("binding calculation is not cited by claim")
        if self._calculation_recomputation_error(calculation) is not None:
            raise ValueError("binding calculation did not pass recomputation")
        self._check_calculation_unit(calculation)


def admit_verified_claim_bindings(
    task: TaskSpec,
    execution: ExecutionResult,
    draft: DraftReport,
    verified_claim: VerifiedClaim,
) -> VerifiedClaim:
    return _BindingAdmission(task, execution, draft, verified_claim).run()
