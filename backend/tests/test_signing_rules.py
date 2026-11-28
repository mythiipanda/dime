import pytest

from shared.tools.cap_rules import CAP
from shared.tools.signing_rules import (
    consume_signing_exception,
    initial_exception_state,
    minimum_salary,
    second_year_minimum_salary,
    validate_signing,
)


def validate(payroll, amount, years, mechanism="auto", yos=None, state=None):
    move = {"player": "Vector Player", "amount": amount,
            "years": years, "mechanism": mechanism}
    if yos is not None:
        move["years_of_service"] = yos
    return validate_signing(
        move, team="TST", payroll_before=payroll,
        exception_state=state or {})


def rejection_reasons(out):
    return {row["mechanism"]: row["reason"] for row in out["rejected_candidates"]}


def projected_2027_lines():
    return {"cap": 181_457_100, "tax": 220_470_800,
            "apron1": 229_916_500, "apron2": 243_854_600}


def test_vector_1_max_salary_external_signing_has_no_valid_mechanism():
    out = validate(195_000_000, 41_240_250, 4, yos=0)
    assert out["outcome"] == "illegal"
    assert out["legal"] is False
    assert out["mechanism_selected"] is None
    assert out["validation_checks"]["maximum_salary"] == "passed"
    reasons = rejection_reasons(out)
    assert "no cap room" in reasons["cap_room"]
    assert "15044000" in reasons["ntmle"].replace(",", "")
    assert "6064000" in reasons["tmle"].replace(",", "")
    assert "5477000" in reasons["bae"].replace(",", "")


def test_vector_2_auto_infers_cap_room():
    out = validate(100_000_000, 14_961_000, 4)
    assert out["outcome"] == "legal_approximation"
    assert out["legal"] is True
    assert out["mechanism_selected"] == "cap_room"
    assert out["mechanism_inference"] == "least_restrictive_legal"
    assert out["hard_cap_trigger"] == ""
    assert out["post_move_payroll"] == 114_961_000
    assert out["validation_checks"]["maximum_salary"] == "unknown"


def test_vector_3_cap_room_equality_is_legal():
    out = validate(150_000_000, 14_961_000, 1, "cap_room")
    assert out["outcome"] == "legal_approximation"
    assert out["mechanism_selected"] == "cap_room"
    assert out["post_move_payroll"] == CAP["cap"]


def test_vector_4_cap_room_one_dollar_over_is_illegal_without_rescue():
    out = validate(150_000_000, 14_961_001, 1, "cap_room")
    assert out["outcome"] == "illegal"
    assert out["mechanism_selected"] is None
    assert "cap room" in out["blocking_issues"][0]
    assert out["hard_cap_trigger"] == ""


def test_vector_5_ntmle_boundary_amount_and_term_are_legal_approximation():
    out = validate(190_000_000, 15_044_000, 4, "ntmle")
    assert out["outcome"] == "legal_approximation"
    assert out["mechanism_selected"] == "ntmle"
    assert out["hard_cap_trigger"] == "first apron"
    assert out["hard_cap_violations"] == []
    assert out["exception_remaining"] == 0
    assert "exception_use_ledger" in out["missing_inputs"]
    assert out["legality_confidence"] == "approximation"


def test_vector_6_ntmle_one_dollar_over_amount_is_illegal():
    out = validate(190_000_000, 15_044_001, 4, "ntmle")
    assert out["outcome"] == "illegal"
    assert "exceeds the non-taxpayer mid-level exception ceiling" in out["blocking_issues"][0]


def test_vector_7_ntmle_five_years_is_illegal():
    out = validate(190_000_000, 10_000_000, 5, "ntmle")
    assert out["outcome"] == "illegal"
    assert "four seasons" in out["blocking_issues"][0]


def test_vector_8_ntmle_can_finish_exactly_at_first_apron():
    out = validate(203_500_000, 5_515_000, 2, "ntmle")
    assert out["outcome"] == "legal_approximation"
    assert out["post_move_payroll"] == CAP["apron1"]
    assert out["post_move_apron_room"] == 0
    assert out["hard_cap_violations"] == []


def test_vector_9_ntmle_cannot_finish_one_thousand_over_first_apron():
    out = validate(203_500_000, 5_516_000, 2, "ntmle")
    assert out["outcome"] == "illegal"
    assert out["post_move_payroll"] == CAP["apron1"] + 1_000
    assert out["hard_cap_violations"] == ["first apron"]
    assert "signing is prohibited" in out["blocking_issues"][0]


def test_vector_10_tmle_can_finish_exactly_at_second_apron():
    out = validate(216_000_000, 5_686_000, 2, "tmle")
    assert out["outcome"] == "legal_approximation"
    assert out["mechanism_selected"] == "tmle"
    assert out["post_move_payroll"] == CAP["apron2"]
    assert out["post_move_apron_room"] == 0
    assert out["hard_cap_trigger"] == "second apron"
    assert out["hard_cap_violations"] == []


def test_vector_11_tmle_cannot_finish_one_thousand_over_second_apron():
    out = validate(216_000_000, 5_687_000, 2, "tmle")
    assert out["outcome"] == "illegal"
    assert out["post_move_payroll"] == CAP["apron2"] + 1_000
    assert out["hard_cap_violations"] == ["second apron"]


def test_vector_12_bae_boundary_is_legal_approximation():
    out = validate(190_000_000, 5_477_000, 2, "bae")
    assert out["outcome"] == "legal_approximation"
    assert out["mechanism_selected"] == "bae"
    assert out["hard_cap_trigger"] == "first apron"
    assert out["exception_remaining"] == 0


def test_vector_13_bae_prior_year_use_is_illegal():
    state = {"bae_used_prior_cap_year": True}
    out = validate(190_000_000, 5_477_000, 2, "bae", state=state)
    assert out["outcome"] == "illegal"
    assert "consecutive" in out["blocking_issues"][0]


def test_vector_14_minimum_exception_is_legal_above_second_apron():
    out = validate(225_000_000, 1_357_763, 2, "minimum", yos=0)
    assert out["outcome"] == "legal_approximation"
    assert out["mechanism_selected"] == "minimum"
    assert out["hard_cap_trigger"] == ""
    assert out["post_move_payroll"] == 226_357_763
    assert out["validation_checks"]["minimum_salary"] == "passed"


def test_vector_15_minimum_exception_three_years_is_illegal():
    out = validate(225_000_000, 1_357_763, 3, "minimum", yos=0)
    assert out["outcome"] == "illegal"
    assert "two seasons" in out["blocking_issues"][0]


def test_auto_does_not_infer_exceptions_when_below_cap_operating_mode_unknown():
    out = validate(150_000_000, 15_000_000, 1)
    assert out["outcome"] == "unknown"
    assert out["legal"] is False
    assert out["mechanism_selected"] is None
    assert out["mechanism_inference"] == "explicit_required"
    assert any("operating mode" in issue for issue in out["blocking_issues"])


def test_auto_infers_single_unambiguous_hard_capped_mechanism():
    out = validate(190_000_000, 15_044_000, 4)
    assert out["outcome"] == "legal_approximation"
    assert out["mechanism_selected"] == "ntmle"
    assert out["mechanism_inference"] == "least_restrictive_legal"


def test_auto_prefers_minimum_over_cap_room_when_exact_minimum():
    out = validate(100_000_000, 1_357_763, 2, yos=0)
    assert out["outcome"] == "legal_approximation"
    assert out["mechanism_selected"] == "minimum"
    assert "cap_room" in out["legal_candidates"]


def test_exception_consumption_is_cumulative_across_signings():
    state = initial_exception_state()
    first = validate(190_000_000, 8_000_000, 1, "ntmle", state=state)
    assert first["legal"] is True
    state = consume_signing_exception(state, first)
    assert state["ntmle_used"] == 8_000_000
    second = validate(198_000_000, 8_000_000, 1, "ntmle", state=state)
    assert second["outcome"] == "illegal"
    assert "remaining" in second["blocking_issues"][0]
    assert second["exception_remaining"] == 7_044_000


def test_active_hard_cap_restricts_later_minimum_signing():
    out = validate_signing(
        {"player": "Minimum Player", "amount": 1_357_763,
         "years": 1, "mechanism": "minimum", "years_of_service": 0},
        team="TST", payroll_before=CAP["apron1"],
        active_hard_caps=["first apron"])
    assert out["outcome"] == "illegal"
    assert "active first apron hard cap" in out["blocking_issues"][0]


def test_every_conclusion_carries_ats_proxy_metadata():
    out = validate(190_000_000, 5_477_000, 2, "bae")
    assert out["salary_basis"] == "approximate_salary_ledger_not_exact_apron_team_salary"
    assert out["ats_exact"] is False
    assert "exact_apron_team_salary" in out["missing_inputs"]
    assert "Approximation, not exact CBA signing legality" in out["signing_proxy_disclosure"]


def test_unknown_mechanism_is_an_input_error():
    out = validate_signing(
        {"player": "Bad Mechanism", "amount": 1_000_000,
         "years": 1, "mechanism": "mle"},
        team="TST", payroll_before=100_000_000)
    assert out["input_errors"]
    assert "unknown signing mechanism" in out["input_errors"][0]


def test_legacy_string_signings_use_auto_one_year_compatibility_shim():
    from shared.tools.league.cap_scenario import _validate_legacy_signings
    moves = [{"kind": "signing", "amount": 8_000_000, "player": "Legacy Player"}]
    out = _validate_legacy_signings("TST", moves, 190_000_000)
    validation = out["validations"][0]
    assert validation["mechanism_input"] == "auto"
    assert validation["years"] == 1
    assert validation["mechanism_selected"] == "ntmle"
    assert any("grouped compatibility inputs" in issue for issue in out["advisory"])
    assert moves[0]["validation"] is validation


def test_typed_scenario_tracks_signing_validation_and_exception_consumption():
    import duckdb
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
            "PLAYER_ID BIGINT, GUARANTEED BIGINT, SALARY_2026_27 BIGINT)")
        con.executemany(
            "INSERT INTO silver_salaries VALUES (?, ?, ?, ?, ?)",
            [(f"Roster {i}", "TST", i, 19_000_000, 19_000_000)
             for i in range(1, 11)])
        out = evaluate_cap_scenario(con, {
            "team": "TST", "season": "2026-27",
            "moves": [
                {"kind": "signing", "player": "First", "amount": 8_000_000,
                 "years": 1, "mechanism": "ntmle"},
                {"kind": "signing", "player": "Second", "amount": 8_000_000,
                 "years": 1, "mechanism": "ntmle"},
            ]})
    finally:
        con.close()
    assert out["ok"] is True
    validations = out["signing_validations"]
    assert validations[0]["outcome"] == "legal_approximation"
    assert validations[1]["outcome"] == "illegal"
    assert "remaining" in validations[1]["blocking_issues"][0]
    signing_steps = [step for step in out["steps"] if step["kind"] == "signing"]
    assert signing_steps[0]["validation"]["mechanism_selected"] == "ntmle"
    assert out["meta"]["signing_validation_version"] == "v1"
    assert out["meta"]["ats_exact"] is False


def _chronology_con():
    import duckdb
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
        "PLAYER_ID BIGINT, GUARANTEED BIGINT, SALARY_2026_27 BIGINT, SALARY_2027_28 BIGINT)")
    rows = [("Outgoing Star", "TST", 20_000_000),
            ("Incoming Star", "OTH", 29_000_000)]
    rows += [(f"Roster {i}", "TST", 13_800_000) for i in range(1, 13)]
    rows.append(("Roster 13", "TST", 13_400_000))
    for i, (name, team, salary) in enumerate(rows, 1):
        con.execute("INSERT INTO silver_salaries VALUES (?, ?, ?, ?, ?, ?)",
                    [name, team, i, salary, salary, salary])
    return con


def test_trade_hard_cap_is_chronological_not_retroactive():
    import duckdb
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    con = _chronology_con()
    try:
        out = evaluate_cap_scenario(con, {
            "team": "TST", "season": "2026-27",
            "moves": [
                {"kind": "trade_out", "player": "Outgoing Star"},
                {"kind": "trade_in", "player": "Incoming Star"},
                {"kind": "signing", "player": "Minimum Player", "amount": 1_357_763,
                 "years": 1, "mechanism": "minimum", "years_of_service": 0},
            ]})
    finally:
        con.close()
    assert out["ok"] is True
    assert out["matching"]["legal"] is True
    assert out["matching"]["post_trade_payroll"] == 208_000_000
    assert out["hard_cap"] == "first apron"
    validation = out["signing_validations"][0]
    assert validation["outcome"] == "illegal"
    assert "active first apron hard cap" in validation["blocking_issues"][0]
    assert not any("post-trade payroll proxy ($209,357,763)" in issue
                   for issue in out["issues"])


def test_declared_below_cap_mode_bars_over_cap_exceptions():
    out = validate(150_000_000, 15_000_000, 1,
                   state={"operating_mode": "below_cap"})
    assert out["outcome"] == "illegal"
    assert out["mechanism_selected"] is None
    reasons = rejection_reasons(out)
    assert "below-cap operating mode" in reasons["ntmle"]
    assert "mid-level exception for room teams ceiling" in reasons["room_exception"]


def test_auto_with_no_legal_candidate_in_any_mode_is_illegal_not_ambiguous():
    out = validate(150_000_000, 40_000_000, 1)
    assert out["outcome"] == "illegal"
    assert out["mechanism_inference"] == "none"
    assert out["legal_candidates"] == []
    assert "no valid signing mechanism" in out["blocking_issues"][0]


def test_auto_tie_breaker_is_disclosed():
    out = validate(190_000_000, 5_400_000, 2)
    assert out["mechanism_selected"] == "ntmle"
    assert "bae carries a consecutive-year frequency restriction" in out["selection_tie_breaker"]


def test_minimum_salary_schedule_enforces_exact_second_year_minimum():
    bad = validate(225_000_000, 1_357_763, 2, "minimum", yos=0)
    assert bad["outcome"] == "legal_approximation"
    move = {"player": "Scheduled Minimum", "amount": 1_357_763, "years": 2,
            "mechanism": "minimum", "years_of_service": 0,
            "salary_schedule": [1_357_763, 20_000_000]}
    out = validate_signing(move, team="TST", payroll_before=225_000_000)
    assert out["outcome"] == "illegal"
    assert "second-year salary" in out["blocking_issues"][0]
    assert "$2,294,370" in out["blocking_issues"][0]
    move["salary_schedule"] = [1_357_763, 2_294_370]
    good = validate_signing(move, team="TST", payroll_before=225_000_000)
    assert good["outcome"] == "legal_approximation"


def test_unsupported_typed_free_agent_inputs_are_errors_not_silently_ignored():
    base = {"player": "Own Free Agent", "amount": 10_000_000, "years": 1,
            "mechanism": "ntmle", "prior_team": "TST"}
    out = validate_signing(base, team="TST", payroll_before=190_000_000)
    assert out["input_errors"]
    assert "prior_team cannot be consumed" in out["input_errors"][0]
    base = {"player": "Own Free Agent", "amount": 10_000_000, "years": 1,
            "mechanism": "ntmle", "free_agent_status": "non_bird"}
    out = validate_signing(base, team="TST", payroll_before=190_000_000)
    assert "free_agent_status cannot be consumed" in out["input_errors"][0]
    base = {"player": "Own Free Agent", "amount": 10_000_000, "years": 1,
            "mechanism": "ntmle", "replaces_cap_hold": True}
    out = validate_signing(base, team="TST", payroll_before=190_000_000)
    assert "replaces_cap_hold requires exact cap-hold ledger state" in out["input_errors"][0]
    base = {"player": "Exception Signing", "amount": 10_000_000, "years": 2,
            "mechanism": "ntmle", "salary_schedule": [10_000_000, 10_500_000]}
    out = validate_signing(base, team="TST", payroll_before=190_000_000)
    assert "supported only for mechanism=minimum" in out["input_errors"][0]


def test_future_season_exceptions_scale_from_season_cap_line_or_require_lines():
    ratio_lines = {key: int(round(value * 1.07)) for key, value in CAP.items()}
    amount = 16_097_080
    out = validate_signing(
        {"player": "Future MLE", "amount": amount, "years": 4,
         "mechanism": "ntmle"},
        team="TST", payroll_before=190_000_000, lines=ratio_lines,
        season="2027-28")
    assert out["outcome"] == "legal_approximation"
    assert out["exception_amount"] == amount
    assert out["exception_amount_basis"] == "warehouse-style exact cap-growth projection; not official cba amounts"
    missing_lines = validate_signing(
        {"player": "Future MLE", "amount": amount, "years": 4,
         "mechanism": "ntmle"},
        team="TST", payroll_before=190_000_000, season="2027-28")
    assert missing_lines["input_errors"]
    assert "season-specific cap lines are required" in missing_lines["input_errors"][0]


@pytest.mark.parametrize(("mechanism", "amount"), [
    ("ntmle", 16_548_400), ("bae", 6_024_700),
    ("room_exception", 10_302_600), ("tmle", 6_670_400),
])
def test_projected_2027_exception_boundaries_are_exact_to_the_dollar(mechanism, amount):
    lines = projected_2027_lines()
    payroll = 190_000_000
    state = {}
    if mechanism == "tmle":
        payroll = lines["apron1"]
    if mechanism == "room_exception":
        payroll = 150_000_000
        state = {"operating_mode": "below_cap"}
    move = {"player": "Projected Boundary", "amount": amount,
            "years": 1, "mechanism": mechanism}
    exact = validate_signing(
        move, team="TST", payroll_before=payroll, lines=lines,
        exception_state=state, season="2027-28")
    assert exact["outcome"] == "legal_approximation"
    assert exact["exception_amount"] == amount
    assert exact["exception_amount_basis"] == "warehouse-style exact cap-growth projection; not official cba amounts"
    over = validate_signing(
        dict(move, amount=amount + 1), team="TST", payroll_before=payroll,
        lines=lines, exception_state=state, season="2027-28")
    assert over["outcome"] == "illegal"
    assert "ceiling" in over["blocking_issues"][0]


def test_warehouse_exception_amounts_override_pure_projection():
    lines = {key: int(round(value * 1.07)) for key, value in CAP.items()}
    move = {"player": "Warehouse Precise", "amount": 16_548_400,
            "years": 1, "mechanism": "ntmle"}
    out = validate_signing(
        move, team="TST", payroll_before=190_000_000, lines=lines,
        season="2027-28", exception_amounts={"ntmle": 16_548_400},
        exception_amounts_source="warehouse silver_cap_room projected estimate; not official cba amounts")
    assert out["outcome"] == "legal_approximation"
    assert out["exception_amount"] == 16_548_400
    assert out["exception_amount_basis"] == "warehouse silver_cap_room projected estimate; not official cba amounts"


def test_scenario_reads_warehouse_exception_amounts_for_projected_season():
    import duckdb
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
            "PLAYER_ID BIGINT, GUARANTEED BIGINT, SALARY_2027_28 BIGINT)")
        con.executemany(
            "INSERT INTO silver_salaries VALUES (?, ?, ?, ?, ?)",
            [(f"Roster {i}", "TST", i, 19_000_000, 19_000_000)
             for i in range(1, 11)])
        con.execute(
            "CREATE TABLE silver_cap_room (TEAM VARCHAR, CAP_SEASON VARCHAR, "
            "PROJECTED_CAP BIGINT, PROJECTED_TAX BIGINT, PROJECTED_APRON1 BIGINT, "
            "PROJECTED_APRON2 BIGINT, NTMLE_EST BIGINT, BAE_EST BIGINT, "
            "ROOM_EST BIGINT, TMLE_EST BIGINT)")
        con.execute(
            "INSERT INTO silver_cap_room VALUES "
            "('TST', '2027-28', 176000000, 214000000, 224000000, 237000000, "
            "16548400, 6024700, 10302600, 6670400)")
        out = evaluate_cap_scenario(con, {
            "team": "TST", "season": "2027-28",
            "moves": [{"kind": "signing", "player": "Warehouse Precise",
                       "amount": 16_548_400, "years": 1, "mechanism": "ntmle"}]})
    finally:
        con.close()
    validation = out["signing_validations"][0]
    assert validation["outcome"] == "legal_approximation"
    assert validation["exception_amount"] == 16_548_400
    assert validation["exception_amount_basis"] == "warehouse silver_cap_room projected estimate; not official cba amounts"


def test_legacy_signing_validation_uses_the_scenario_season():
    from shared.tools.league.cap_scenario import _validate_legacy_signings
    moves = [{"kind": "signing", "player": "Future Player", "amount": 16_548_400}]
    out = _validate_legacy_signings(
        "TST", moves, 190_000_000, lines=projected_2027_lines(), season="2027-28")
    validation = out["validations"][0]
    assert validation["outcome"] == "legal_approximation"
    assert validation["exception_amount"] == 16_548_400


def test_current_season_official_amounts_take_precedence_over_estimates():
    move = {"player": "Current Season", "amount": 15_044_001,
            "years": 1, "mechanism": "ntmle"}
    out = validate_signing(
        move, team="TST", payroll_before=190_000_000,
        exception_amounts={"ntmle": 20_000_000})
    assert out["outcome"] == "illegal"
    assert out["exception_amount"] == 15_044_000
    assert out["exception_amount_basis"] == "2026-27 official cba amounts"


def test_exception_amount_overrides_are_strictly_validated():
    move = {"player": "Override", "amount": 1, "years": 1,
            "mechanism": "ntmle"}
    bad_value = validate_signing(
        move, team="TST", payroll_before=190_000_000,
        lines=projected_2027_lines(), season="2027-28",
        exception_amounts={"ntmle": 1.5})
    assert "exception_amounts.ntmle must be a positive integer" in bad_value["input_errors"]
    bad_key = validate_signing(
        move, team="TST", payroll_before=190_000_000,
        lines=projected_2027_lines(), season="2027-28",
        exception_amounts={"mle": 16_548_400})
    assert "unknown exception_amounts key 'mle'" in bad_key["input_errors"]


def test_future_minimum_scaling_uses_exact_rational_half_up_dollars():
    lines = {"cap": CAP["cap"] // 2}
    assert minimum_salary(2, "2027-28", lines) == 1_224_711
    move = {"player": "Future Minimum", "amount": 1_224_711, "years": 1,
            "mechanism": "minimum", "years_of_service": 2}
    lines = {**projected_2027_lines(), "cap": CAP["cap"] // 2}
    out = validate_signing(
        move, team="TST", payroll_before=150_000_000, lines=lines,
        season="2027-28")
    assert out["validation_checks"]["minimum_salary"] == "passed"
    assert any("half-dollar tie rounding" in issue
               for issue in out["advisory_issues"])


def test_roster_failure_is_reported_before_apron_failure():
    import duckdb
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
            "PLAYER_ID BIGINT, GUARANTEED BIGINT, SALARY_2026_27 BIGINT)")
        for i in range(1, 16):
            con.execute("INSERT INTO silver_salaries VALUES (?, ?, ?, ?, ?)",
                        [f"Roster {i}", "TST", i, 13_000_000, 13_000_000])
        out = evaluate_cap_scenario(con, {
            "team": "TST", "season": "2026-27",
            "moves": [{"kind": "signing", "player": "Too Much",
                       "amount": 15_044_000, "years": 1,
                       "mechanism": "ntmle"}]})
    finally:
        con.close()
    assert out["issues"][0].startswith("roster would be 16 players")
    assert "first apron" in out["issues"][1]


def test_minimum_salary_scales_match_published_2026_27_multiyear_table():
    first_year = {
        0: 1_357_763, 1: 2_185_116, 2: 2_449_421, 3: 2_537_526,
        4: 2_625_627, 5: 2_845_883, 6: 3_066_143, 7: 3_286_399,
        8: 3_506_659, 9: 3_524_115, 10: 3_876_529,
    }
    second_year = {
        1: 2_294_370, 2: 2_571_895, 3: 2_664_401, 4: 2_756_912,
        5: 2_988_178, 6: 3_219_451, 7: 3_450_720, 8: 3_681_991,
        9: 3_700_320, 10: 4_070_355,
    }
    for yos, expected in first_year.items():
        assert minimum_salary(yos) == expected
    for service_year, expected in second_year.items():
        assert second_year_minimum_salary(service_year - 1, "2026-27", CAP) == expected
    assert second_year_minimum_salary(10, "2026-27", CAP) == second_year[10]


def test_five_yos_minimum_schedule_boundary_is_exact_to_the_dollar():
    move = {"player": "Boundary Minimum", "amount": 2_845_883, "years": 2,
            "mechanism": "minimum", "years_of_service": 5,
            "salary_schedule": [2_845_883, 3_219_451]}
    good = validate_signing(move, team="TST", payroll_before=225_000_000)
    assert good["outcome"] == "legal_approximation"
    low = dict(move, salary_schedule=[2_845_883, 3_219_450])
    bad = validate_signing(low, team="TST", payroll_before=225_000_000)
    assert bad["outcome"] == "illegal"
    assert "$3,219,451" in bad["blocking_issues"][0]


def _payroll_con(total: int, players: int = 10):
    import duckdb
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
        "PLAYER_ID BIGINT, GUARANTEED BIGINT, SALARY_2026_27 BIGINT)")
    base = total // players
    amounts = [base] * players
    amounts[-1] += total - sum(amounts)
    for i, amount in enumerate(amounts, 1):
        con.execute("INSERT INTO silver_salaries VALUES (?, ?, ?, ?, ?)",
                    [f"Roster {i}", "TST", i, amount, amount])
    return con


def test_per_move_exception_state_cannot_reset_cumulative_consumption():
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    con = _payroll_con(189_000_000)
    try:
        out = evaluate_cap_scenario(con, {
            "team": "TST", "season": "2026-27",
            "moves": [
                {"kind": "signing", "player": "First", "amount": 4_000_000,
                 "years": 1, "mechanism": "ntmle",
                 "exception_state": {"ntmle_used": 10_000_000}},
                {"kind": "signing", "player": "Second", "amount": 4_000_000,
                 "years": 1, "mechanism": "ntmle",
                 "exception_state": {"ntmle_used": 10_000_000}},
            ]})
    finally:
        con.close()
    validations = out["signing_validations"]
    assert validations[0]["outcome"] == "legal_approximation"
    assert validations[0]["exception_remaining"] == 1_044_000
    assert validations[1]["outcome"] == "illegal"
    assert validations[1]["exception_remaining"] == 1_044_000
    assert "remaining" in validations[1]["blocking_issues"][0]
    assert any("exception_state.ntmle_used" in row["error"]
               and "override rejected" in row["error"]
               for row in out["errors"])
    assert out["signing_exception_state"]["ntmle_used"] == 14_000_000


def test_first_move_exception_state_input_seeds_single_validation():
    out = validate_signing(
        {"player": "Prior Use", "amount": 4_000_000, "years": 1,
         "mechanism": "ntmle", "exception_state": {"ntmle_used": 10_000_000}},
        team="TST", payroll_before=190_000_000)
    assert out["outcome"] == "legal_approximation"
    assert out["exception_remaining"] == 1_044_000


def test_prohibited_signing_hard_cap_trigger_is_disclosed_not_active():
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    con = _payroll_con(203_500_000)
    try:
        out = evaluate_cap_scenario(con, {
            "team": "TST", "season": "2026-27",
            "moves": [
                {"kind": "signing", "player": "Too High", "amount": 5_516_000,
                 "years": 2, "mechanism": "ntmle"},
                {"kind": "signing", "player": "Minimum Player", "amount": 1_357_763,
                 "years": 1, "mechanism": "minimum", "years_of_service": 0},
            ]})
    finally:
        con.close()
    validations = out["signing_validations"]
    assert validations[0]["outcome"] == "illegal"
    assert validations[0]["hard_cap_trigger"] == "first apron"
    assert validations[1]["outcome"] == "legal_approximation"
    assert out["hard_cap"] == ""
    assert out["active_hard_caps"] == []
    assert out["hard_cap_triggers"] == [
        {"transaction": "signing", "move_index": 0,
         "apron": "first apron", "status": "prohibited"}]
    assert out["would_be_hard_cap_triggers"] == out["hard_cap_triggers"]


def test_exception_state_rejects_malformed_keys_and_types():
    move = {"player": "Malformed State", "amount": 4_000_000, "years": 1,
            "mechanism": "ntmle",
            "exception_state": {"ntmle_used": 1.5, "typo_key": True}}
    out = validate_signing(move, team="TST", payroll_before=190_000_000)
    assert out["mechanism_inference"] == "input_error"
    assert any("unknown exception_state key 'typo_key'" in e for e in out["input_errors"])
    assert any("exception_state.ntmle_used must be a non-negative integer" in e
               for e in out["input_errors"])


def test_scenario_malformed_per_move_exception_state_is_input_error_without_consumption():
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    con = _payroll_con(189_000_000)
    try:
        out = evaluate_cap_scenario(con, {
            "team": "TST", "season": "2026-27",
            "moves": [{"kind": "signing", "player": "Malformed State",
                       "amount": 4_000_000, "years": 1, "mechanism": "ntmle",
                       "exception_state": {"ntmle_used": 1.5, "typo_key": True}}]})
    finally:
        con.close()
    assert len(out["signing_validations"]) == 1
    validation = out["signing_validations"][0]
    assert validation["outcome"] == "unknown"
    assert validation["mechanism_inference"] == "input_error"
    assert validation["legal"] is False
    assert validation["exception_use"] is None
    assert any("unknown exception_state key 'typo_key'" in e
               for e in validation["input_errors"])
    assert any("exception_state.ntmle_used must be a non-negative integer" in e
               for e in validation["input_errors"])
    assert any("override rejected" in row["error"] for row in out["errors"])
    assert out["signing_exception_state"]["ntmle_used"] == 0
    assert out["pay_after"] == out["pay_before"]
    assert not any(step["kind"] == "signing" for step in out["steps"])


def test_top_level_exception_state_rejects_malformed_input_explicitly():
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    con = _payroll_con(189_000_000)
    try:
        out = evaluate_cap_scenario(con, {
            "team": "TST", "season": "2026-27",
            "exception_state": {"ntmle_used": -1},
            "moves": [{"kind": "signing", "player": "First", "amount": 4_000_000,
                       "years": 1, "mechanism": "ntmle"}]})
    finally:
        con.close()
    assert any(row["move"] == "scenario"
               and "exception_state.ntmle_used" in row["error"]
               for row in out["errors"])
