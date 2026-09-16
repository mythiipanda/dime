from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from threading import Lock

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CandidateState(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


class FailureObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    failure_class: str
    summary: str
    expected_relation: str
    revision: str
    trace_id: str | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> "FailureObservation":
        values = (self.source, self.failure_class, self.summary,
                  self.expected_relation, self.revision)
        if any(not value.strip() for value in values):
            raise ValueError("failure observation fields must be non-empty")
        if self.trace_id is not None and not self.trace_id.strip():
            raise ValueError("failure observation trace id must be non-empty")
        return self


class ScenarioCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    source: str
    failure_class: str
    summary: str
    expected_relation: str
    first_bad_revision: str
    trace_id: str | None = None
    state: CandidateState = CandidateState.PENDING
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_identity(self) -> "ScenarioCandidate":
        values = (self.candidate_id, self.source, self.failure_class, self.summary,
                  self.expected_relation, self.first_bad_revision)
        if any(not value.strip() for value in values):
            raise ValueError("scenario candidate fields must be non-empty")
        if self.trace_id is not None and not self.trace_id.strip():
            raise ValueError("scenario candidate trace id must be non-empty")
        if any(not tag.strip() for tag in self.tags):
            raise ValueError("scenario candidate tags must be non-empty")
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("scenario candidate tags must be unique")
        return self

    @classmethod
    def from_observation(cls, item: FailureObservation) -> "ScenarioCandidate":
        identity = {
            "failure_class": item.failure_class.casefold().strip(),
            "summary": " ".join(item.summary.casefold().split()),
            "expected_relation": " ".join(item.expected_relation.casefold().split()),
        }
        candidate_id = hashlib.sha256(json.dumps(
            identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
        return cls(
            candidate_id=candidate_id,
            source=item.source,
            failure_class=item.failure_class,
            summary=item.summary,
            expected_relation=item.expected_relation,
            first_bad_revision=item.revision,
            trace_id=item.trace_id,
        )


class CandidateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def add(self, item: FailureObservation) -> ScenarioCandidate:
        candidate = ScenarioCandidate.from_observation(item)
        current = {entry.candidate_id: entry for entry in self.read()}
        if candidate.candidate_id in current:
            return current[candidate.candidate_id]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(candidate.model_dump_json() + "\n")
        return candidate

    def read(self) -> list[ScenarioCandidate]:
        if not self.path.exists():
            return []
        return [ScenarioCandidate.model_validate_json(line)
                for line in self.path.read_text().splitlines() if line.strip()]
