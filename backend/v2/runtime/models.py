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
        nodes = {node.id: node for node in self.plan.nodes}
        unknown = (set(self.attempts) | set(self.errors) | set(self.error_codes)) - nodes.keys()
        if unknown:
            raise ValueError(f"execution references unknown nodes: {sorted(unknown)}")
        unknown_evidence_nodes = set(self.evidence_by_node) - nodes.keys()
        if unknown_evidence_nodes:
            raise ValueError(
                f"execution evidence has unknown owners: {sorted(unknown_evidence_nodes)}")
        evidence_ids = [item.evidence_id for item in self.evidence_by_node.values()]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("execution evidence ids must be unique")
        for node_id, item in self.evidence_by_node.items():
            node = nodes[node_id]
            if node.status.value != "complete":
                raise ValueError("execution evidence owner must be complete")
            if item.capability not in node.capability_hints:
                raise ValueError(
                    f"execution evidence capability does not match node {node.id!r}")
            expected_lineage = [
                self.evidence_by_node[parent].evidence_id
                for parent in node.depends_on
                if parent in self.evidence_by_node
            ]
            if item.lineage != expected_lineage:
                raise ValueError(
                    f"execution evidence lineage does not match node {node.id!r}")
        if any(isinstance(count, bool) or not isinstance(count, int)
               for count in self.attempts.values()):
            raise ValueError("execution attempt counts must be integers")
        if any(count < 0 for count in self.attempts.values()):
            raise ValueError("execution attempt counts must be non-negative")
        for node_id, codes in self.error_codes.items():
            if len(codes) != len(set(codes)):
                raise ValueError(f"execution node {node_id!r} has duplicate error codes")
            if node_id not in self.errors:
                raise ValueError(f"execution error codes require node errors for {node_id!r}")
        for node in self.plan.nodes:
            count = self.attempts.get(node.id, 0)
            if count > node.max_attempts:
                raise ValueError(
                    f"execution attempts exceed max_attempts for node {node.id!r}")
            if node.status.value in {"complete", "failed"} and count == 0:
                raise ValueError(
                    f"execution node {node.id!r} reached terminal state without an attempt")
            node_errors = self.errors.get(node.id, [])
            if len(node_errors) > 5:
                raise ValueError(f"execution node {node.id!r} has too many errors")
            if any(not error.strip() for error in node_errors):
                raise ValueError(f"execution node {node.id!r} has empty errors")
            if any(len(error) > 4000 for error in node_errors):
                raise ValueError(f"execution node {node.id!r} has oversized errors")
            if len(node_errors) != len(set(node_errors)):
                raise ValueError(f"execution node {node.id!r} has duplicate errors")
            if node.status.value == "failed" and not node_errors:
                raise ValueError(f"failed node {node.id!r} requires errors")
            if node.status.value == "failed" and count != node.max_attempts:
                raise ValueError(
                    f"failed node {node.id!r} must exhaust its attempt budget")
            if node.status.value in {"pending", "running"} and count >= node.max_attempts:
                raise ValueError(
                    f"execution node {node.id!r} has no attempts remaining")
            if node.status.value == "skipped" and node_errors:
                raise ValueError(f"skipped node {node.id!r} cannot carry errors")
            if node.status.value == "skipped" and count:
                raise ValueError(f"skipped node {node.id!r} cannot carry attempts")
        return self

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
        if any(not flag.strip() for flag in self.structural_flags):
            raise ValueError("runtime structural flags must not be empty")
        if len(self.structural_flags) != len(set(self.structural_flags)):
            raise ValueError("runtime structural flags must not contain duplicates")
        by_index = {item.claim_index: item for item in self.verification.claim_results}
        invalid_indices = [
            index for index in by_index if index >= len(self.draft.claims)
        ]
        if invalid_indices:
            raise ValueError(
                f"verification claim indices are outside the draft: {invalid_indices}")
        evidence = {item.evidence_id: item for item in self.execution.evidence}
        if self.task.season is not None:
            wrong_season = [
                item.evidence_id for item in evidence.values()
                if item.task_season_scoped
                and item.season != self.task.season.value
            ]
            if wrong_season:
                raise ValueError(
                    f"runtime evidence does not match task season: {wrong_season}")
        seen: set[int] = set()
        evidence_ids = set(evidence)
        seen_gaps: set[tuple] = set()
        for gap in self.gaps:
            identity = (gap.kind, gap.message, tuple(gap.evidence_ids), tuple(gap.blocks))
            if identity in seen_gaps:
                raise ValueError("runtime gaps must not contain duplicates")
            seen_gaps.add(identity)
            unknown = set(gap.evidence_ids) - evidence_ids
            if unknown:
                raise ValueError(f"gap cites unknown evidence ids: {sorted(unknown)}")
            for block in gap.blocks:
                if block.startswith("claim:"):
                    suffix = block.removeprefix("claim:")
                    if not suffix.isdigit() or int(suffix) >= len(self.draft.claims):
                        raise ValueError(f"gap blocks unknown claim: {block}")
                elif block.startswith("node:"):
                    if block.removeprefix("node:") not in {
                        node.id for node in self.execution.plan.nodes
                    }:
                        raise ValueError(f"gap blocks unknown node: {block}")
                elif block.startswith("requirement:"):
                    if block.removeprefix("requirement:") not in {
                        item.id for item in self.task.requirements
                    }:
                        raise ValueError(f"gap blocks unknown requirement: {block}")
        for item in self.verified_claims:
            if item.claim_index in seen:
                raise ValueError("verified claim indices must be unique")
            seen.add(item.claim_index)
            if item.claim_index >= len(self.draft.claims):
                raise ValueError("verified claim index is outside the draft")
            if item.claim != self.draft.claims[item.claim_index]:
                raise ValueError("verified claim does not match the draft")
            result = by_index.get(item.claim_index)
            if result is None or not result.supported or result.uncertain:
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
                    self.task, self.execution, self.draft, item)
            except ValueError as exc:
                raise ValueError(
                    f"verified claim carries invalid output authority: {exc}") from exc
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

def propagate_evidence_to_task(task, execution, draft, admitted):
    from v2.contracts import (
        EvidenceOutputBinding, canonical_entity_id, canonical_entity_ref)
    task_entities = {canonical_entity_ref(item) for item in task.entities}
    league_scoped = bool(task_entities) and all(
        kind == "league" for kind, _ in task_entities)
    owner_by_evidence_id = {
        envelope.evidence_id: envelope for envelope in execution.evidence}
    owned = {(binding.requirement_kind, binding.requirement_id,
              binding.output_id)
             for claim in admitted for binding in claim.output_bindings}
    candidates: dict[str, list] = {}
    for claim in admitted:
        for binding in claim.output_bindings:
            if not isinstance(binding, EvidenceOutputBinding):
                continue
            if binding.requirement_kind != "evidence":
                continue
            if binding.output_id not in task.requested_outputs:
                continue
            if binding.subject_entity_type is None \
                    or binding.subject_entity_id is None:
                continue
            subject = (binding.subject_entity_type, canonical_entity_id(
                binding.subject_entity_type, binding.subject_entity_id))
            if subject in task_entities:
                pass
            elif not task_entities or league_scoped:
                envelope = owner_by_evidence_id.get(binding.evidence_id)
                if envelope is None:
                    envelope = execution.evidence_by_node.get(binding.node_id)
                if envelope is None:
                    raise ValueError("propagation could not resolve binding evidence")
                envelope_entities = {
                    canonical_entity_ref(item) for item in envelope.entities
                }
                if subject not in envelope_entities:
                    continue
            else:
                continue
            candidates.setdefault(binding.output_id, []).append(
                (claim, binding))
    accepted: dict[int, list] = {}

    def admit_alias(claim, binding, update, key):
        if key in owned:
            return
        clone = binding.model_copy(update=update)
        trial = claim.model_copy(update={
            "output_bindings": [*claim.output_bindings, clone]})
        try:
            admit_verified_claim_bindings(task, execution, draft, trial)
        except ValueError:
            return
        accepted.setdefault(claim.claim_index, []).append(clone)
        owned.add(key)

    for output_id, competing in candidates.items():
        if len(competing) != 1:
            continue
        claim, binding = competing[0]
        admit_alias(claim, binding,
                    {"requirement_kind": "task", "requirement_id": None},
                    ("task", None, output_id))
    for claim in admitted:
        for binding in [
                *claim.output_bindings,
                *accepted.get(claim.claim_index, [])]:
            if not isinstance(binding, EvidenceOutputBinding):
                continue
            if binding.requirement_kind != "task":
                continue
            for requirement in task.requirements:
                if binding.output_id not in requirement.requested_outputs:
                    continue
                admit_alias(
                    claim, binding,
                    {"requirement_kind": "evidence",
                     "requirement_id": requirement.id},
                    ("evidence", requirement.id, binding.output_id))
    if not accepted:
        return list(admitted)
    return [claim.model_copy(update={"output_bindings": [
        *claim.output_bindings, *accepted.get(claim.claim_index, [])]})
        if claim.claim_index in accepted else claim
        for claim in admitted]

class BindingFormMismatch(ValueError):
    pass

def admit_verified_claim_bindings(
    task: TaskSpec,
    execution: ExecutionResult,
    draft: DraftReport,
    verified_claim: VerifiedClaim,
) -> VerifiedClaim:
    from v2.adapters.capabilities import CAPABILITIES, resolve_metric_column
    from v2.contracts import EvidenceOutputBinding, canonical_entity_id, canonical_entity_ref
    evidence_requirements = {item.id: item for item in task.requirements}
    calculation_requirements = {item.id: item for item in task.calculation_requirements}
    evidence_by_id = {item.evidence_id: (node_id, item)
                      for node_id, item in execution.evidence_by_node.items()}
    calculations = {item.calculation_id: item for item in draft.calculations}
    task_entities = {canonical_entity_ref(item) for item in task.entities}
    league_scoped = bool(task_entities) and all(t == "league" for t, _ in task_entities)
    verified_claim = reanchor_verified_claim_bindings(execution, verified_claim)
    fallback_map: dict[str, str] = {}
    for binding in verified_claim.output_bindings:
        if isinstance(binding, EvidenceOutputBinding):
            if binding.evidence_id not in evidence_by_id:
                if ((binding.requirement_kind == "task" and binding.requirement_id is None)
                        or binding.requirement_kind == "evidence"):
                    envelope = execution.evidence_by_node.get(binding.node_id)
                    if envelope is not None:
                        real_id = envelope.evidence_id
                        if binding.evidence_id != real_id:
                            prev = fallback_map.get(binding.evidence_id)
                            if prev is not None and prev != real_id:
                                raise ValueError("binding evidence ownership is invalid")
                            fallback_map[binding.evidence_id] = real_id
    if fallback_map:
        fixed_bindings = [
            item.model_copy(update={"evidence_id": fallback_map[item.evidence_id]})
            if isinstance(item, EvidenceOutputBinding) and item.evidence_id in fallback_map
            else item
            for item in verified_claim.output_bindings
        ]
        remapped_ids: list[str] = []
        for evidence_id in verified_claim.evidence_ids:
            mapped = fallback_map.get(evidence_id, evidence_id)
            if mapped not in remapped_ids:
                remapped_ids.append(mapped)
        remapped_sources = []
        seen_source_ids: set[str] = set()
        for source in verified_claim.sources:
            mapped = fallback_map.get(source.evidence_id, source.evidence_id)
            if mapped in seen_source_ids:
                continue
            seen_source_ids.add(mapped)
            remapped_sources.append(
                source.model_copy(update={"evidence_id": mapped})
                if mapped != source.evidence_id else source
            )
        verified_claim = verified_claim.model_copy(update={
            "output_bindings": fixed_bindings,
            "evidence_ids": remapped_ids,
            "sources": remapped_sources,
        })
    for binding in verified_claim.output_bindings:
        if isinstance(binding, EvidenceOutputBinding):
            requirement = (evidence_requirements.get(binding.requirement_id)
                           if binding.requirement_kind == "evidence" else None)
            allowed_outputs = (requirement.requested_outputs if requirement is not None
                               else task.requested_outputs)
            if binding.requirement_kind == "evidence" and requirement is None:
                raise ValueError("binding names unknown evidence requirement")
            if binding.output_id not in allowed_outputs:
                raise ValueError("binding output is outside its authority")
            owned = evidence_by_id.get(binding.evidence_id)
            if owned is None and ((binding.requirement_kind == "task"
                    and binding.requirement_id is None)
                    or binding.requirement_kind == "evidence"):
                envelope = execution.evidence_by_node.get(binding.node_id)
                if envelope is not None:
                    owned = (binding.node_id, envelope)
            if owned is None:
                raise ValueError("binding evidence ownership is invalid")
            node = next(item for item in execution.plan.nodes if item.id == owned[0])
            evidence = owned[1]
            if requirement is not None:
                if binding.requirement_id not in node.covers_requirement_ids:
                    raise ValueError("binding node does not cover requirement")
                if evidence.capability not in requirement.capability_options:
                    raise ValueError("binding capability is outside requirement")
                selected_arguments = (dict(next(
                    item.arguments for item in requirement.capability_argument_sets
                    if item.capability_id == evidence.capability))
                    if requirement.capability_argument_sets
                    else requirement.capability_arguments)
                if any(node.arguments.get(key) != value
                       for key, value in selected_arguments.items()):
                    raise ValueError("binding node scope does not match requirement")
            capability = CAPABILITIES.get(evidence.capability)
            if capability is None:
                raise ValueError("binding capability lacks catalog authority")
            if capability.units or capability.metric_definitions \
                    or capability.output_aliases:
                leaf = binding.selector.rsplit(".", 1)[-1]
                leaf = leaf.split("[", 1)[0]
                if leaf == binding.output_id:
                    metric_column = leaf
                else:
                    resolved = resolve_metric_column(capability, binding.output_id)
                    if resolved is None or resolved != leaf:
                        raise BindingFormMismatch("binding selector metric does not match output")
                    metric_column = resolved
                catalog_unit = capability.units.get(metric_column)
                evidence_unit = evidence.units.get(metric_column)
                if catalog_unit is not None and evidence_unit is not None \
                        and catalog_unit != evidence_unit:
                    raise ValueError("catalog and evidence units disagree")
                authoritative_unit = evidence_unit or catalog_unit
                if authoritative_unit is None:
                    if binding.unit.kind != "unitless":
                        raise ValueError("unitless output must be explicit")
                elif binding.unit.kind != "declared" \
                        or _canonical_unit(binding.unit.value) != _canonical_unit(authoritative_unit):
                    raise ValueError("binding unit does not match output authority")
            if _canonical_domain(binding.domain) not in {
                    _canonical_domain(capability.domain),
                    _canonical_domain(capability.name),
                    _canonical_domain(capability.tool_name),
            }:
                raise ValueError("binding domain does not match capability")
            if task.season is not None and evidence.task_season_scoped \
                    and evidence.season != task.season.value:
                raise ValueError("binding evidence season is outside task scope")
            if task.as_of is not None and evidence.as_of != task.as_of:
                raise ValueError("binding evidence as_of is outside task scope")
            scoped_entities = task_entities
            if scoped_entities and binding.subject_entity_id is None:
                raise ValueError("entity-scoped binding requires selector-local subject")
            if binding.subject_entity_id is not None:
                subject = (binding.subject_entity_type, canonical_entity_id(binding.subject_entity_type, binding.subject_entity_id))
                if subject not in scoped_entities and not ((league_scoped or not task_entities) and any(canonical_entity_ref(e) == subject for e in evidence.entities)):
                    raise ValueError("binding subject is outside requested scope")
                if evidence.entities and not any(
                        canonical_entity_ref(entity) == subject
                        for entity in evidence.entities):
                    raise ValueError("binding subject is outside evidence scope")
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
                def descends(selector: str, root: str) -> bool:
                    return (selector.startswith(root + ".")
                            or selector.startswith(root + "["))
                if not descends(binding.selector, row_root) \
                        or not descends(binding.subject_selector, row_root):
                    raise ValueError("binding selectors are outside declared row")
                subject_row = resolve_subject_row(evidence, binding, subject[1])
                if subject_row is None:
                    raise ValueError("binding selector row does not match subject")
            else:
                subject_row = None
            resolution = resolve_evidence_binding(evidence, binding, subject_row)
            if isinstance(resolution, AmbiguousSelector):
                raise ValueError(
                    f"binding selector names {len(resolution.paths)} values")
            if not isinstance(resolution, ResolvedSelector) \
                    or resolution.value is None:
                raise ValueError("binding selector must locate exactly one value")
            selected = resolution.value
            declared = binding.value
            if not _declared_value_matches(declared, selected):
                raise ValueError("binding value does not exactly match selected evidence")
            if binding.evidence_id not in verified_claim.evidence_ids:
                raise ValueError("binding evidence is not cited by claim")
        else:
            requirement = calculation_requirements.get(binding.requirement_id)
            if requirement is None or binding.output_id not in requirement.requested_outputs:
                raise ValueError("binding calculation output is outside requirement")
            calculation = calculations.get(binding.calculation_id)
            if calculation is None or calculation.requirement_id != binding.requirement_id:
                raise ValueError("binding calculation authority is invalid")
            if verified_claim.claim.calculation_id != binding.calculation_id:
                raise ValueError("binding calculation is not cited by claim")
            from v2.domain.calculations import Calculation, validate_calculation
            from v2.domain.evidence import EvidenceIndex
            checked = Calculation.model_validate({
                "calculation_id": calculation.calculation_id,
                "operation": calculation.operation,
                "inputs": [item.model_dump() for item in calculation.inputs],
                "result": calculation.result, "unit": calculation.unit,
                "subject_input": calculation.subject_input})
            if validate_calculation(checked, EvidenceIndex(execution.evidence)) is not None:
                raise ValueError("binding calculation did not pass recomputation")
            operation = str(calculation.operation)
            unit_text = (calculation.unit or "").strip().casefold()
            if operation in ("rank_desc", "rank_asc"):
                if unit_text not in ("", "rank", "unitless"):
                    raise ValueError("rank calculation unit must be rank or unitless")
            elif unit_text == "rank":
                raise ValueError("non-rank calculation cannot carry rank unit")
    return verified_claim
