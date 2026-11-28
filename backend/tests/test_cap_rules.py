from shared.tools.cap_rules import (
    CAP,
    allowed_incoming,
    apron_state,
    cba_restrictions,
    frozen_pick_year,
    hard_cap_consequences,
    matching_band,
    matching_election,
    operative_match_rule,
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


def test_allowed_incoming_zero_outgoing_has_no_simultaneous_capacity():
    unavailable, rule = allowed_incoming(0, False)
    assert unavailable == 0
    assert rule == ("no available salary-matching structure "
                    "(no outgoing player salary)")
    assert allowed_incoming(0, False, cap_room=1)[0] == 250_001
    assert allowed_incoming(1, False)[0] == 250_002


def test_used_expanded_matching():
    assert used_expanded_matching(30_000_000, 20_000_000) is True
    assert used_expanded_matching(20_000_000, 20_000_000) is False
    assert used_expanded_matching(10_000_000, 20_000_000) is False
    assert used_expanded_matching(20_100_000, 20_000_000) is False
    assert used_expanded_matching(20_250_000, 20_000_000) is False
    assert used_expanded_matching(20_250_001, 20_000_000) is True
    assert used_expanded_matching(
        20_100_000, 20_000_000, cushion=0) is True
    assert used_expanded_matching(
        20_000_000, 20_000_000, cushion=0) is False
    assert used_expanded_matching(35_000_000, 20_000_000, cap_room=15_000_000) is False
    assert used_expanded_matching(36_000_000, 20_000_000, cap_room=15_000_000) is True


def test_matching_election_cap_room_precedes_standard_band():
    election = matching_election(
        20_100_000, 20_000_000, cap_room=14_961_000)
    assert election["matching_structure"] == "cap_room"
    assert election["matching_mechanisms"] == ["cap_room"]
    assert election["expanded_required"] is False

    standard = matching_election(20_100_000, 20_000_000)
    assert standard["matching_structure"] == "standard_simultaneous"


def test_operative_match_rule_follows_selected_mechanism():
    expanded_rule = "outgoing salary plus $9.096M (below the first apron)"
    standard = matching_election(20_100_000, 20_000_000)
    aggregated = matching_election(
        30_100_000, 30_000_000, outgoing_count=2)
    cap_room = matching_election(
        20_100_000, 20_000_000, cap_room=14_961_000)
    expanded = matching_election(
        20_250_001, 20_000_000, expanded_matching=True)
    assert operative_match_rule(expanded_rule, standard) == (
        "standard TPE matching: 100% of outgoing salary plus "
        "applicable cushion")
    assert operative_match_rule(expanded_rule, aggregated) == (
        "aggregated standard TPE matching: 100% of aggregated "
        "outgoing salary plus applicable cushion")
    assert operative_match_rule(expanded_rule, cap_room) == (
        "cap room plus outgoing salary plus $250k (under the cap)")
    assert operative_match_rule(expanded_rule, expanded) == expanded_rule


def test_operative_match_rule_non_expanded_fallback_shapes_are_coherent():
    expanded_rule = "outgoing salary plus $9.096M (below the first apron)"
    declared_only = matching_election(
        8_200_000, 0, uses_declared_tpe=True)
    combined = matching_election(
        15_000_000, 14_000_000, uses_declared_tpe=True)
    no_salary = matching_election(0, 20_000_000)
    unavailable = matching_election(1_000_000, 0)
    assert declared_only["matching_structure"] == "declared_tpe"
    assert combined["matching_structure"] == "standard_simultaneous+declared_tpe"
    assert operative_match_rule(expanded_rule, declared_only) == (
        "declared TPE capacity: separate non-combined exception bin")
    assert operative_match_rule(expanded_rule, combined) == (
        "standard TPE matching: 100% of outgoing salary plus "
        "applicable cushion")
    assert operative_match_rule(expanded_rule, no_salary) == (
        "no salary matching required (no incoming player salary)")
    assert operative_match_rule(expanded_rule, unavailable) == (
        "no available salary-matching structure (no outgoing player salary)")
    for election in (declared_only, combined, no_salary, unavailable):
        rule = operative_match_rule(expanded_rule, election)
        assert "$9.096M" not in rule
        assert "expanded" not in rule.lower()


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
    assert "Expanded Traded Player Exception" in over_first["issues"][0]
    assert "transaction is prohibited" in over_first["issues"][0]

    over_second = hard_cap_consequences(
        "BOS", CAP["apron2"] + 1,
        aggregates=True, expanded_matching=True)
    assert over_second["violations"] == ["second apron", "first apron"]
    assert len(over_second["issues"]) == 2
    assert "second apron" in over_second["issues"][0]


def test_hard_cap_consequences_cover_signing_triggers():
    ntmle = hard_cap_consequences(
        "BOS", CAP["apron1"], used_ntmle=True)
    assert ntmle["hard_cap"] == "first apron"
    assert ntmle["causes"]["first apron"] == ["the non-taxpayer mid-level exception"]
    assert ntmle["violations"] == []

    bae = hard_cap_consequences(
        "BOS", CAP["apron1"] + 1, used_bae=True)
    assert bae["violations"] == ["first apron"]
    assert "bi-annual exception" in bae["issues"][0]

    tmle = hard_cap_consequences(
        "BOS", CAP["apron2"], used_tmle=True)
    assert tmle["hard_cap"] == "second apron"
    assert tmle["causes"]["second apron"] == ["the taxpayer mid-level exception"]
    assert tmle["violations"] == []

    waived = hard_cap_consequences(
        "BOS", CAP["apron1"], signed_high_salary_waived_player=True)
    assert waived["hard_cap"] == "first apron"
    assert waived["causes"]["first apron"] == ["the high-salary waived-player signing"]


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


def test_scenario_trace_waive_subtracts_relief():
    trace = scenario_trace(50, [
        {"kind": "waive", "detail": "waive X stretch", "amount": 5,
         "dead_cap": 10, "guaranteed": 20, "estimate_basis": "pin"},
        {"kind": "option_decline", "detail": "decline Y", "amount": 0},
    ])
    assert trace["pay_after"] == 45
    waive = trace["steps"][1]
    assert waive["dead_cap"] == 10
    assert waive["guaranteed"] == 20
    assert waive["estimate_basis"] == "pin"
