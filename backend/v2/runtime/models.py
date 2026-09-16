from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from v2.contracts import (
    DraftReport,
    EvidenceEnvelope,
    Plan,
    TaskSpec,
    Gap,
    VerificationReport,
    VerifiedClaim,
)


class ExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: Plan
    evidence: list[EvidenceEnvelope] = Field(default_factory=list)
    attempts: dict[str, int] = Field(default_factory=dict)
    errors: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_execution(self) -> "ExecutionResult":
        nodes = {node.id: node for node in self.plan.nodes}
        unknown = (set(self.attempts) | set(self.errors)) - nodes.keys()
        if unknown:
            raise ValueError(f"execution references unknown nodes: {sorted(unknown)}")
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("execution evidence ids must be unique")
        completed = [
            node for node in self.plan.nodes if node.status.value == "complete"
        ]
        if len(completed) != len(self.evidence):
            raise ValueError("execution evidence must match completed plan nodes")
        evidence_by_node = dict(zip(
            (node.id for node in completed), self.evidence, strict=True
        ))
        for node, item in zip(completed, self.evidence, strict=True):
            if item.capability not in node.capability_hints:
                raise ValueError(
                    f"execution evidence capability does not match node {node.id!r}")
            expected_lineage = [
                evidence_by_node[parent].evidence_id
                for parent in node.depends_on
                if parent in evidence_by_node
            ]
            if item.lineage != expected_lineage:
                raise ValueError(
                    f"execution evidence lineage does not match node {node.id!r}")
        if any(count < 0 for count in self.attempts.values()):
            raise ValueError("execution attempt counts must be non-negative")
        for node in self.plan.nodes:
            count = self.attempts.get(node.id, 0)
            if count > node.max_attempts:
                raise ValueError(
                    f"execution attempts exceed max_attempts for node {node.id!r}")
            if node.status.value in {"complete", "failed"} and count == 0:
                raise ValueError(
                    f"execution node {node.id!r} reached terminal state without an attempt")
            node_errors = self.errors.get(node.id, [])
            if any(not error.strip() for error in node_errors):
                raise ValueError(f"execution node {node.id!r} has empty errors")
            if len(node_errors) != len(set(node_errors)):
                raise ValueError(f"execution node {node.id!r} has duplicate errors")
            if node.status.value == "failed" and not node_errors:
                raise ValueError(f"failed node {node.id!r} requires errors")
            if node.status.value in {"pending", "running"} and count >= node.max_attempts:
                raise ValueError(
                    f"execution node {node.id!r} has no attempts remaining")
            if node.status.value == "skipped" and node_errors:
                raise ValueError(f"skipped node {node.id!r} cannot carry errors")
        return self


class RuntimeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: TaskSpec
    execution: ExecutionResult
    draft: DraftReport
    verification: VerificationReport
    repaired: bool = False
    verified_claims: list[VerifiedClaim] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_publication(self) -> "RuntimeResult":
        by_index = {item.claim_index: item for item in self.verification.claim_results}
        invalid_indices = [
            index for index in by_index if index >= len(self.draft.claims)
        ]
        if invalid_indices:
            raise ValueError(
                f"verification claim indices are outside the draft: {invalid_indices}")
        evidence = {item.evidence_id: item for item in self.execution.evidence}
        seen: set[int] = set()
        evidence_ids = set(evidence)
        for gap in self.gaps:
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
        supported = {index for index, result in by_index.items() if result.supported}
        if seen != supported:
            raise ValueError("verified claims must match supported adjudications")
        return self
