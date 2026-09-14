"""Hermetic tests for the benchmark pack: scenario-file integrity and
the assertion engine on fabricated transcripts. No network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from assertions import (  # noqa: E402
    check_budget,
    check_text,
    check_trajectory,
    evaluate_scenario,
    load_pack,
)


def test_scenarios_json_is_valid():
    pack = load_pack(Path(__file__).resolve().parent / "scenarios.json")
    assert len(pack["scenarios"]) >= 8


def test_check_text_contains_and_banned():
    fails = check_text("Atlanta Hawks lead with 2462 total AST.",
                       {"contains": ["2462", "Atlanta"]},
                       ["warehouse"])
    assert fails == []
    fails = check_text("Try a narrower ask.",
                       {"contains": ["2462"]}, ["narrower"])
    assert len(fails) == 2


def test_check_budget():
    assert check_budget({"seconds": 5, "tool_calls": 2},
                        {"max_seconds": 10, "max_tool_calls": 4}) == []
    fails = check_budget({"seconds": 50, "tool_calls": 9},
                         {"max_seconds": 10, "max_tool_calls": 4})
    assert len(fails) == 2


def test_evaluate_chain_context_carry():
    scenario = {
        "id": "t", "chain": ["q1", "q2"],
        "expect_turns": [{"contains": ["45"]},
                         {"contains": ["45"],
                          "not_contains": ["do not show"]}],
        "budget": {"max_seconds_per_turn": 60},
    }
    good = evaluate_scenario(scenario, [
        {"text": "He scored 45.", "seconds": 10, "tool_calls": 3,
         "streamed_chars": 100},
        {"text": "45 points.", "seconds": 8, "tool_calls": 1,
         "streamed_chars": 60},
    ], banned=[])
    assert good["pass"]
    bad = evaluate_scenario(scenario, [
        {"text": "He scored 45.", "seconds": 10, "tool_calls": 3,
         "streamed_chars": 100},
        {"text": "My records do not show that game.", "seconds": 8,
         "tool_calls": 1, "streamed_chars": 60},
    ], banned=[])
    assert not bad["pass"]
    assert any("T2" in f for f in bad["fails"])


def test_xfail_never_fails_pack_semantics():
    scenario = {"id": "x", "chain": ["q"], "expect": {"contains": ["zzz"]},
                "xfail": True}
    res = evaluate_scenario(scenario, [{"text": "nope", "seconds": 1,
                                        "tool_calls": 1,
                                        "streamed_chars": 1}], banned=[])
    assert res["xfail"] and not res["pass"]


def test_check_trajectory_required_forbidden_and_duplicates():
    turns = [{"tool_trace": [
        {"name": "delegate_team", "agent": ""},
        {"name": "resolve_entity", "agent": "team"},
        {"name": "get_team_hub", "agent": "team"},
    ]}]
    assert check_trajectory(turns, {
        "required_tools": ["delegate_team", "get_team_hub"],
        "forbidden_tools": ["text_to_sql"],
        "no_duplicate_calls": True,
    }) == []
    fails = check_trajectory(turns, {
        "required_tools": ["get_standings"],
        "forbidden_tools": ["resolve_entity"],
    })
    assert len(fails) == 2


def test_evaluate_scenario_grades_trajectory_separately():
    scenario = {
        "id": "route", "chain": ["q"], "expect": {"contains": ["LeBron"]},
        "trajectory": {"required_tools": ["get_team_hub"]},
    }
    result = evaluate_scenario(scenario, [{
        "text": "LeBron", "seconds": 1, "tool_calls": 1,
        "tool_trace": [{"name": "resolve_entity", "agent": "team"}],
        "streamed_chars": 5,
    }], banned=[])
    assert not result["pass"]
    assert result["fails"] == ["trajectory: missing required tool: get_team_hub"]


def test_claim_grounding_matches_rows_meta_and_percent_scaling():
    from grounding import check_claim_grounding
    tables = [{"rows": [{"PLAYER": "Luke Kennard", "FG3_PCT": 0.478,
                          "FG3M": 117, "FG3A": 245}],
               "meta": {"season": "2025-26", "qualification": "82+ makes"}}]
    grade = check_claim_grounding(
        "In 2025-26 Kennard shot 47.8% (117 on 245); 82 makes required.",
        tables)
    assert grade["unsupported"] == []
    assert grade["coverage"] == 1.0


def test_claim_grounding_flags_invented_number_and_allows_declared_constant():
    from grounding import check_claim_grounding
    grade = check_claim_grounding("He scored 45 in 2 games.",
                                  [{"rows": [{"PTS": 44}]}], allow=["2"])
    assert grade["unsupported"] == ["45"]


def test_evidence_envelope_excludes_answer_and_question_text():
    from grounding import evidence_envelope
    env = evidence_envelope("case", [{"text": "secret", "evidence_tables":
                                      [{"rows": [{"PTS": 33}]}],
                                      "tool_trace": [{"name": "get_x"}]}])
    raw = __import__("json").dumps(env)
    assert "secret" not in raw and "33" in raw and "get_x" in raw
