from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class GapKind(StrEnum):
    MISSING_EVIDENCE = "missing_evidence"
    SOURCE_CONFLICT = "source_conflict"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    EXECUTION_FAILURE = "execution_failure"


class EntityRef(BaseModel):
    id: str
    type: Literal["player", "team", "game", "league"]
    display_name: str


class SeasonRef(BaseModel):
    value: str
    source: Literal["user", "context", "default", "resolved"]
    confidence: float = Field(ge=0, le=1)


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class TaskSpec(BaseModel):
    goal: str
    mode: RunMode
    deliverable: str
    entities: list[EntityRef] = Field(default_factory=list)
    season: SeasonRef | None = None
    as_of: date | None = None
    subquestions: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scope(self) -> "TaskSpec":
        if len(self.required_evidence) != len(set(self.required_evidence)):
            raise ValueError("required_evidence must not contain duplicates")
        entity_keys = [(item.type, item.id) for item in self.entities]
        if len(entity_keys) != len(set(entity_keys)):
            raise ValueError("entities must not contain duplicate identities")
        if len(self.skills) != len(set(self.skills)):
            raise ValueError("skills must not contain duplicates")
        return self


class PlanNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    capability_hints: list[str] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = Field(default=1, ge=1, le=5)
    status: PlanStatus = PlanStatus.PENDING


class Plan(BaseModel):
    nodes: list[PlanNode]

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


class EvidenceEnvelope(BaseModel):
    evidence_id: str
    capability: str
    source: str
    observed_at: datetime
    season: str | None = None
    vintages: dict[str, str] = Field(default_factory=dict)
    task_season_scoped: bool = True
    as_of: date | None = None
    entities: list[EntityRef] = Field(default_factory=list)
    rows: list[dict[str, Any]] | dict[str, Any]
    units: dict[str, str] = Field(default_factory=dict)
    metric_definitions: dict[str, str] = Field(default_factory=dict)
    qualification: str | None = None
    coverage: str | None = None
    lineage: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    text: str
    kind: ClaimKind
    evidence_ids: list[str] = Field(default_factory=list)
    calculation_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_support(self) -> Claim:
        if self.kind in (ClaimKind.OBSERVED, ClaimKind.DERIVED):
            if not self.evidence_ids:
                raise ValueError("observed and derived claims require evidence")
        if self.kind == ClaimKind.DERIVED and not self.calculation_id:
            raise ValueError("derived claims require a calculation id")
        if self.kind == ClaimKind.PROJECTION and self.confidence is None:
            raise ValueError("projection claims require confidence")
        return self


class DraftReport(BaseModel):
    sections: list[str]
    claims: list[Claim]
    gaps: list[str] = Field(default_factory=list)


class Gap(BaseModel):
    kind: GapKind
    message: str
    evidence_ids: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)


class ClaimSource(BaseModel):
    evidence_id: str
    source: str
    capability: str


class VerifiedClaim(BaseModel):
    claim_index: int = Field(ge=0)
    claim: Claim
    evidence_ids: list[str] = Field(default_factory=list)
    sources: list[ClaimSource] = Field(default_factory=list)


class ClaimResult(BaseModel):
    claim_index: int = Field(ge=0)
    supported: bool
    reasons: list[str] = Field(default_factory=list)


class VerificationReport(BaseModel):
    status: VerificationStatus
    claim_results: list[ClaimResult] = Field(default_factory=list)
    missing_branches: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    repair_instructions: list[str] = Field(default_factory=list)
