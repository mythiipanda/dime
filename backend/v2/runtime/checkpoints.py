from __future__ import annotations

import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from v2.contracts import EvidenceEnvelope, Plan, TaskSpec


_CHECKPOINT_LOCKS_GUARD = Lock()
_CHECKPOINT_LOCKS: dict[Path, Lock] = {}


def _checkpoint_path_lock(path: Path) -> Lock:
    resolved = path.resolve()
    with _CHECKPOINT_LOCKS_GUARD:
        return _CHECKPOINT_LOCKS.setdefault(resolved, Lock())


class ExecutionCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(max_length=256)
    task: TaskSpec
    plan: Plan
    evidence_by_node: dict[str, EvidenceEnvelope] = Field(default_factory=dict, max_length=32)
    attempts: dict[str, StrictInt] = Field(default_factory=dict, max_length=32)
    errors: dict[str, list[str]] = Field(default_factory=dict, max_length=32)

    @model_validator(mode="after")
    def validate_identity(self) -> "ExecutionCheckpoint":
        if not self.run_id.strip():
            raise ValueError("checkpoint run id must be non-empty")
        if any(isinstance(count, bool) or not isinstance(count, int)
               for count in self.attempts.values()):
            raise ValueError("checkpoint attempt counts must be integers")
        if any(len(errors) > 5 for errors in self.errors.values()):
            raise ValueError("checkpoint nodes cannot carry more than 5 errors")
        if any(not error.strip() for errors in self.errors.values() for error in errors):
            raise ValueError("checkpoint errors must be non-empty")
        return self


class CheckpointStore(Protocol):
    def load(self, run_id: str) -> ExecutionCheckpoint | None: ...
    def save(self, checkpoint: ExecutionCheckpoint) -> None: ...
    def delete(self, run_id: str) -> None: ...


class FileCheckpointStore:
    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)
        parent = self._directory.parent
        if any(component.is_symlink() for component in (parent, *parent.parents)):
            raise ValueError("checkpoint directory parent cannot be a symlink")

    def load(self, run_id: str) -> ExecutionCheckpoint | None:
        path = self._path(run_id)
        with _checkpoint_path_lock(path):
            self._reject_symlinked_directory()
            if path.is_symlink():
                raise ValueError("checkpoint file cannot be a symlink")
            if not path.exists():
                return None
            return ExecutionCheckpoint.model_validate_json(path.read_text())

    def save(self, checkpoint: ExecutionCheckpoint) -> None:
        checkpoint = ExecutionCheckpoint.model_validate(checkpoint.model_dump())
        path = self._path(checkpoint.run_id)
        with _checkpoint_path_lock(path):
            self._reject_symlinked_directory()
            self._directory.mkdir(parents=True, exist_ok=True)
            if path.is_symlink():
                raise ValueError("checkpoint file cannot be a symlink")
            fd, temporary = tempfile.mkstemp(dir=self._directory, prefix=".checkpoint-")
            try:
                with os.fdopen(fd, "w") as handle:
                    handle.write(checkpoint.model_dump_json())
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
                self._fsync_directory()
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

    def delete(self, run_id: str) -> None:
        path = self._path(run_id)
        with _checkpoint_path_lock(path):
            self._reject_symlinked_directory()
            if path.is_symlink():
                raise ValueError("checkpoint file cannot be a symlink")
            if not path.exists():
                return
            path.unlink()
            self._fsync_directory()

    def _reject_symlinked_directory(self) -> None:
        if self._directory.is_symlink():
            raise ValueError("checkpoint directory cannot be a symlink")
        parent = self._directory.parent
        if any(component.is_symlink() for component in (parent, *parent.parents)):
            raise ValueError("checkpoint directory parent cannot be a symlink")

    def _fsync_directory(self) -> None:
        directory_fd = os.open(self._directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def _path(self, run_id: str) -> Path:
        if not run_id or any(
            char
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for char in run_id
        ):
            raise ValueError("run_id may contain only letters, numbers, '-' and '_'")
        return self._directory / f"{run_id}.json"
