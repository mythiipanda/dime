from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, model_validator

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


class OutcomeStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OutcomeStatus
    answer: str = Field(default="", max_length=200_000)
    capabilities: list[str] = Field(default_factory=list, max_length=32)
    evidence_count: StrictInt = 0
    supported_claims: StrictInt = 0
    total_claims: StrictInt = 0
    duration_ms: StrictInt | None = None

    @model_validator(mode="after")
    def validate_metrics(self) -> "RunOutcome":
        if any(not name.strip() for name in self.capabilities):
            raise ValueError("shadow outcome capabilities must be non-empty")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("shadow outcome capabilities must be unique")
        if min(self.evidence_count, self.supported_claims, self.total_claims) < 0:
            raise ValueError("shadow outcome counts must be non-negative")
        if self.supported_claims > self.total_claims:
            raise ValueError("supported claims cannot exceed total claims")
        if self.status == OutcomeStatus.OK and self.supported_claims != self.total_claims:
            raise ValueError("ok shadow outcome requires every claim to be supported")
        if self.status == OutcomeStatus.OK and not self.answer.strip():
            raise ValueError("ok shadow outcome requires a non-empty answer")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("shadow outcome duration must be non-negative")
        return self


class ShadowComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison_id: str = Field(max_length=24)
    request_hash: str = Field(max_length=64)
    v1: RunOutcome
    v2: RunOutcome
    differences: list[DifferenceKind] = Field(default_factory=list, max_length=4)

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
    if v1.status != OutcomeStatus.OK or v2.status != OutcomeStatus.OK:
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
    if not isinstance(request, str):
        raise TypeError("shadow request must be a string")
    if not request.strip():
        raise ValueError("shadow request must be non-empty")
    if len(request) > 2000:
        raise ValueError("shadow request cannot exceed 2000 characters")
    v1 = RunOutcome.model_validate(v1.model_dump())
    v2 = RunOutcome.model_validate(v2.model_dump())
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
        self._reject_symlinked_path()
        self._lock = _shadow_path_lock(self.path)

    def _reject_symlinked_path(self) -> None:
        if self.path.is_symlink():
            raise ValueError("shadow store file cannot be a symlink")
        parent = self.path.parent
        if any(component.is_symlink() for component in (parent, *parent.parents)):
            raise ValueError("shadow store parent cannot be a symlink")

    def append(self, comparison: ShadowComparison) -> None:
        comparison = ShadowComparison.model_validate(comparison.model_dump())
        with self._lock:
            self._reject_symlinked_path()
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
            self._reject_symlinked_path()
            if not self.path.exists():
                return []
            lines = self.path.read_text().splitlines()
            if any(not line.strip() for line in lines):
                raise ValueError("shadow store cannot contain blank records")
            return [ShadowComparison.model_validate_json(line) for line in lines]


def outcome_from_v2(result: Any, answer: str, duration_ms: int | None = None) -> RunOutcome:
    from v2.runtime.models import RuntimeResult

    result = RuntimeResult.model_validate(result.model_dump())
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

    minimum_runs: StrictInt = Field(default=100, ge=1)
    maximum_failure_rate: StrictFloat = Field(default=0.01, ge=0, le=1)
    maximum_grounding_drift_rate: StrictFloat = Field(default=0.01, ge=0, le=1)
    maximum_route_drift_rate: StrictFloat = Field(default=0.05, ge=0, le=1)
    maximum_answer_drift_rate: StrictFloat = Field(default=0.10, ge=0, le=1)


class ShadowGateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_runs: StrictInt
    failure_rate: StrictFloat
    grounding_drift_rate: StrictFloat
    route_drift_rate: StrictFloat
    answer_drift_rate: StrictFloat
    ready: StrictBool
    blockers: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_report(self) -> "ShadowGateReport":
        rates = (self.failure_rate, self.grounding_drift_rate,
                 self.route_drift_rate, self.answer_drift_rate)
        if (self.total_runs < 0
                or any(not math.isfinite(rate) or rate < 0 or rate > 1
                       for rate in rates)):
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
    policy = (ShadowGatePolicy() if policy is None
              else ShadowGatePolicy.model_validate(policy.model_dump()))
    comparisons = [
        ShadowComparison.model_validate(item.model_dump())
        for item in comparisons
    ]
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
