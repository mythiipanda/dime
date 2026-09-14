from __future__ import annotations

from datetime import datetime
from pathlib import Path

from v2.contracts import EvidenceEnvelope
from v2.tests.compatibility.harness import TurnTrace, grade_scenario, load_pack

HERE = Path(__file__).resolve().parent
PACK = HERE / "fixtures" / "scenarios.json"


def evidence(capability: str = "ratings", rows: dict | None = None, **kwargs) -> EvidenceEnvelope:
    return EvidenceEnvelope(
        evidence_id="ev-1", capability=capability, source="fixture",
        observed_at=datetime(2026, 9, 14), rows=rows or {}, **kwargs,
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
    }),), ({"name": "a_new_planner_chosen_tool"},), text="113.8 offense, 114.4 defense, -0.5 net")
    assert grade_scenario(scenario, [turn]).passed


def test_missing_evidence_stays_a_failure():
    scenario = next(s for s in load_pack(PACK)["scenarios"] if s["id"] == "f88-team-ratings")
    result = grade_scenario(scenario, [TurnTrace(1.0, 1, (), ())])
    assert not result.passed
    assert any("missing equivalent evidence" in failure for failure in result.failures)


def test_qualification_is_behavioral_requirement():
    scenario = next(s for s in load_pack(PACK)["scenarios"] if s["id"] == "f88-qualified-3p-leader")
    unqualified = evidence("qualified_leaders", {"player": "Luke Kennard", "3P%": 47.8})
    assert not grade_scenario(scenario, [TurnTrace(1.0, 1, (unqualified,), (), text="Luke Kennard 47.8% on 82+ made threes")]).passed
    qualified = unqualified.model_copy(update={"qualification": "82+ made threes"})
    assert grade_scenario(scenario, [TurnTrace(1.0, 1, (qualified,), (), text="Luke Kennard 47.8% on 82+ made threes")]).passed


def test_latency_and_tool_budgets_are_hard_failures():
    scenario = next(s for s in load_pack(PACK)["scenarios"] if s["id"] == "efficiency-simple")
    result = grade_scenario(scenario, [TurnTrace(20.1, 6, (), (), text="54")])
    assert set(result.failures) == {
        "latency 20.1s > 20s budget", "6 tool calls > 5 budget",
    }
