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
