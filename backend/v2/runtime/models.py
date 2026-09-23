from __future__ import annotations

from enum import StrEnum

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
)


class ExecutionErrorCode(StrEnum):
    PROFILE_NAME_RESOLUTION_UNAVAILABLE = "profile/name_resolution_unavailable"


class ExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: Plan
    evidence_by_node: dict[str, EvidenceEnvelope] = Field(default_factory=dict, max_length=32)

    @property
    def evidence(self) -> list[EvidenceEnvelope]:
        """Stable public evidence list; ownership remains explicit by node."""
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
            if result is None or not result.supported:
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
        supported = {index for index, result in by_index.items() if result.supported}
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


def build_output_statuses(task, verified_claims, gaps):
    """Compute one deterministic status for every typed requested output."""
    from v2.contracts import OutputFinalStatus
    admitted = {}
    rejected = set()
    for claim in verified_claims:
        if any(gap.kind.value == "synthesis_incomplete"
               and f"claim:{claim.claim_index}" in gap.blocks for gap in gaps):
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


def admit_verified_claim_bindings(
    task: TaskSpec,
    execution: ExecutionResult,
    draft: DraftReport,
    verified_claim: VerifiedClaim,
) -> VerifiedClaim:
    """Atomically validate claim-local output authority; never infer it."""
    from v2.adapters.capabilities import CAPABILITIES
    from v2.contracts import EvidenceOutputBinding, CalculationOutputBinding
    from v2.domain.evidence import iter_values
    evidence_requirements = {item.id: item for item in task.requirements}
    calculation_requirements = {item.id: item for item in task.calculation_requirements}
    evidence_by_id = {item.evidence_id: (node_id, item)
                      for node_id, item in execution.evidence_by_node.items()}
    calculations = {item.calculation_id: item for item in draft.calculations}
    task_entities = {(item.type, item.id) for item in task.entities}
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
            if owned is None or owned[0] != binding.node_id:
                raise ValueError("binding evidence ownership is invalid")
            node = next(item for item in execution.plan.nodes if item.id == binding.node_id)
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
            leaf = binding.selector.rsplit(".", 1)[-1]
            leaf = leaf.split("[", 1)[0]
            if leaf != binding.output_id:
                raise ValueError("binding selector metric does not match output")
            catalog_unit = capability.units.get(binding.output_id)
            evidence_unit = evidence.units.get(binding.output_id)
            if catalog_unit is not None and evidence_unit is not None \
                    and catalog_unit != evidence_unit:
                raise ValueError("catalog and evidence units disagree")
            authoritative_unit = evidence_unit or catalog_unit
            if authoritative_unit is None:
                if binding.unit.kind != "unitless":
                    raise ValueError("unitless output must be explicit")
            elif binding.unit.kind != "declared" \
                    or binding.unit.value != authoritative_unit:
                raise ValueError("binding unit does not match output authority")
            if binding.domain != evidence.capability:
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
                subject = (binding.subject_entity_type, binding.subject_entity_id)
                if subject not in scoped_entities:
                    raise ValueError("binding subject is outside requested scope")
                if not any((entity.type, entity.id) == subject
                           for entity in evidence.entities):
                    raise ValueError("binding subject is outside evidence scope")
                values = [item for item in iter_values(evidence)
                          if item.path == binding.selector]
                identity_keys = {
                    "player": {"PLAYER_ID", "player_id"},
                    "team": {"TEAM_ID", "team_id"},
                }.get(binding.subject_entity_type)
                if identity_keys is None:
                    raise ValueError("binding subject type lacks identity authority")
                subject_values = [item.value for item in iter_values(evidence)
                                  if item.path == binding.subject_selector]
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
                if len(subject_values) != 1 or str(subject_values[0]) != binding.subject_entity_id:
                    raise ValueError("binding selector row does not match subject")
            else:
                values = [item for item in iter_values(evidence)
                          if item.path == binding.selector]
            if len(values) != 1 or values[0].value is None:
                raise ValueError("binding selector must locate exactly one value")
            selected = values[0].value
            declared = binding.value
            if declared.kind == "boolean":
                equal = isinstance(selected, bool) and selected is declared.value
            elif declared.kind == "integer":
                equal = (not isinstance(selected, bool)
                         and isinstance(selected, int)
                         and selected == declared.value)
            elif declared.kind == "float":
                equal = (isinstance(selected, float)
                         and selected == declared.value)
            elif declared.kind == "decimal":
                from decimal import Decimal
                equal = (isinstance(selected, Decimal)
                         and selected == Decimal(declared.value))
            else:
                equal = isinstance(selected, str) and selected == declared.value
            if not equal:
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
    return verified_claim
