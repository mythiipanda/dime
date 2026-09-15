from __future__ import annotations

from pydantic import BaseModel, Field

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
    plan: Plan
    evidence: list[EvidenceEnvelope] = Field(default_factory=list)
    attempts: dict[str, int] = Field(default_factory=dict)
    errors: dict[str, list[str]] = Field(default_factory=dict)


class RuntimeResult(BaseModel):
    task: TaskSpec
    execution: ExecutionResult
    draft: DraftReport
    verification: VerificationReport
    repaired: bool = False
    verified_claims: list[VerifiedClaim] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
