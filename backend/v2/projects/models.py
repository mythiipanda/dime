from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(max_length=64)
    goal: str = Field(max_length=2000)
    status: ProjectStatus = ProjectStatus.PENDING
    run_id: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    result: str | None = Field(default=None, max_length=200_000)
    error: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_state(self) -> "Project":
        if not self.id.strip() or not self.goal.strip() or not self.run_id.strip():
            raise ValueError("project identity and goal must be non-empty")
        if self.run_id != f"project-{self.id}":
            raise ValueError("project run id must match project identity")
        if self.created_at.utcoffset() is None or self.updated_at.utcoffset() is None:
            raise ValueError("project timestamps must include timezone")
        if self.updated_at < self.created_at:
            raise ValueError("project updated_at cannot precede created_at")
        if self.status == ProjectStatus.COMPLETE:
            if self.result is None or not self.result.strip() or self.error is not None:
                raise ValueError("completed project requires result and no error")
        elif self.status == ProjectStatus.FAILED:
            if self.error is None or not self.error.strip() or self.result is not None:
                raise ValueError("failed project requires error and no result")
        elif self.result is not None or self.error is not None:
            raise ValueError("nonterminal project cannot carry result or error")
        return self
