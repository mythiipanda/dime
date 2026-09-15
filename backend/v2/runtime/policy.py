from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class ExecutionMode(StrEnum):
    LIVE = "live"
    REPLAY = "replay"
    EVAL = "eval"
    SHADOW = "shadow"


class ExecutionPolicy(BaseModel):
    mode: ExecutionMode
    max_concurrency: int = Field(default=4, ge=1, le=16)
    max_failures: int = Field(default=2, ge=1, le=10)
    repair_attempts: int = Field(default=1, ge=0, le=2)
    ledger_dir: Path | None = None
    checkpoint_dir: Path | None = None
    replay_path: Path | None = None
    publish: bool = True

    @model_validator(mode="after")
    def validate_mode(self) -> "ExecutionPolicy":
        if self.mode == ExecutionMode.REPLAY and self.replay_path is None:
            raise ValueError("replay mode requires replay_path")
        if self.mode == ExecutionMode.SHADOW and self.publish:
            raise ValueError("shadow mode cannot publish")
        return self

    @classmethod
    def live(cls, *, ledger_dir: str | Path | None = None) -> "ExecutionPolicy":
        return cls(mode=ExecutionMode.LIVE, ledger_dir=ledger_dir)

    @classmethod
    def shadow(cls, *, ledger_dir: str | Path | None = None) -> "ExecutionPolicy":
        return cls(mode=ExecutionMode.SHADOW, ledger_dir=ledger_dir, publish=False)

    @classmethod
    def evaluation(cls, *, ledger_dir: str | Path | None = None) -> "ExecutionPolicy":
        return cls(mode=ExecutionMode.EVAL, ledger_dir=ledger_dir, publish=False)

    @classmethod
    def replay(cls, path: str | Path) -> "ExecutionPolicy":
        return cls(mode=ExecutionMode.REPLAY, replay_path=path, publish=False)
