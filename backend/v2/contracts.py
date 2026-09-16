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
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["player", "team", "game", "league"]
    display_name: str

    @model_validator(mode="after")
    def validate_identity(self) -> "EntityRef":
        if not self.id.strip() or not self.display_name.strip():
            raise ValueError("entity id and display name must be non-empty")
        return self


class SeasonRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    source: Literal["user", "context", "default", "resolved"]
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_identity(self) -> "SeasonRef":
        if not self.value.strip():
            raise ValueError("season value must be non-empty")
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


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
        if not self.goal.strip() or not self.deliverable.strip():
            raise ValueError("task goal and deliverable must be non-empty")
        for field_name in ("subquestions", "required_evidence", "assumptions",
                           "open_questions", "skills"):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError(f"{field_name} must not contain empty values")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        entity_keys = [(item.type, item.id) for item in self.entities]
        if len(entity_keys) != len(set(entity_keys)):
            raise ValueError("entities must not contain duplicate identities")
        return self


class PlanNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    capability_hints: list[str] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = Field(default=1, ge=1, le=5)
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
        return self


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
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

    @model_validator(mode="after")
    def validate_identity(self) -> "EvidenceEnvelope":
        if not self.capability.strip() or not self.source.strip():
            raise ValueError("evidence capability and source must be non-empty")
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
        return self


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    kind: ClaimKind
    evidence_ids: list[str] = Field(default_factory=list)
    calculation_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_support(self) -> Claim:
        if not self.text.strip():
            raise ValueError("claim text must be non-empty")
        if any(not evidence_id.strip() for evidence_id in self.evidence_ids):
            raise ValueError("claim evidence_ids must not contain empty values")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("claim evidence_ids must not contain duplicates")
        if self.kind in (ClaimKind.OBSERVED, ClaimKind.DERIVED):
            if not self.evidence_ids:
                raise ValueError("observed and derived claims require evidence")
        if self.kind == ClaimKind.DERIVED and not self.calculation_id:
            raise ValueError("derived claims require a calculation id")
        if self.kind != ClaimKind.DERIVED and self.calculation_id is not None:
            raise ValueError("only derived claims may name a calculation id")
        if self.kind == ClaimKind.PROJECTION and self.confidence is None:
            raise ValueError("projection claims require confidence")
        if self.kind == ClaimKind.PROJECTION and not self.evidence_ids:
            raise ValueError("projection claims require evidence")
        if self.kind != ClaimKind.PROJECTION and self.confidence is not None:
            raise ValueError("only projection claims may name confidence")
        return self


class DraftReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[str]
    claims: list[Claim]
    gaps: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content(self) -> "DraftReport":
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
    message: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)

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


class ClaimSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source: str
    capability: str

    @model_validator(mode="after")
    def validate_identity(self) -> "ClaimSource":
        if not all(value.strip() for value in (
            self.evidence_id, self.source, self.capability
        )):
            raise ValueError("claim source identity must be non-empty")
        return self


class VerifiedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_index: int = Field(ge=0)
    claim: Claim
    evidence_ids: list[str] = Field(default_factory=list)
    sources: list[ClaimSource] = Field(default_factory=list)

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
        return self


class ClaimResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_index: int = Field(ge=0)
    supported: bool
    reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_reason(self) -> "ClaimResult":
        if not self.supported and not self.reasons:
            raise ValueError("unsupported claim result requires a reason")
        if self.supported and self.reasons:
            raise ValueError("supported claim result cannot carry rejection reasons")
        if any(not reason.strip() for reason in self.reasons):
            raise ValueError("claim result reasons must not contain empty values")
        if len(self.reasons) != len(set(self.reasons)):
            raise ValueError("claim result reasons must not contain duplicates")
        return self


class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VerificationStatus
    claim_results: list[ClaimResult] = Field(default_factory=list)
    missing_branches: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    repair_instructions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self) -> "VerificationReport":
        indices = [item.claim_index for item in self.claim_results]
        if len(indices) != len(set(indices)):
            raise ValueError("verification claim indices must be unique")
        for field_name in ("missing_branches", "contradictions",
                           "repair_instructions"):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError(f"{field_name} must not contain empty values")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        findings = (
            any(not item.supported for item in self.claim_results)
            or bool(self.missing_branches)
            or bool(self.contradictions)
            or bool(self.repair_instructions)
        )
        if self.status == VerificationStatus.PASS and findings:
            raise ValueError("pass status contradicts verification findings")
        if self.status == VerificationStatus.REPAIR and not findings:
            raise ValueError("repair status requires an actionable finding")
        return self
