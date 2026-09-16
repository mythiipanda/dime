from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, TypeAdapter, field_validator, model_validator


class StrictEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def reject_blank_strings(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError("event string fields must be non-empty")
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            if any(not item.strip() for item in value):
                raise ValueError("event string lists must not contain empty values")
            if len(value) != len(set(value)):
                raise ValueError("event string lists must not contain duplicates")
        return value


class EventType(StrEnum):
    NODE_UPDATE = "node_update"
    THOUGHT_STREAM = "thought_stream"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOKEN = "token"
    CUSTOM_DATA = "custom_data"
    FINAL_ANSWER = "final_answer"
    SUGGESTIONS = "suggestions"
    GRAPH_END = "graph_end"


class NodeUpdate(StrictEvent):
    type: Literal[EventType.NODE_UPDATE] = EventType.NODE_UPDATE
    node: Literal["entry", "data_retrieval", "tools", "analytics", "presentation"]
    status: Literal["running", "complete", "error"]


class ThoughtStream(StrictEvent):
    type: Literal[EventType.THOUGHT_STREAM] = EventType.THOUGHT_STREAM
    node: Literal["entry", "data_retrieval", "tools", "analytics", "presentation"]
    text: str = Field(max_length=200_000)


class ToolCall(StrictEvent):
    type: Literal[EventType.TOOL_CALL] = EventType.TOOL_CALL
    node: Literal["entry", "data_retrieval", "tools", "analytics", "presentation"]
    name: str = Field(max_length=256)
    args: dict[str, Any] = Field(default_factory=dict, max_length=64)
    label: str | None = Field(default=None, max_length=1000)
    summary: str | None = Field(default=None, max_length=4000)
    agent: str | None = Field(default=None, max_length=256)


class ToolResult(StrictEvent):
    type: Literal[EventType.TOOL_RESULT] = EventType.TOOL_RESULT
    node: Literal["entry", "data_retrieval", "tools", "analytics", "presentation"]
    name: str = Field(max_length=256)
    status: Literal["ok", "fail"]
    rows: StrictInt | None = Field(default=None, ge=0)
    ms: StrictInt | None = Field(default=None, ge=0)
    error: str | None = Field(default=None, max_length=4000)
    summary: str | None = Field(default=None, max_length=4000)
    sql: str | None = Field(default=None, max_length=100_000)
    agent: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def validate_status(self):
        if self.status == "ok" and self.error is not None:
            raise ValueError("successful tool result cannot carry an error")
        if self.status == "fail" and self.error is None:
            raise ValueError("failed tool result requires an error")
        return self


class Token(StrictEvent):
    type: Literal[EventType.TOKEN] = EventType.TOKEN
    text: str = Field(max_length=200_000)


class CustomData(StrictEvent):
    type: Literal[EventType.CUSTOM_DATA] = EventType.CUSTOM_DATA
    node: Literal["entry", "data_retrieval", "tools", "analytics", "presentation"]
    tables: list[dict[str, Any]] = Field(default_factory=list, max_length=32)
    unverified_numbers: list[str] = Field(default_factory=list, max_length=128)


class FinalAnswer(StrictEvent):
    type: Literal[EventType.FINAL_ANSWER] = EventType.FINAL_ANSWER
    text: str = Field(max_length=200_000)
    carry: dict[str, Any] | None = Field(default=None, max_length=64)


class Suggestions(StrictEvent):
    type: Literal[EventType.SUGGESTIONS] = EventType.SUGGESTIONS
    items: list[str] = Field(default_factory=list, max_length=16)


class GraphEnd(StrictEvent):
    type: Literal[EventType.GRAPH_END] = EventType.GRAPH_END


InternalEvent = Annotated[
    NodeUpdate
    | ThoughtStream
    | ToolCall
    | ToolResult
    | Token
    | CustomData
    | FinalAnswer
    | Suggestions
    | GraphEnd,
    Field(discriminator="type"),
]

EVENT_ADAPTER = TypeAdapter(InternalEvent)
