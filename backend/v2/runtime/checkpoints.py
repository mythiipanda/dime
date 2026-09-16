from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from v2.contracts import EvidenceEnvelope, Plan, TaskSpec


class ExecutionCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    task: TaskSpec
    plan: Plan
    evidence_by_node: dict[str, EvidenceEnvelope] = Field(default_factory=dict)
    attempts: dict[str, int] = Field(default_factory=dict)
    errors: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_identity(self) -> "ExecutionCheckpoint":
        if not self.run_id.strip():
            raise ValueError("checkpoint run id must be non-empty")
        return self


class CheckpointStore(Protocol):
    def load(self, run_id: str) -> ExecutionCheckpoint | None: ...
    def save(self, checkpoint: ExecutionCheckpoint) -> None: ...
    def delete(self, run_id: str) -> None: ...


class FileCheckpointStore:
    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)

    def load(self, run_id: str) -> ExecutionCheckpoint | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        return ExecutionCheckpoint.model_validate_json(path.read_text())

    def save(self, checkpoint: ExecutionCheckpoint) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._path(checkpoint.run_id)
        fd, temporary = tempfile.mkstemp(dir=self._directory, prefix=".checkpoint-")
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(checkpoint.model_dump_json())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            directory_fd = os.open(self._directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def delete(self, run_id: str) -> None:
        self._path(run_id).unlink(missing_ok=True)

    def _path(self, run_id: str) -> Path:
        if not run_id or any(
            char
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for char in run_id
        ):
            raise ValueError("run_id may contain only letters, numbers, '-' and '_'")
        return self._directory / f"{run_id}.json"
