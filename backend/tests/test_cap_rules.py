from shared.tools.cap_rules import (
    CAP,
    allowed_incoming,
    apron_state,
    cba_restrictions,
    frozen_pick_year,
    hard_cap_consequences,
    matching_band,
    roster_issues,
    scenario_trace,
    used_expanded_matching,
)


def test_apron_state_boundaries_exact():
    at_tax = apron_state(CAP["tax"])
    assert at_tax["over_tax"] is False
    over = apron_state(CAP["tax"] + 1)
    assert over["over_tax"] is True
    at_a1 = apron_state(CAP["apron1"])
    assert at_a1["over_apron1"] is False
    assert at_a1["room_apron1"] == 0
    over_a2 = apron_state(CAP["apron2"] + 1)
    assert over_a2["over_apron2"] is True
    assert over_a2["room_apron2"] == -1


def test_apron_state_custom_lines():
    lines = {"cap": 100, "tax": 150, "apron1": 160, "apron2": 170}
    state = apron_state(165, lines)
    assert state["over_apron1"] is True
    assert state["over_apron2"] is False


def test_allowed_incoming_tiers():
    low, rule_low = allowed_incoming(5_000_000, False)
    assert low == 5_000_000 * 2 + 250_000
    assert "200%" in rule_low
    mid, rule_mid = allowed_incoming(20_000_000, False)
    assert mid == 20_000_000 + 9_096_000
    high, rule_high = allowed_incoming(60_000_000, False)
    assert high == int(60_000_000 * 1.25 + 250_000)
    assert "125%" in rule_high
    apron, rule_apron = allowed_incoming(30_000_000, True)
    assert apron == 30_000_000
    assert "100%" in rule_apron


def test_allowed_incoming_cap_room_upgrade():
    matched, rule = allowed_incoming(20_000_000, False, cap_room=15_000_000)
    assert matched == 20_000_000 + 15_000_000 + 250_000
    assert "cap room" in rule


def test_used_expanded_matching():
    assert used_expanded_matching(30_000_000, 20_000_000) is True
    assert used_expanded_matching(20_000_000, 20_000_000) is False
    assert used_expanded_matching(10_000_000, 20_000_000) is False
    assert used_expanded_matching(35_000_000, 20_000_000, cap_room=15_000_000) is False
    assert used_expanded_matching(36_000_000, 20_000_000, cap_room=15_000_000) is True


def test_hard_cap_consequences_cover_both_triggers_post_trade():
    below = hard_cap_consequences(
        "BOS", CAP["apron1"] - 1,
        aggregates=True, expanded_matching=True)
    assert below["hard_cap"] == "second apron+first apron"
    assert below["violations"] == []
    assert below["issues"] == []

    over_first = hard_cap_consequences(
        "BOS", CAP["apron1"] + 1,
        aggregates=True, expanded_matching=True)
    assert over_first["violations"] == ["first apron"]
    assert len(over_first["issues"]) == 1
    assert "expanded salary matching" in over_first["issues"][0]

    over_second = hard_cap_consequences(
        "BOS", CAP["apron2"] + 1,
        aggregates=True, expanded_matching=True)
    assert over_second["violations"] == ["second apron", "first apron"]
    assert len(over_second["issues"]) == 2
    assert "second apron" in over_second["issues"][0]


def test_matching_band_shape():
    band = matching_band(20_000_000, False)
    assert band["allowed_incoming"] == 20_000_000 + 9_096_000
    assert isinstance(band["match_rule"], str)


def test_cba_restrictions_second_apron_full_catalog():
    state = {"over_apron2": True, "over_apron1": True,
             "over_tax": True, "cap_room": 0}
    rules = cba_restrictions(state, "2026-27")
    active = [r for r in rules if r["status"] == "active"
              and r["threshold"] == "second apron"]
    assert len(active) == 7
    assert any("frozen" in r["rule"] for r in active)
    texts = [r["rule"] for r in rules]
    assert not any("hard-caps the team at the second apron" in t
                   and "trigger" == r["status"] for t in texts for r in rules if r["rule"] == t)


def test_cba_restrictions_first_apron_partial():
    state = {"over_apron2": False, "over_apron1": True,
             "over_tax": True, "cap_room": 0}
    rules = cba_restrictions(state, "2026-27")
    a1_active = [r for r in rules if r["status"] == "active"
                 and r["threshold"] == "first apron"]
    assert len(a1_active) == 2
    assert any(r["status"] == "trigger" and r["threshold"] == "second apron"
               for r in rules)
    assert not any(r["status"] == "trigger" and r["threshold"] == "first apron"
                   for r in rules)


def test_cba_restrictions_under_cap_room():
    state = {"over_apron2": False, "over_apron1": False,
             "over_tax": False, "cap_room": 10_000_000}
    rules = cba_restrictions(state, "2026-27")
    assert any(r["threshold"] == "cap" and r["status"] == "active"
               for r in rules)
    assert any(r["status"] == "trigger" for r in rules)


def test_frozen_pick_year_math():
    assert frozen_pick_year("2026-27") == 2034
    assert frozen_pick_year("2025-26") == 2033
    assert frozen_pick_year("") is None


def test_roster_issues_bounds():
    assert roster_issues(15) == []
    assert roster_issues(14) == []
    assert len(roster_issues(16)) == 1
    assert "trim to 15" in roster_issues(16)[0]
    assert "at 14" in roster_issues(13)[0]


def test_scenario_trace_signs_and_order():
    trace = scenario_trace(100_000_000, [
        {"kind": "trade_out", "detail": "out A", "amount": 30_000_000},
        {"kind": "signing", "detail": "sign B", "amount": 12_000_000},
        {"kind": "trade_in", "detail": "in C (from POR)", "amount": 25_000_000},
    ], "BOS committed payroll")
    steps = trace["steps"]
    assert steps[0]["step"] == 0
    assert steps[0]["detail"] == "BOS committed payroll"
    assert steps[1]["delta"] == -30_000_000
    assert steps[2]["delta"] == 12_000_000
    assert steps[3]["delta"] == 25_000_000
    assert trace["pay_after"] == 107_000_000
    assert steps[-1]["payroll"] == 107_000_000
    assert trace["next_step"] == 4


def test_scenario_trace_waive_and_option_kinds_positive():
    trace = scenario_trace(50, [
        {"kind": "waive", "detail": "waive X stretch", "amount": 5},
        {"kind": "option_decline", "detail": "decline Y", "amount": 0},
    ])
    assert trace["pay_after"] == 55
