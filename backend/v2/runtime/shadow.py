from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHADOW_LOCKS_GUARD = Lock()
_SHADOW_LOCKS: dict[Path, Lock] = {}


def _shadow_path_lock(path: Path) -> Lock:
    resolved = path.resolve()
    with _SHADOW_LOCKS_GUARD:
        return _SHADOW_LOCKS.setdefault(resolved, Lock())


class DifferenceKind(StrEnum):
    ANSWER = "answer"
    ROUTE = "route"
    GROUNDING = "grounding"
    FAILURE = "failure"


class RunOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    answer: str = ""
    capabilities: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    supported_claims: int = 0
    total_claims: int = 0
    duration_ms: int | None = None

    @model_validator(mode="after")
    def validate_metrics(self) -> "RunOutcome":
        if not self.status.strip():
            raise ValueError("shadow outcome status must be non-empty")
        if any(not name.strip() for name in self.capabilities):
            raise ValueError("shadow outcome capabilities must be non-empty")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("shadow outcome capabilities must be unique")
        if min(self.evidence_count, self.supported_claims, self.total_claims) < 0:
            raise ValueError("shadow outcome counts must be non-negative")
        if self.supported_claims > self.total_claims:
            raise ValueError("supported claims cannot exceed total claims")
        if self.status == "ok" and self.supported_claims != self.total_claims:
            raise ValueError("ok shadow outcome requires every claim to be supported")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("shadow outcome duration must be non-negative")
        return self


class ShadowComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison_id: str
    request_hash: str
    v1: RunOutcome
    v2: RunOutcome
    differences: list[DifferenceKind] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_identity(self) -> "ShadowComparison":
        if not self.comparison_id.strip() or not self.request_hash.strip():
            raise ValueError("shadow comparison identity must be non-empty")
        if len(self.request_hash) != 64 or any(
            char not in "0123456789abcdef" for char in self.request_hash
        ):
            raise ValueError("shadow request hash must be lowercase sha256")
        if len(self.differences) != len(set(self.differences)):
            raise ValueError("shadow differences must be unique")
        expected = _difference_kinds(self.v1, self.v2)
        if self.differences != expected:
            raise ValueError("shadow differences do not match recorded outcomes")
        identity = _hash({
            "request": self.request_hash,
            "v1": self.v1.model_dump(mode="json"),
            "v2": self.v2.model_dump(mode="json"),
        })[:24]
        if self.comparison_id != identity:
            raise ValueError("shadow comparison id does not match recorded outcomes")
        return self


def _difference_kinds(v1: RunOutcome, v2: RunOutcome) -> list[DifferenceKind]:
    differences: list[DifferenceKind] = []
    if v1.status != "ok" or v2.status != "ok":
        differences.append(DifferenceKind.FAILURE)
    if _canon(v1.answer) != _canon(v2.answer):
        differences.append(DifferenceKind.ANSWER)
    if set(v1.capabilities) != set(v2.capabilities):
        differences.append(DifferenceKind.ROUTE)
    v1_grounded = (v1.supported_claims, v1.total_claims, v1.evidence_count)
    v2_grounded = (v2.supported_claims, v2.total_claims, v2.evidence_count)
    if v1_grounded != v2_grounded:
        differences.append(DifferenceKind.GROUNDING)
    return differences


def compare_outcomes(request: str, v1: RunOutcome, v2: RunOutcome) -> ShadowComparison:
    differences = _difference_kinds(v1, v2)
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
        self._lock = _shadow_path_lock(self.path)

    def append(self, comparison: ShadowComparison) -> None:
        with self._lock:
            parent_was_missing = not self.path.parent.exists()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            file_was_missing = not self.path.exists()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(comparison.model_dump_json() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            if parent_was_missing or file_was_missing:
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)

    def read(self) -> list[ShadowComparison]:
        with self._lock:
            if self.path.is_symlink():
                raise ValueError("shadow store file cannot be a symlink")
            if not self.path.exists():
                return []
            lines = self.path.read_text().splitlines()
            if any(not line.strip() for line in lines):
                raise ValueError("shadow store cannot contain blank records")
            return [ShadowComparison.model_validate_json(line) for line in lines]


def outcome_from_v2(result: Any, answer: str, duration_ms: int | None = None) -> RunOutcome:
    claim_results = result.verification.claim_results
    status = result.verification.status.value
    return RunOutcome(
        status="ok" if status == "pass" else status,
        answer=answer,
        capabilities=list(dict.fromkeys(
            item.capability for item in result.execution.evidence
        )),
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
    model_config = ConfigDict(extra="forbid")

    minimum_runs: int = Field(default=100, ge=1)
    maximum_failure_rate: float = Field(default=0.01, ge=0, le=1)
    maximum_grounding_drift_rate: float = Field(default=0.01, ge=0, le=1)
    maximum_route_drift_rate: float = Field(default=0.05, ge=0, le=1)
    maximum_answer_drift_rate: float = Field(default=0.10, ge=0, le=1)


class ShadowGateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_runs: int
    failure_rate: float
    grounding_drift_rate: float
    route_drift_rate: float
    answer_drift_rate: float
    ready: bool
    blockers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_report(self) -> "ShadowGateReport":
        rates = (self.failure_rate, self.grounding_drift_rate,
                 self.route_drift_rate, self.answer_drift_rate)
        if self.total_runs < 0 or any(rate < 0 or rate > 1 for rate in rates):
            raise ValueError("shadow gate counts and rates are out of range")
        if any(not blocker.strip() for blocker in self.blockers):
            raise ValueError("shadow gate blockers must be non-empty")
        if len(self.blockers) != len(set(self.blockers)):
            raise ValueError("shadow gate blockers must be unique")
        if self.ready == bool(self.blockers):
            raise ValueError("shadow gate readiness contradicts blockers")
        return self


def evaluate_shadow_gate(
    comparisons: list[ShadowComparison],
    policy: ShadowGatePolicy | None = None,
) -> ShadowGateReport:
    policy = policy or ShadowGatePolicy()
    ids = [comparison.comparison_id for comparison in comparisons]
    if len(ids) != len(set(ids)):
        raise ValueError("shadow gate comparisons must be unique")
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
