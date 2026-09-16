from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from v2.contracts import EvidenceEnvelope, VerificationReport
from v2.tests.compatibility.harness import TurnTrace, grade_scenario, load_pack

HERE = Path(__file__).resolve().parent
PACK = HERE / "fixtures" / "scenarios.json"


def evidence(capability: str = "ratings", rows: dict | None = None, **kwargs) -> EvidenceEnvelope:
    return EvidenceEnvelope(
        evidence_id="ev-1", capability=capability, source="fixture",
        observed_at=datetime(2026, 9, 14, tzinfo=UTC), rows=rows or {}, **kwargs,
    )


def test_pack_freezes_all_35_scenarios():
    pack = load_pack(PACK)
    assert len(pack["scenarios"]) == 35
    assert pack["version"] == 3


def test_old_routing_pins_are_removed():
    pack = load_pack(PACK)
    assert all("trajectory" not in scenario for scenario in pack["scenarios"])
    formerly_pinned = [scenario for scenario in pack["scenarios"] if "routing" in scenario.get("tags", [])]
    assert formerly_pinned
    assert all("evidence_requirement" in scenario for scenario in formerly_pinned)


def test_grades_equivalent_evidence_not_tool_name():
    scenario = next(s for s in load_pack(PACK)["scenarios"] if s["id"] == "f88-team-ratings")
    turn = TurnTrace(1.0, 1, (evidence("team_ratings", {
        "offense": 113.8, "defense": 114.4, "net": -0.5,
    }),), ({"call_id": "call", "name": "a_new_planner_chosen_tool"},),
        report=VerificationReport(status="pass"), text="113.8 offense, 114.4 defense, -0.5 net")
    assert grade_scenario(scenario, [turn]).passed


def test_missing_evidence_stays_a_failure():
    scenario = next(s for s in load_pack(PACK)["scenarios"] if s["id"] == "f88-team-ratings")
    result = grade_scenario(scenario, [TurnTrace(
        1.0, 1, (), ({"call_id": "call", "name": "tool"},), report=VerificationReport(status="pass"))])
    assert not result.passed
    assert any("missing equivalent evidence" in failure for failure in result.failures)


def test_qualification_is_behavioral_requirement():
    scenario = next(s for s in load_pack(PACK)["scenarios"] if s["id"] == "f88-qualified-3p-leader")
    unqualified = evidence("qualified_leaders", {"player": "Luke Kennard", "3P%": 47.8})
    assert not grade_scenario(scenario, [TurnTrace(1.0, 1, (unqualified,), ({"call_id": "call", "name": "tool"},),
        report=VerificationReport(status="pass"), text="Luke Kennard 47.8% on 82+ made threes")]).passed
    qualified = unqualified.model_copy(update={"qualification": "82+ made threes"})
    assert grade_scenario(scenario, [TurnTrace(1.0, 1, (qualified,), ({"call_id": "call", "name": "tool"},),
        report=VerificationReport(status="pass"), text="Luke Kennard 47.8% on 82+ made threes")]).passed


def test_latency_and_tool_budgets_are_hard_failures():
    scenario = next(s for s in load_pack(PACK)["scenarios"] if s["id"] == "efficiency-simple")
    result = grade_scenario(scenario, [TurnTrace(20.1, 6, (), tuple({"call_id": str(i), "name": str(i)} for i in range(6)), report=VerificationReport(status="pass"), text="54")])
    assert set(result.failures) == {
        "latency 20.1s > 20s budget", "6 tool calls > 5 budget",
    }


def test_global_banned_text_is_enforced():
    scenario = next(s for s in load_pack(PACK)["scenarios"]
                    if s["id"] == "efficiency-simple")
    result = grade_scenario(
        scenario, [TurnTrace(1.0, 1, (), ({"call_id": "call", "name": "tool"},), report=VerificationReport(status="pass"),
                             text="Try a narrower warehouse query")])
    assert not result.passed
    assert any("contains banned text" in failure for failure in result.failures)


def test_multi_turn_scenario_requires_expectation_for_every_turn():
    scenario = {
        "id": "chain",
        "chain": ["first", "second"],
        "expect_turns": [{"contains": ["first"]}],
    }
    turns = [
        TurnTrace(1.0, 0, (), (), report=VerificationReport(status="pass"), text="first"),
        TurnTrace(1.0, 0, (), (), report=VerificationReport(status="pass"), text="anything passes if ungraded"),
    ]
    result = grade_scenario(scenario, turns)
    assert result.failures == ("expected 2 turn expectations, got 1",)


def test_scenario_requires_clean_verification_for_every_turn():
    scenario = {"id": "verified", "chain": ["q"], "expect": {}}
    missing = grade_scenario(scenario, [TurnTrace(1.0, 0, (), ())])
    partial = grade_scenario(scenario, [TurnTrace(
        1.0, 0, (), (), report=VerificationReport(status="partial"))])
    assert missing.failures == ("T1: missing verification report",)
    assert partial.failures == ("T1: verifier status is partial",)


@pytest.mark.parametrize("seconds,tool_calls,tools,error", [
    (-1.0, 0, (), "seconds"),
    (float("nan"), 0, (), "seconds"),
    (1.0, -1, (), "tool_calls"),
    (1.0, 1, (), "match recorded tools"),
])
def test_turn_trace_rejects_impossible_metrics(seconds, tool_calls, tools, error):
    import pytest
    with pytest.raises(ValueError, match=error):
        TurnTrace(seconds, tool_calls, (), tools)


def test_turn_trace_rejects_duplicate_evidence_and_tool_identities():
    item = evidence()
    with pytest.raises(ValueError, match="evidence ids must be unique"):
        TurnTrace(1.0, 0, (item, item), ())
    tools = ({"call_id": "same", "name": "a"},
             {"call_id": "same", "name": "b"})
    with pytest.raises(ValueError, match="call ids must be unique"):
        TurnTrace(1.0, 2, (), tools)


@pytest.mark.parametrize("change,error", [
    ({"version": 2}, "unsupported.*version"),
    ({"notes": " "}, "notes must be non-empty"),
    ({"banned_everywhere": ["same", "same"]}, "banned text"),
    ({"invented": True}, "top-level fields"),
])
def test_pack_rejects_malformed_top_level_contract(tmp_path, change, error):
    import json
    payload = json.loads(PACK.read_text())
    payload.update(change)
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=error):
        load_pack(path)


@pytest.mark.parametrize("scenario,error", [
    ("not-an-object", "scenarios must be objects"),
    ({"id": " ", "chain": ["q"], "expect": {}}, "id must be non-empty"),
    ({"id": "x", "chain": [], "expect": {}}, "non-empty text chain"),
    ({"id": "x", "chain": ["q"]}, "exactly one expectation form"),
    ({"id": "x", "chain": ["q"], "expect": {}, "expect_turns": [{}]},
     "exactly one expectation form"),
    ({"id": "x", "chain": ["q", "followup"], "expect_turns": [{}]},
     "expectations must match"),
])
def test_pack_rejects_malformed_scenario_contract(tmp_path, scenario, error):
    import json
    payload = json.loads(PACK.read_text())
    payload["scenarios"][0] = scenario
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=error):
        load_pack(path)
