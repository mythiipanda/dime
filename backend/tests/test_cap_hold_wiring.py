import duckdb

from shared.tools.league.cap_hold_derivation import derive_cap_holds
from shared.tools.league.cap_sheet import evaluate_cap_scenario


def wiring_con():
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE silver_free_agents ("
        "PLAYER_NAME VARCHAR, TEAM VARCHAR, BREF_SLUG VARCHAR, FA_YEAR BIGINT, "
        "FA_TYPE VARCHAR, PRIOR_SALARY BIGINT, CAP_HOLD_EST BIGINT)")
    con.executemany(
        "INSERT INTO silver_free_agents VALUES (?,?,?,?,?,?,?)",
        [("Veteran FA", "BOS", "vetfa01", 2027, "ufa", 20_000_000, 30_000_000),
         ("Rookie FA", "BOS", "rookfa01", 2027, "ufa", 10_000_000, 15_000_000),
         ("Option Rookie", "BOS", "optro01", 2027, "team_option", 5_000_000, 7_500_000),
         ("Unknown FA", "BOS", "unkno01", 2027, "ufa", 8_000_000, 12_000_000)])
    con.execute(
        "CREATE TABLE silver_salaries ("
        "PLAYER_NAME VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, BREF_SLUG VARCHAR, "
        "GUARANTEED BIGINT, SALARY_2026_27 BIGINT, SALARY_2027_28 BIGINT, "
        "OPTION_2026_27 VARCHAR, OPTION_2027_28 VARCHAR)")
    con.executemany(
        "INSERT INTO silver_salaries VALUES (?,?,?,?,?,?,?,?,?)",
        [("Contracted Player", "BOS", 1, "contr01", 80_000_000,
          40_000_000, 40_000_000, None, None),
         ("Veteran FA", "BOS", 2, "vetfa01", 20_000_000,
          20_000_000, None, None, None),
         ("Rookie FA", "BOS", 3, "rookfa01", 10_000_000,
          10_000_000, None, None, None),
         ("Option Rookie", "BOS", 4, "optro01", 11_000_000,
          5_000_000, 6_000_000, None, "team"),
         ("Unknown FA", "BOS", 5, "unkno01", 8_000_000,
          8_000_000, None, None, None)])
    con.execute(
        "CREATE TABLE silver_cap_room ("
        "TEAM VARCHAR, CAP_SEASON VARCHAR, COMMITTED_SALARY BIGINT, "
        "PENDING_OPTION_SALARY BIGINT, FA_HOLDS_EST BIGINT, "
        "INCOMPLETE_ROSTER_CHARGES BIGINT, PROJECTED_ROOM BIGINT, MAX_ROOM BIGINT, "
        "PROJECTED_CAP BIGINT, PROJECTED_TAX BIGINT, PROJECTED_APRON1 BIGINT, "
        "PROJECTED_APRON2 BIGINT, PLAYERS_UNDER_CONTRACT BIGINT, "
        "ROSTER_CHARGE_MINIMUM BIGINT)")
    con.execute(
        "INSERT INTO silver_cap_room VALUES "
        "('BOS','2027-28',40000000,6000000,67500000,2987078,100000000,"
        "110000000,181457100,220470800,229916500,243854600,8,1493539)")
    con.execute(
        "CREATE TABLE silver_hist_draft ("
        "PERSON_ID BIGINT, DRAFT_YEAR BIGINT, ROUND_NUMBER BIGINT, OVERALL_PICK BIGINT)")
    con.executemany(
        "INSERT INTO silver_hist_draft VALUES (?,?,?,?)",
        [(3, 2023, 1, 6), (4, 2025, 1, 14)])
    con.execute(
        "CREATE TABLE silver_hist_player_seasons ("
        "player_id BIGINT, player_name VARCHAR, team_abbreviation VARCHAR, season INTEGER)")
    season_rows = []
    for year in range(2023, 2028):
        season_rows.append((2, "Veteran FA", "BOS", year))
    for year in range(2024, 2028):
        season_rows.append((3, "Rookie FA", "BOS", year))
    for year in range(2026, 2028):
        season_rows.append((4, "Option Rookie", "BOS", year))
    con.executemany("INSERT INTO silver_hist_player_seasons VALUES (?,?,?,?)", season_rows)
    con.execute(
        "CREATE TABLE silver_transactions ("
        "txn_date VARCHAR, txn_type VARCHAR, player VARCHAR, player_id BIGINT, "
        "team VARCHAR, team_id BIGINT, detail VARCHAR)")
    con.execute(
        "CREATE TABLE silver_cap_players ("
        "team VARCHAR, player VARCHAR, contract_type VARCHAR, _season VARCHAR)")
    con.executemany(
        "INSERT INTO silver_cap_players VALUES (?,?,?,?)",
        [("BOS", "Rookie FA", "Rookie Scale", "2026-27"),
         ("BOS", "Option Rookie", "Rookie Scale", "2026-27")])
    return con


def add_transaction_case(con, player, slug, player_id, txns):
    con.execute("INSERT INTO silver_free_agents VALUES (?,?,?,?,?,?,?)",
                [player, "BOS", slug, 2027, "ufa", 20_000_000, 30_000_000])
    con.execute("INSERT INTO silver_salaries VALUES (?,?,?,?,?,?,?,?,?)",
                [player, "BOS", player_id, slug, 20_000_000,
                 20_000_000, None, None, None])
    con.executemany(
        "INSERT INTO silver_hist_player_seasons VALUES (?,?,?,?)",
        [(player_id, player, team, year)
         for year, team in [(2024, "ATL"), (2025, "ATL"), (2026, "BOS"), (2027, "BOS")]])
    con.executemany("INSERT INTO silver_transactions VALUES (?,?,?,?,?,?,?)", txns)


def test_derivation_uses_rookie_scale_and_discloses_unknowns():
    con = wiring_con()
    try:
        payload = derive_cap_holds(con, 2027, "BOS")
    finally:
        con.close()
    rows = {row["player"]: row for row in payload["rows"]}
    assert rows["Veteran FA"]["cap_hold"] == 30_000_000
    assert rows["Veteran FA"]["hold_rule"] == "qualifying_veteran_150_percent"
    assert rows["Rookie FA"]["cap_hold"] == 30_000_000
    assert rows["Rookie FA"]["rookie_scale_status"] == "completed_after_second_option_year"
    assert rows["Rookie FA"]["hold_rule"] == "rookie_scale_completion_300_percent"
    assert rows["Option Rookie"]["cap_hold"] == 6_000_000
    assert rows["Option Rookie"]["rookie_scale_status"] == "option_declined_after_second_or_third_year"
    assert rows["Option Rookie"]["active_in_baseline"] is False
    assert rows["Unknown FA"]["cap_hold"] is None
    assert rows["Unknown FA"]["provenance_class"] == "uncomputed_unknown_inputs"
    assert rows["Veteran FA"]["input_provenance"]["rights_classification"].startswith(
        "inference:")
    assert "silver_transactions" in payload["meta"]["derivation_source_pin"]["rights_inference"]
    assert payload["active_total"] == 60_000_000
    assert payload["unknown_count"] == 1


def test_transaction_evidence_models_carryover_reset_or_unknown():
    con = wiring_con()
    try:
        add_transaction_case(con, "Traded Carry", "traca01", 101, [
            ("2025-07-06", "Trade", "traded-carry", 101, "celtics", 1610612738,
             "Boston Celtics received guard Traded Carry from Atlanta Hawks."),
        ])
        add_transaction_case(con, "Unproven Traded", "unptr01", 102, [
            ("2025-07-06", "Trade", "unproven-traded", 102, "celtics", 1610612738, ""),
        ])
        add_transaction_case(con, "Signed Reset", "signr01", 103, [
            ("2025-07-06", "Signing", "signed-reset", 103, "celtics", 1610612738,
             "Boston Celtics signed guard Signed Reset to a Contract."),
        ])
        payload = derive_cap_holds(con, 2027, "BOS")
    finally:
        con.close()
    rows = {row["player"]: row for row in payload["rows"]}
    assert rows["Traded Carry"]["rights_classification"] == "qualifying"
    assert rows["Traded Carry"]["cap_hold"] == 30_000_000
    assert rows["Traded Carry"]["hold_rule"] == "qualifying_veteran_150_percent"
    assert "trade carryover" in rows["Traded Carry"]["input_provenance"]["rights_classification"]
    assert rows["Unproven Traded"]["rights_classification"] == "unknown"
    assert rows["Unproven Traded"]["cap_hold"] is None
    assert rows["Unproven Traded"]["hold_rule"] == "unknown_rights_classification"
    assert rows["Signed Reset"]["rights_classification"] == "early_qualifying"
    assert rows["Signed Reset"]["cap_hold"] == 26_000_000
    assert rows["Signed Reset"]["hold_rule"] == "early_qualifying_veteran_130_percent"


def test_scenario_renounce_removes_hold_and_opens_roster_spot():
    con = wiring_con()
    try:
        out = evaluate_cap_scenario(con, {
            "team": "BOS", "season": "2027-28",
            "moves": [{"kind": "renounce", "player": "Veteran FA"}]})
    finally:
        con.close()
    assert out["ok"] is True
    assert out["pay_before"] == 46_000_000
    assert out["pay_after"] == 46_000_000
    assert out["cap_holds_before"] == 60_000_000
    assert out["cap_holds_after"] == 30_000_000
    assert out["roster_charges_before"] == 2_987_078
    assert out["roster_charges_after"] == 4_480_617
    assert out["team_salary_before"] == 108_987_078
    assert out["team_salary_after"] == 80_480_617
    assert out["cap_room_before"] == 72_470_022
    assert out["cap_room_after"] == 100_976_483
    assert out["cap_hold_events"][0]["kind"] == "renounced"
    veteran = next(row for row in out["cap_hold_details"] if row["player"] == "Veteran FA")
    assert veteran["included_in_team_salary_before"] is True
    assert veteran["included_in_team_salary_after"] is False
    assert veteran["money_unit"] == "usd_dollars"


def test_option_decline_activates_option_dependent_rookie_hold():
    con = wiring_con()
    try:
        out = evaluate_cap_scenario(con, {
            "team": "BOS", "season": "2027-28",
            "moves": [{"kind": "option_decision", "player": "Option Rookie",
                       "exercise": False}]})
    finally:
        con.close()
    assert out["ok"] is True
    assert out["pay_before"] == 46_000_000
    assert out["pay_after"] == 40_000_000
    assert out["cap_holds_before"] == 60_000_000
    assert out["cap_holds_after"] == 66_000_000
    assert out["roster_charges_before"] == out["roster_charges_after"]
    assert out["team_salary_before"] == out["team_salary_after"]
    option = next(row for row in out["cap_hold_details"] if row["player"] == "Option Rookie")
    assert option["scenario_dependency"] == "option_decision_required"
    assert option["included_in_team_salary_before"] is False
    assert option["included_in_team_salary_after"] is True
    assert any(event["kind"] == "option_declined" for event in out["cap_hold_events"])


def test_signing_own_free_agent_extinguishes_hold():
    con = wiring_con()
    try:
        out = evaluate_cap_scenario(con, {
            "team": "BOS", "season": "2027-28",
            "moves": [{"kind": "signing", "player": "Veteran FA",
                       "label": "Veteran FA", "amount": 12_000_000}]})
    finally:
        con.close()
    assert out["ok"] is True
    assert out["pay_after"] == 58_000_000
    assert out["cap_holds_before"] == 60_000_000
    assert out["cap_holds_after"] == 30_000_000
    assert out["team_salary_after"] - out["team_salary_before"] == -18_000_000
    assert any(event["kind"] == "signed" and event["player"] == "Veteran FA"
               for event in out["cap_hold_events"])


def test_option_player_sign_or_renounce_requires_prior_decline():
    con = wiring_con()
    try:
        sign = evaluate_cap_scenario(con, {
            "team": "BOS", "season": "2027-28",
            "moves": [{"kind": "signing", "player": "Option Rookie",
                       "label": "Option Rookie", "amount": 12_000_000}]})
        renounce = evaluate_cap_scenario(con, {
            "team": "BOS", "season": "2027-28",
            "moves": [{"kind": "renounce", "player": "Option Rookie"}]})
        sequence = evaluate_cap_scenario(con, {
            "team": "BOS", "season": "2027-28",
            "moves": [{"kind": "option_decision", "player": "Option Rookie",
                       "exercise": False},
                      {"kind": "signing", "player": "Option Rookie",
                       "label": "Option Rookie", "amount": 12_000_000}]})
    finally:
        con.close()
    assert sign["pay_after"] == sign["pay_before"]
    assert any("prior option decision decline" in error["error"]
               for error in sign["errors"])
    assert not any(event["kind"] == "signed" and event["player"] == "Option Rookie"
                   for event in sign["cap_hold_events"])
    assert renounce["cap_holds_after"] == renounce["cap_holds_before"]
    assert any("prior option decision decline" in error["error"]
               for error in renounce["errors"])
    assert not any(event["kind"] == "renounced" and event["player"] == "Option Rookie"
                   for event in renounce["cap_hold_events"])
    assert sequence["errors"] == []
    assert sequence["pay_after"] == 52_000_000
    assert [event["kind"] for event in sequence["cap_hold_events"]][:2] \
        == ["option_declined", "signed"]


def test_signing_own_free_agent_replaces_hold_in_validation_room():
    con = wiring_con()
    try:
        out = evaluate_cap_scenario(con, {
            "team": "BOS", "season": "2027-28",
            "moves": [{"kind": "signing", "player": "Veteran FA",
                       "label": "Veteran FA", "amount": 80_000_000,
                       "years": 1, "mechanism": "cap_room"}]})
    finally:
        con.close()
    validation = out["signing_validations"][0]
    assert validation["outcome"] == "legal_approximation"
    assert validation["mechanism_selected"] == "cap_room"
    assert validation["blocking_issues"] == []
    assert out["team_salary_before"] == 108_987_078
    assert out["team_salary_after"] == 158_987_078
    assert out["cap_holds_after"] == 30_000_000


def wiring_scenario(moves, mutate=None):
    con = wiring_con()
    try:
        if mutate is not None:
            mutate(con)
        return evaluate_cap_scenario(con, {
            "team": "BOS", "season": "2027-28", "moves": moves})
    finally:
        con.close()


def signing_move(player, amount):
    return {"kind": "signing", "player": player, "label": player,
            "amount": amount, "years": 1, "mechanism": "cap_room"}


def assert_boundary(out, amount, legal, cap_room_after, illegal_indices):
    validation = out["signing_validations"][-1]
    assert validation["amount"] == amount
    assert validation["legal"] is legal
    assert validation["outcome"] == ("legal_approximation" if legal else "illegal")
    assert out["cap_room_after"] == cap_room_after
    assert out["includes_illegal_moves"] is bool(illegal_indices)
    assert out["illegal_move_indices"] == illegal_indices
    assert "chronologically applies" in out["meta"]["illegal_move_state_disclosure"]


def test_external_signing_displaces_one_roster_charge_at_exact_boundary():
    for amount, legal, room, indices in [
            (73_963_561, True, 0, []),
            (73_963_562, False, -1, [0])]:
        out = wiring_scenario([signing_move("External Wing", amount)])
        assert out["errors"] == []
        assert out["cap_room_before"] == 72_470_022
        assert out["roster_charges_before"] == 2_987_078
        assert out["roster_charges_after"] == 1_493_539
        assert_boundary(out, amount, legal, room, indices)


def test_renounce_then_resign_does_not_subtract_extinguished_hold_twice():
    for amount, legal, room, indices in [
            (102_470_022, True, 0, []),
            (102_470_023, False, -1, [1])]:
        out = wiring_scenario([
            {"kind": "renounce", "player": "Veteran FA"},
            signing_move("Veteran FA", amount)])
        assert out["errors"] == []
        assert [event["kind"] for event in out["cap_hold_events"]] \
            == ["renounced", "signed"]
        assert out["roster_charges_after"] == 2_987_078
        assert_boundary(out, amount, legal, room, indices)


def test_double_signing_does_not_subtract_extinguished_hold_twice():
    for amount, legal, room, indices in [
            (91_963_561, True, 0, []),
            (91_963_562, False, -1, [1])]:
        out = wiring_scenario([
            signing_move("Veteran FA", 12_000_000),
            signing_move("Veteran FA", amount)])
        assert out["errors"] == []
        assert out["signing_validations"][0]["legal"] is True
        assert out["cap_holds_after"] == 30_000_000
        assert out["roster_charges_after"] == 1_493_539
        assert_boundary(out, amount, legal, room, indices)


def test_active_own_free_agent_resign_does_not_displace_a_roster_charge():
    for amount, legal, room, indices in [
            (102_470_022, True, 0, []),
            (102_470_023, False, -1, [0])]:
        out = wiring_scenario([signing_move("Veteran FA", amount)])
        assert out["errors"] == []
        assert out["roster_charges_before"] == 2_987_078
        assert out["roster_charges_after"] == 2_987_078
        assert_boundary(out, amount, legal, room, indices)


def test_no_roster_charge_means_no_signing_displacement():
    def ten_players(con):
        con.execute("UPDATE silver_cap_room SET PLAYERS_UNDER_CONTRACT = 10")
    for amount, legal, room, indices in [
            (75_457_100, True, 0, []),
            (75_457_101, False, -1, [0])]:
        out = wiring_scenario(
            [signing_move("External Wing", amount)], mutate=ten_players)
        assert out["errors"] == []
        assert out["roster_charges_before"] == 0
        assert out["roster_charges_after"] == 0
        assert_boundary(out, amount, legal, room, indices)


def test_unvalidated_signing_state_is_disclosed_separately():
    move = signing_move("Bird Case", 10_000_000)
    move["mechanism"] = "bird"
    out = wiring_scenario([move])
    assert out["signing_validations"][0]["outcome"] == "unknown"
    assert out["includes_illegal_moves"] is False
    assert out["illegal_move_indices"] == []
    assert out["includes_unvalidated_moves"] is True
    assert out["unvalidated_move_indices"] == [0]


def test_same_scenario_sign_then_trade_out_is_explicitly_rejected():
    out = wiring_scenario([
        signing_move("External Wing", 10_000_000),
        {"kind": "trade_out", "player": "External Wing"}])
    assert out["errors"] == [{
        "move": "1",
        "error": "trade_out of External Wing after a same-scenario signing is "
                 "unsupported sign-and-trade sequencing; atomic sign-and-trade, "
                 "BYC, and coupled hard-cap treatment are outside cap scenario "
                 "validation v1"}]
    assert out["pay_after"] == out["pay_before"] + 10_000_000
    assert out["includes_illegal_moves"] is False
    assert out["illegal_move_indices"] == []
    assert "explicitly rejected" in out["meta"]["sign_and_trade_scope"]


def legacy_cap_scenario(con, payload, monkeypatch):
    monkeypatch.setattr("shared.tools.league.store.connect",
                        lambda read_only=True: con.cursor())
    from shared.tools import get_cap_scenario
    return get_cap_scenario.invoke(payload)


def test_legacy_get_cap_scenario_rejects_pending_option_player_signing(monkeypatch):
    con = wiring_con()
    try:
        out = legacy_cap_scenario(con, {
            "team": "BOS", "season": "2027-28",
            "signings": "Option Rookie=12000000"}, monkeypatch)
    finally:
        con.close()
    assert out["ok"] is False
    assert "signing Option Rookie requires a prior option decision decline" in out["error"]
    assert "option salary is still committed" in out["error"]


def test_legacy_get_cap_scenario_preserves_active_hold_resigning(monkeypatch):
    con = wiring_con()
    try:
        out = legacy_cap_scenario(con, {
            "team": "BOS", "season": "2027-28",
            "signings": "Veteran FA=12000000"}, monkeypatch)
    finally:
        con.close()
    assert out["ok"] is True
    assert out["signing_validations"][0]["legal"] is True
    assert out["summary"]["cap_holds_before"] == 60_000_000
    assert out["summary"]["cap_holds_after"] == 30_000_000
    assert out["summary"]["team_salary_after"] - out["summary"]["team_salary_before"] == -18_000_000
