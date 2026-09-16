from __future__ import annotations

import hashlib
import json
import os
from enum import StrEnum
from pathlib import Path
from threading import Lock

from pydantic import BaseModel, ConfigDict, Field, model_validator

_CANDIDATE_LOCKS_GUARD = Lock()
_CANDIDATE_LOCKS: dict[Path, Lock] = {}


def _candidate_path_lock(path: Path) -> Lock:
    resolved = path.resolve()
    with _CANDIDATE_LOCKS_GUARD:
        return _CANDIDATE_LOCKS.setdefault(resolved, Lock())


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
    tags: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_identity(self) -> "ScenarioCandidate":
        values = (self.candidate_id, self.source, self.failure_class, self.summary,
                  self.expected_relation, self.first_bad_revision)
        if any(not value.strip() for value in values):
            raise ValueError("scenario candidate fields must be non-empty")
        if self.trace_id is not None and not self.trace_id.strip():
            raise ValueError("scenario candidate trace id must be non-empty")
        expected_id = _candidate_id(
            self.failure_class, self.summary, self.expected_relation)
        if self.candidate_id != expected_id:
            raise ValueError("scenario candidate id does not match failure identity")
        if any(not tag.strip() for tag in self.tags):
            raise ValueError("scenario candidate tags must be non-empty")
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("scenario candidate tags must be unique")
        return self

    @classmethod
    def from_observation(cls, item: FailureObservation) -> "ScenarioCandidate":
        return cls(
            candidate_id=_candidate_id(
                item.failure_class, item.summary, item.expected_relation),
            source=item.source,
            failure_class=item.failure_class,
            summary=item.summary,
            expected_relation=item.expected_relation,
            first_bad_revision=item.revision,
            trace_id=item.trace_id,
        )


def _candidate_id(
    failure_class: str, summary: str, expected_relation: str,
) -> str:
    identity = {
        "failure_class": failure_class.casefold().strip(),
        "summary": " ".join(summary.casefold().split()),
        "expected_relation": " ".join(expected_relation.casefold().split()),
    }
    return hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]


class CandidateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._reject_symlinked_path()
        self._lock = _candidate_path_lock(self.path)

    def _reject_symlinked_path(self) -> None:
        if self.path.is_symlink():
            raise ValueError("candidate store file cannot be a symlink")
        parent = self.path.parent
        if any(component.is_symlink() for component in (parent, *parent.parents)):
            raise ValueError("candidate store parent cannot be a symlink")

    def add(self, item: FailureObservation) -> ScenarioCandidate:
        item = FailureObservation.model_validate(item.model_dump())
        candidate = ScenarioCandidate.from_observation(item)
        with self._lock:
            current = {entry.candidate_id: entry for entry in self._read()}
            if candidate.candidate_id in current:
                return current[candidate.candidate_id]
            parent_was_missing = not self.path.parent.exists()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            file_was_missing = not self.path.exists()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(candidate.model_dump_json() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            if parent_was_missing or file_was_missing:
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            return candidate

    def read(self) -> list[ScenarioCandidate]:
        with self._lock:
            return self._read()

    def _read(self) -> list[ScenarioCandidate]:
        self._reject_symlinked_path()
        if not self.path.exists():
            return []
        lines = self.path.read_text().splitlines()
        if any(not line.strip() for line in lines):
            raise ValueError("candidate store cannot contain blank records")
        candidates = [ScenarioCandidate.model_validate_json(line) for line in lines]
        ids = [candidate.candidate_id for candidate in candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate store cannot contain duplicate identities")
        return candidates
