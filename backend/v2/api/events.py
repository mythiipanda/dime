"""The public SSE event contract.

Every line the chat stream emits is `event: <type>` followed by `data: <json>`.
The object after `data:` is the public projection of an internal event, built
by `v2.api.routes._safe_buffered_event` and encoded by `v2.api.sse.encode_event`.
A client may rely on exactly the fields listed here, may skip a field it does
not recognise, and must never assume a field is present: the encoder drops
null values. Nothing outside this list is guaranteed, so a field may be added
without a version bump and a client must not break on one. Nothing here is
allowed to carry a secret, an internal id, a prompt, a file path, a row payload,
a source name or an exception message.

Lifecycle fields the typed events share:

    `event_id`     stable identity for this event, `<run_id>:<sequence>`.
    `sequence`     1-based position in the run, contiguous and gap-free.
    `emitted_at`   ISO-8601 UTC instant the event was written.
    `phase`        `understand`, `plan`, `execute` or `verify`.
    `status`       `running`, `complete`, `failed`, `pass`, `partial` or
                   `repair`, narrowed per event below.
    `title`        short human label for the event, safe to render verbatim.
    `correlation_id` links the events of one step, such as a tool_call and the
                   tool_result it produced. Absent when the event has no step.
    `transition`   `started`, `completed`, `failed`, `succeeded`, `admitted`,
                   `rejected` or `snapshot`.
    `duration_ms`  wall time of the step, non-negative, absent while running.

Events the chat stream emits:

    `node_update`  `node` is `entry`, `data_retrieval`, `tools`, `analytics`
                   or `presentation`; `status` is `running`, `complete` or
                   `error`. No `data` and nothing else is published.
    `status`       `text`, at most 500 characters, safe to render verbatim.
    `tool_call`    `node` is always `tools`; `name` is the capability id, or
                   the literal `tool` when the capability is not in the public
                   registry; `data` carries exactly the keys listed for
                   `tool_call` under `PUBLIC_EVENT_DATA_FIELDS`, documented
                   below. Step identity, the node id and the capability label
                   are not published, so `tool_call` and `tool_result` carry
                   no `event_id`, `sequence`, `emitted_at`, `phase`, `status`,
                   `correlation_id`, `transition`, `duration_ms` or `label`;
                   the four typed activity events are where a client reads
                   step identity from.
    `tool_result`  `node` is always `tools`; `name` as above; `status` is `ok`
                   or `fail`; `error` appears only on `fail` and is always the
                   fixed string `Tool failed`, never an exception message. Row
                   counts, durations, row payloads, sql, evidence ids and
                   source names are not published.
    `stage_summary` `data` keys per `PUBLIC_EVENT_DATA_FIELDS`: `mode`,
                   `season`, `entity_count`, `requirement_count` and
                   `calculation_count`, all counts safe to render.
    `plan_update`  `data` keys: `capabilities`, the ordered capability ids the
                   plan selected, and `node_count`, the plan's node count, plus
                   `unknown_capability_count`, how many selected ids are not in
                   the public registry.
    `evidence_update` `data` keys: `capability`, `season`, `as_of`, `observed_at`,
                   `rows`, `qualification` and `coverage`, each `present` or
                   `missing`, and `warning_count`. Evidence ids and row
                   payloads are never published.
    `verification_update` `data` keys: `round` and the claim counters
                   `supported_count`, `claim_count`, `missing_count`,
                   `contradiction_count` and `repair_count`.
    `custom_data`  `node`, `tables` and `unverified_numbers`. A `tables` row is
                   an output: `output_id`, `display_name`, `subject_type`,
                   `subject_id`, `value`, `unit` and `provenance`, or
                   `output_id`, `display_name`, `input_value` and `provenance`
                   when the value came from a calculation input.
                   `provenance` carries `capability`, `origin` (`declared` or
                   `undeclared`), `warehouse_id`, `season`, `as_of` and
                   `live_sources`. Node ids, evidence ids and row selectors
                   are not published.
    `work_log`     `run_id` and `status`, which is `complete` only when every
                   claim verified and `partial` otherwise.
    `final_answer` `text` is the answer to render. `carry` carries `run_id`,
                   `verification`, `verified_claims`, `output_statuses`,
                   `structural_flags`, `gaps` and `stage_latencies_ms`.
    `graph_end`    empty object, and always the last event of the stream.
    `ping`         empty object with `ok` true. A keepalive between chunks; a
                   client must ignore it.

`error` and `run_diagnostic` are the only stream events tied to a failed run.
`error` appears once, carries `message` and `run_id`, and is followed by
`graph_end`. `run_diagnostic` appears only when the request asked for
diagnostics and carries `run_id`, `error_type`, `message` and `last_stage`.
`binding_diagnostic` appears only on request for diagnostics and carries the
binding adjudication for one claim: `run_id`, `claim_index`,
`requirement_kind`, `requirement_id`, `output_id`, `node_id`, `evidence_id`,
`selector`, `row_selector`, `subject_selector`, `subject_entity_type`,
`subject_entity_id`, `declared_value`, `declared_unit`, `domain`,
`evidence_capability`, `reanchor_changed` and `rejection`.

The remaining models in this module, `thought_stream`, `token` and
`suggestions`, are part of the internal vocabulary; the chat stream does not
emit them, and a client must not wait for them.

The `tool_call` `data` object, field by field:

    `name`      the capability id, identical to the event `name`.

    `arguments`
        an ordered list of `{name, value}` for the arguments the tool was
        actually invoked with, ascending by `name`. `value` is a string,
        boolean, integer, finite float, null, or a list of those. An argument
        the capability does not declare, one whose name marks it as internal
        identity or as a secret, prompt or filesystem path, and one whose value
        is not a JSON scalar or a list of JSON scalars are all withheld, so
        `arguments` may be shorter than `argument_count`. A withheld argument
        is absent from the list rather than redacted in place.

    `argument_count`
        how many arguments the call carried, withheld ones included.

    `unknown_argument_count`
        how many of those the capability does not declare, so a subset count.
        It is at most `argument_count`, and the two are equal only when every
        argument is undeclared.

"""

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
