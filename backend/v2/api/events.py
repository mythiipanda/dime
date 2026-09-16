from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class StrictEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    node: str
    status: Literal["running", "complete", "failed"]


class ThoughtStream(StrictEvent):
    type: Literal[EventType.THOUGHT_STREAM] = EventType.THOUGHT_STREAM
    node: str
    text: str


class ToolCall(StrictEvent):
    type: Literal[EventType.TOOL_CALL] = EventType.TOOL_CALL
    node: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    label: str | None = None
    summary: str | None = None
    agent: str | None = None


class ToolResult(StrictEvent):
    type: Literal[EventType.TOOL_RESULT] = EventType.TOOL_RESULT
    node: str
    name: str
    status: Literal["ok", "fail"]
    rows: int | None = Field(default=None, ge=0)
    ms: int | None = Field(default=None, ge=0)
    error: str | None = None
    summary: str | None = None
    sql: str | None = None
    agent: str | None = None


class Token(StrictEvent):
    type: Literal[EventType.TOKEN] = EventType.TOKEN
    text: str


class CustomData(StrictEvent):
    type: Literal[EventType.CUSTOM_DATA] = EventType.CUSTOM_DATA
    node: str
    tables: list[dict[str, Any]] = Field(default_factory=list)
    unverified_numbers: list[str] = Field(default_factory=list)


class FinalAnswer(StrictEvent):
    type: Literal[EventType.FINAL_ANSWER] = EventType.FINAL_ANSWER
    text: str
    carry: dict[str, Any] | None = None


class Suggestions(StrictEvent):
    type: Literal[EventType.SUGGESTIONS] = EventType.SUGGESTIONS
    items: list[str] = Field(default_factory=list)


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
