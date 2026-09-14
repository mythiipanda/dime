from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any, Mapping

from pydantic import BaseModel, Field


class DifferenceKind(StrEnum):
    ANSWER = "answer"
    ROUTE = "route"
    GROUNDING = "grounding"
    FAILURE = "failure"


class RunOutcome(BaseModel):
    status: str
    answer: str = ""
    capabilities: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    supported_claims: int = 0
    total_claims: int = 0
    duration_ms: int | None = None


class ShadowComparison(BaseModel):
    comparison_id: str
    request_hash: str
    v1: RunOutcome
    v2: RunOutcome
    differences: list[DifferenceKind] = Field(default_factory=list)


def compare_outcomes(request: str, v1: RunOutcome, v2: RunOutcome) -> ShadowComparison:
    differences: list[DifferenceKind] = []
    if v1.status != v2.status or v1.status != "ok":
        differences.append(DifferenceKind.FAILURE)
    if _canon(v1.answer) != _canon(v2.answer):
        differences.append(DifferenceKind.ANSWER)
    if set(v1.capabilities) != set(v2.capabilities):
        differences.append(DifferenceKind.ROUTE)
    v1_grounded = (v1.supported_claims, v1.total_claims, v1.evidence_count)
    v2_grounded = (v2.supported_claims, v2.total_claims, v2.evidence_count)
    if v1_grounded != v2_grounded:
        differences.append(DifferenceKind.GROUNDING)
    request_hash = _hash(request)
    comparison_id = _hash({
        "request": request_hash,
        "v1": v1.model_dump(mode="json"),
        "v2": v2.model_dump(mode="json"),
    })[:24]
    return ShadowComparison(
        comparison_id=comparison_id,
        request_hash=request_hash,
        v1=v1,
        v2=v2,
        differences=differences,
    )


class ShadowStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def append(self, comparison: ShadowComparison) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(comparison.model_dump_json() + "\n")
            handle.flush()

    def read(self) -> list[ShadowComparison]:
        if not self.path.exists():
            return []
        return [
            ShadowComparison.model_validate_json(line)
            for line in self.path.read_text().splitlines()
            if line.strip()
        ]


def outcome_from_v2(result: Any, answer: str, duration_ms: int | None = None) -> RunOutcome:
    claim_results = result.verification.claim_results
    return RunOutcome(
        status="ok",
        answer=answer,
        capabilities=[item.capability for item in result.execution.evidence],
        evidence_count=len(result.execution.evidence),
        supported_claims=sum(item.supported for item in claim_results),
        total_claims=len(result.draft.claims),
        duration_ms=duration_ms,
    )


def _canon(value: str) -> str:
    return " ".join(value.casefold().split())


def _hash(value: Any) -> str:
    raw = value if isinstance(value, str) else json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()

class ShadowGatePolicy(BaseModel):
    minimum_runs: int = Field(default=100, ge=1)
    maximum_failure_rate: float = Field(default=0.01, ge=0, le=1)
    maximum_grounding_drift_rate: float = Field(default=0.01, ge=0, le=1)
    maximum_route_drift_rate: float = Field(default=0.05, ge=0, le=1)
    maximum_answer_drift_rate: float = Field(default=0.10, ge=0, le=1)


class ShadowGateReport(BaseModel):
    total_runs: int
    failure_rate: float
    grounding_drift_rate: float
    route_drift_rate: float
    answer_drift_rate: float
    ready: bool
    blockers: list[str] = Field(default_factory=list)


def evaluate_shadow_gate(
    comparisons: list[ShadowComparison],
    policy: ShadowGatePolicy | None = None,
) -> ShadowGateReport:
    policy = policy or ShadowGatePolicy()
    total = len(comparisons)

    def rate(kind: DifferenceKind) -> float:
        if not total:
            return 0.0
        return sum(kind in item.differences for item in comparisons) / total

    rates = {
        DifferenceKind.FAILURE: rate(DifferenceKind.FAILURE),
        DifferenceKind.GROUNDING: rate(DifferenceKind.GROUNDING),
        DifferenceKind.ROUTE: rate(DifferenceKind.ROUTE),
        DifferenceKind.ANSWER: rate(DifferenceKind.ANSWER),
    }
    blockers: list[str] = []
    if total < policy.minimum_runs:
        blockers.append(
            f"need {policy.minimum_runs - total} more shadow runs")
    checks = [
        (DifferenceKind.FAILURE, policy.maximum_failure_rate),
        (DifferenceKind.GROUNDING, policy.maximum_grounding_drift_rate),
        (DifferenceKind.ROUTE, policy.maximum_route_drift_rate),
        (DifferenceKind.ANSWER, policy.maximum_answer_drift_rate),
    ]
    for kind, maximum in checks:
        if rates[kind] > maximum:
            blockers.append(
                f"{kind.value} rate {rates[kind]:.3f} exceeds {maximum:.3f}")
    return ShadowGateReport(
        total_runs=total,
        failure_rate=rates[DifferenceKind.FAILURE],
        grounding_drift_rate=rates[DifferenceKind.GROUNDING],
        route_drift_rate=rates[DifferenceKind.ROUTE],
        answer_drift_rate=rates[DifferenceKind.ANSWER],
        ready=not blockers,
        blockers=blockers,
    )
