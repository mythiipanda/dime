from __future__ import annotations

import pytest
from pydantic import ValidationError

from v2.api import events as events_module
from v2.api.activity import (
    EvidenceData,
    PlanData,
    PublicArgument,
    StageData,
    ToolCallData,
    ToolResultData,
    VerificationData,
)
from v2.api.events import (
    PUBLIC_EVENT_DATA_FIELDS,
    BindingDiagnostic,
    CustomData,
    EvidenceUpdate,
    FinalAnswer,
    GraphEnd,
    NodeUpdate,
    PlanUpdate,
    RunDiagnostic,
    StageSummary,
    StatusUpdate,
    ToolCall,
    ToolResult,
    VerificationUpdate,
    WorkLog,
)

DATA_MODELS = {
    "stage_summary": StageData,
    "plan_update": PlanData,
    "tool_call": ToolCallData,
    "tool_result": ToolResultData,
    "evidence_update": EvidenceData,
    "verification_update": VerificationData,
}
EMITTED_EVENTS = (
    NodeUpdate, StatusUpdate, ToolCall, ToolResult, StageSummary, PlanUpdate,
    EvidenceUpdate, VerificationUpdate, CustomData, WorkLog, FinalAnswer,
    GraphEnd, BindingDiagnostic, RunDiagnostic,
)
RESERVED_FIELDS = {
    "ToolCall": ("event_id", "sequence", "emitted_at", "phase", "status",
                 "correlation_id", "transition", "duration_ms", "label",
                 "summary", "agent"),
    "ToolResult": ("event_id", "sequence", "emitted_at", "phase",
                   "correlation_id", "transition", "duration_ms", "rows",
                   "ms", "summary", "agent", "sql"),
}


def test_documented_data_fields_match_every_documented_model():
    assert set(PUBLIC_EVENT_DATA_FIELDS) == set(DATA_MODELS)
    for kind, documented in PUBLIC_EVENT_DATA_FIELDS.items():
        assert set(documented) == set(DATA_MODELS[kind].model_fields), kind


def test_tool_call_data_publishes_scalar_and_scalar_list_values():
    assert ToolCallData.model_fields["arguments"].annotation == list[PublicArgument]
    assert set(PublicArgument.model_fields) == {"name", "value"}
    for value in (None, True, 3, -1.5, "2025-26", [], ["a", "b"], [1, 2]):
        published = ToolCallData(
            name="standings", argument_count=1, unknown_argument_count=0,
            arguments=[{"name": "season", "value": value}])
        assert published.arguments[0].value == value


def test_tool_call_data_refuses_arguments_it_cannot_publish():
    for value in ({"nested": 1}, object(), 1.5 + 2j, [[1]], [1, {"nested": 1}]):
        with pytest.raises(ValidationError):
            ToolCallData(name="standings", argument_count=1,
                         unknown_argument_count=0,
                         arguments=[{"name": "season", "value": value}])
    with pytest.raises(ValidationError):
        ToolCallData(name="standings", argument_count=0, unknown_argument_count=0,
                     arguments=[{"name": "a b", "value": "x"}])
    with pytest.raises(ValidationError):
        ToolCallData(name="standings", argument_count=0, unknown_argument_count=0,
                     arguments=[{"name": "a", "secret": "x"}])
    with pytest.raises(ValidationError):
        ToolCallData(name="standings", argument_count=0, unknown_argument_count=0,
                     arguments="season=2025-26")


def test_public_event_contract_documents_every_published_field():
    document = events_module.__doc__
    for model in EMITTED_EVENTS:
        reserved = set(RESERVED_FIELDS.get(model.__name__, ()))
        for field in model.model_fields:
            if field == "type" or field in reserved:
                continue
            assert f"`{field}`" in document, f"{model.__name__}.{field}"
    for kind, documented in PUBLIC_EVENT_DATA_FIELDS.items():
        for field in documented:
            assert f"`{field}`" in document, f"{kind}.{field}"


def test_reserved_event_fields_are_reserved_on_the_model():
    for model in EMITTED_EVENTS:
        reserved = set(RESERVED_FIELDS.get(model.__name__, ()))
        assert reserved <= set(model.model_fields), model.__name__


def test_public_event_contract_documents_the_ping_and_failure_frames():
    document = events_module.__doc__
    for token in ("ping", "error", "run_diagnostic", "binding_diagnostic",
                  "graph_end", "ok", "message", "run_id", "Tool failed"):
        assert f"`{token}`" in document, token
