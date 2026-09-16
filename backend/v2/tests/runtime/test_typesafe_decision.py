import builtins
from types import SimpleNamespace as Answer

import pytest

from app.config import Settings
from v2.decision import (
    build_optional_jev_layer,
    DecisionAuditLog,
    DecisionThresholds,
    JevDecisionLayer,
    TypeSafeClientAdapter,
    UNRESOLVED,
)


def choice(**values):
    return values


def noul(**values):
    return values


class Client:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def evaluate(self, state, questions):
        self.calls.append((state, questions))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def picked(value, confidence=1.0):
    return Answer(choice=value, confidence=confidence, probabilities={value: confidence})


def test_evidence_filter_preserves_enumerated_order_and_ids():
    client = Client(Answer(answers={"e1": Answer(noul=.8), "e2": Answer(noul=.2)}))
    layer = JevDecisionLayer(client, choice=choice, noul=noul)
    assert layer.filter_evidence(goal="trade", candidates={
        "e1": {"coverage": "player value"}, "e2": {"coverage": "standings"},
    }) == ("e1",)


def test_eval_judge_abstains_below_its_class_threshold():
    client = Client(Answer(answers={"answer": picked("pass", .49)}))
    layer = JevDecisionLayer(client, choice=choice, noul=noul)
    assert layer.judge_eval(expectation={}, result={}).value == UNRESOLVED


def test_model_route_falls_back_to_strongest_without_guessing():
    client = Client(Answer(answers={"answer": picked(UNRESOLVED, .99)}))
    layer = JevDecisionLayer(client, choice=choice, noul=noul)
    assert layer.route_model(
        stage={"route": "synthesis"}, routes={"fast": "fast", "strong": "strong"},
        strongest="strong",
    ).value == "strong"


def test_tool_choice_is_two_pass_and_loads_only_selected_schema():
    client = Client(
        Answer(answers={"answer": picked("trade_value", .8)}),
        Answer(answers={
            "outgoing": picked("Jaylen Brown", .9),
            "incoming": picked("Paul George", .9),
        }),
    )
    layer = JevDecisionLayer(client, choice=choice, noul=noul)
    result = layer.choose_tool(
        state={"season": "2025-26"}, tools={"trade_value": "two-sided value"},
        argument_candidates=lambda selected: {
            "outgoing": ("Which outgoing player?", {"Jaylen Brown": "resolved"}),
            "incoming": ("Which incoming player?", {"Paul George": "resolved"}),
        } if selected == "trade_value" else {},
    )
    assert result is not None
    assert set(client.calls[0][1]) == {"answer"}
    assert set(client.calls[1][1]) == {"outgoing", "incoming"}


def test_tool_choice_blocks_duplicate_role_values():
    client = Client(
        Answer(answers={"answer": picked("compare", .8)}),
        Answer(answers={
            "outgoing": picked("Jaylen Brown", .9),
            "incoming": picked("Jaylen Brown", .9),
        }),
    )
    layer = JevDecisionLayer(client, choice=choice, noul=noul)
    assert layer.choose_tool(
        state={}, tools={"compare": "compare"},
        argument_candidates=lambda _tool: {
            "outgoing": ("Outgoing?", {"Jaylen Brown": "resolved"}),
            "incoming": ("Incoming?", {"Jaylen Brown": "resolved"}),
        },
    ) is None


def test_tool_choice_blocks_unresolved_argument():
    client = Client(
        Answer(answers={"answer": picked("compare", .8)}),
        Answer(answers={"incoming": picked(UNRESOLVED, 1)}),
    )
    layer = JevDecisionLayer(client, choice=choice, noul=noul)
    assert layer.choose_tool(
        state={}, tools={"compare": "compare"},
        argument_candidates=lambda _tool: {
            "incoming": ("Which incoming player?", {"Paul George": "resolved"})
        },
    ) is None


def test_timeout_falls_back_without_exposing_upstream_detail():
    audit = []
    layer = JevDecisionLayer(
        Client(TimeoutError("secret upstream body")), choice=choice, noul=noul,
        audit=lambda kind, data: audit.append((kind, data)),
    )
    decision = layer.judge_eval(expectation={}, result={})
    assert decision.value == UNRESOLVED
    assert audit == [("eval_judgment", {"status": "failed", "error": "TimeoutError"})]


def test_unavailable_read_only_helpers_preserve_current_path():
    candidates = {"e1": {"coverage": "value"}}
    assert JevDecisionLayer(
        Client(TimeoutError()), choice=choice, noul=noul,
    ).filter_evidence(goal="trade", candidates=candidates) == ("e1",)
    assert JevDecisionLayer(
        Client(TimeoutError()), choice=choice, noul=noul,
    ).result_satisfied(step={}, result={}) is True


def test_result_satisfaction_uses_calibrated_probability():
    layer = JevDecisionLayer(
        Client(Answer(answers={"satisfied": Answer(noul=.31)})),
        choice=choice, noul=noul,
    )
    assert layer.result_satisfied(step={}, result={}) is True


@pytest.mark.parametrize("field", [
    "evidence", "eval_judgment", "model_route", "tool", "argument",
    "satisfaction",
])
def test_thresholds_validate_each_class(field):
    with pytest.raises(ValueError, match="between 0 and 1"):
        DecisionThresholds(**{field: 1.1})


def test_jev_config_is_disabled_by_default(monkeypatch):
    for name in (
        "DIME_JEV_ENABLED", "TYPESAFE_API_KEY", "TYPESAFE_MODEL",
        "TYPESAFE_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.dime_jev_enabled is False
    assert settings.typesafe_api_key == ""
    assert settings.typesafe_model == "jev-1.13.0"
    assert settings.typesafe_timeout_seconds == 2.0


def test_adapter_imports_optional_sdk_only_when_constructed(monkeypatch):
    original_import = builtins.__import__

    def missing_sdk(name, *args, **kwargs):
        if name == "typesafe_sdk":
            raise ImportError("not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_sdk)
    with pytest.raises(RuntimeError, match="private package index"):
        TypeSafeClientAdapter(api_key="test-key")


def test_disabled_factory_does_not_import_optional_sdk(monkeypatch):
    original_import = builtins.__import__

    def fail_sdk_import(name, *args, **kwargs):
        if name == "typesafe_sdk":
            raise AssertionError("disabled path imported optional SDK")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_sdk_import)
    assert build_optional_jev_layer(enabled=False, api_key="") is None


def test_shadow_audit_log_contains_only_sanitized_outcome(tmp_path):
    path = tmp_path / "jev.jsonl"
    audit = DecisionAuditLog(path)
    layer = JevDecisionLayer(
        Client(RuntimeError("private state")), choice=choice, noul=noul,
        audit=audit,
    )
    assert layer.judge_eval(expectation={"secret": "a"}, result={}).value == UNRESOLVED
    assert path.read_text() == (
        '{"error": "RuntimeError", "kind": "eval_judgment", "status": "failed"}\n'
    )
