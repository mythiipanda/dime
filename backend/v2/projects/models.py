from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProjectStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    goal: str
    status: ProjectStatus = ProjectStatus.PENDING
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    result: str | None = None
    error: str | None = None
