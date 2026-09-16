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
        evidence = {item.evidence_id: item for item in self.execution.evidence}
        seen: set[int] = set()
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
        return self
