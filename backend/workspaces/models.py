from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class Workspace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=256)
    owner: str = Field(min_length=1, max_length=256)
    member_thread_ids: list[str] = Field(default_factory=list, max_length=1024)
    member_brief_ids: list[str] = Field(default_factory=list, max_length=1024)
    owner_token_hash: str = Field(default="", max_length=256)
    created_at: datetime
    updated_at: datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
