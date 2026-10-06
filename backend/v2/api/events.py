
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, TypeAdapter, field_validator, model_validator

PUBLIC_EVENT_DATA_FIELDS: dict[str, tuple[str, ...]] = {
    "stage_summary": ("mode", "season", "entity_count", "requirement_count",
                      "calculation_count"),
    "plan_update": ("node_count", "capabilities", "unknown_capability_count"),
    "tool_call": ("name", "arguments", "argument_count", "unknown_argument_count"),
    "tool_result": ("name", "rows"),
    "evidence_update": ("capability", "season", "as_of", "observed_at", "rows",
                        "qualification", "coverage", "warning_count"),
    "verification_update": ("round", "supported_count", "claim_count",
                            "missing_count", "contradiction_count", "repair_count"),
}

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
    STATUS = "status"
    THOUGHT_STREAM = "thought_stream"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOKEN = "token"
    CUSTOM_DATA = "custom_data"
    WORK_LOG = "work_log"
    FINAL_ANSWER = "final_answer"
    SUGGESTIONS = "suggestions"
    GRAPH_END = "graph_end"
    BINDING_DIAGNOSTIC = "binding_diagnostic"
    RUN_DIAGNOSTIC = "run_diagnostic"

class NodeUpdate(StrictEvent):
    type: Literal[EventType.NODE_UPDATE] = EventType.NODE_UPDATE
    node: Literal["entry", "data_retrieval", "tools", "analytics", "presentation"]
    status: Literal["running", "complete", "error"]

class ThoughtStream(StrictEvent):
    type: Literal[EventType.THOUGHT_STREAM] = EventType.THOUGHT_STREAM
    node: Literal["entry", "data_retrieval", "tools", "analytics", "presentation"]
    text: str = Field(max_length=200_000)

class StatusUpdate(StrictEvent):
    type: Literal[EventType.STATUS] = EventType.STATUS
    text: str = Field(max_length=500)

class ToolCall(StrictEvent):
    event_id: str | None = None
    sequence: StrictInt | None = Field(default=None, ge=1)
    emitted_at: str | None = None
    phase: str | None = None
    correlation_id: str | None = None
    transition: str | None = None
    status: str | None = None
    duration_ms: StrictInt | None = Field(default=None, ge=0)
    data: dict[str, Any] = Field(default_factory=dict)
    type: Literal[EventType.TOOL_CALL] = EventType.TOOL_CALL
    node: Literal["entry", "data_retrieval", "tools", "analytics", "presentation"]
    name: str = Field(max_length=256)
    label: str | None = Field(default=None, max_length=1000)
    summary: str | None = Field(default=None, max_length=4000)
    agent: str | None = Field(default=None, max_length=256)

class ToolResult(StrictEvent):
    event_id: str | None = None
    sequence: StrictInt | None = Field(default=None, ge=1)
    emitted_at: str | None = None
    phase: str | None = None
    correlation_id: str | None = None
    transition: str | None = None
    duration_ms: StrictInt | None = Field(default=None, ge=0)
    data: dict[str, Any] = Field(default_factory=dict)
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

class WorkLog(StrictEvent):
    type: Literal[EventType.WORK_LOG] = EventType.WORK_LOG
    run_id: str = Field(pattern=r"^run-[0-9a-f]{32}$")
    status: Literal["complete", "partial"]

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

class BindingDiagnostic(StrictEvent):
    type: Literal[EventType.BINDING_DIAGNOSTIC] = EventType.BINDING_DIAGNOSTIC
    run_id: str = Field(max_length=256)
    claim_index: StrictInt = Field(ge=0)
    requirement_kind: str = Field(max_length=64)
    requirement_id: str | None = Field(default=None, max_length=64)
    output_id: str = Field(max_length=256)
    node_id: str | None = Field(default=None, max_length=256)
    evidence_id: str | None = Field(default=None, max_length=256)
    selector: str | None = Field(default=None, max_length=512)
    row_selector: str | None = Field(default=None, max_length=512)
    subject_selector: str | None = Field(default=None, max_length=512)
    subject_entity_type: str | None = Field(default=None, max_length=64)
    subject_entity_id: str | None = Field(default=None, max_length=256)
    declared_value: dict[str, Any] = Field(default_factory=dict, max_length=8)
    declared_unit: dict[str, Any] | None = Field(default=None, max_length=8)
    domain: str | None = Field(default=None, max_length=256)
    evidence_capability: str | None = Field(default=None, max_length=256)
    reanchor_changed: StrictBool
    rejection: str = Field(max_length=512)

class RunDiagnostic(StrictEvent):
    type: Literal[EventType.RUN_DIAGNOSTIC] = EventType.RUN_DIAGNOSTIC
    run_id: str = Field(max_length=256)
    error_type: str = Field(max_length=256)
    message: str = Field(max_length=4000)
    last_stage: str | None = Field(default=None, max_length=256)

class ReplayVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(max_length=256)
    status: Literal["verified", "mismatch"]
    turn_count: StrictInt = Field(ge=0)
    item_count: StrictInt = Field(ge=0)
    content_hashes: dict[str, str] = Field(max_length=256)
    mismatched_turn: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def validate_replay(self) -> "ReplayVerification":
        if not self.run_id.strip():
            raise ValueError("replay run id must be non-empty")
        for turn_id, digest in self.content_hashes.items():
            if not turn_id.strip():
                raise ValueError("replay turn ids must be non-empty")
            if len(digest) != 64 or any(
                char not in "0123456789abcdef" for char in digest
            ):
                raise ValueError("replay content hashes must be lowercase sha256")
        if self.status == "verified" and self.mismatched_turn is not None:
            raise ValueError("verified replay cannot name a mismatched_turn")
        if self.status == "mismatch" and (
            self.mismatched_turn is None or not self.mismatched_turn.strip()
        ):
            raise ValueError("mismatched replay must name its mismatched_turn")
        return self

def replay_verification_for(run_id: str, thread) -> ReplayVerification:
    return ReplayVerification(
        run_id=run_id, status="verified", turn_count=len(thread.turns),
        item_count=sum(len(turn.items) for turn in thread.turns),
        content_hashes={
            turn.turn_id: turn.content_hash for turn in thread.turns
        })

def replay_mismatch_report(run_id: str, turn_id: str) -> ReplayVerification:
    if not turn_id.strip():
        raise ValueError("mismatched turn must be non-empty")
    return ReplayVerification(
        run_id=run_id, status="mismatch", turn_count=0, item_count=0,
        content_hashes={}, mismatched_turn=turn_id)

from v2.api.activity import StageData, PlanData, EvidenceData, VerificationData
class ActivityBase(StrictEvent):
    event_id: str = Field(pattern=r'^[A-Za-z0-9_-]+:\d+$')
    sequence: StrictInt = Field(ge=1)
    emitted_at: str
    phase: Literal["understand","plan","execute","verify"]
    status: Literal["running","complete","failed","pass","partial","repair"]
    title: Literal["Request understood","Plan accepted","Evidence admitted","Evidence rejected","Verification updated"]
    correlation_id: str | None = Field(default=None, pattern=r'^activity-\d+$')
    transition: Literal["started","completed","failed","succeeded","admitted","rejected","snapshot"]
    duration_ms: StrictInt | None = Field(default=None, ge=0)
class StageSummary(ActivityBase):
    type: Literal["stage_summary"]
    data: StageData
class PlanUpdate(ActivityBase):
    type: Literal["plan_update"]
    data: PlanData
class EvidenceUpdate(ActivityBase):
    type: Literal["evidence_update"]
    data: EvidenceData
class VerificationUpdate(ActivityBase):
    type: Literal["verification_update"]
    data: VerificationData
ActivityUpdate = StageSummary | PlanUpdate | EvidenceUpdate | VerificationUpdate

InternalEvent = Annotated[
    StageSummary
    | PlanUpdate
    | EvidenceUpdate
    | VerificationUpdate
    | NodeUpdate
    | StatusUpdate
    | ThoughtStream
    | ToolCall
    | ToolResult
    | Token
    | WorkLog
    | CustomData
    | FinalAnswer
    | Suggestions
    | GraphEnd
    | BindingDiagnostic
    | RunDiagnostic,
    Field(discriminator="type"),
]

EVENT_ADAPTER = TypeAdapter(InternalEvent)
