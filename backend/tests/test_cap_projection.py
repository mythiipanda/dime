import pytest


def memory_con(rows=None):
    import duckdb
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE silver_salaries ("
        "PLAYER_NAME VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, GUARANTEED BIGINT, "
        "SALARY_2026_27 BIGINT, SALARY_2027_28 BIGINT, SALARY_2028_29 BIGINT, "
        "SALARY_2029_30 BIGINT, "
        "OPTION_2026_27 VARCHAR, OPTION_2027_28 VARCHAR, OPTION_2028_29 VARCHAR, OPTION_2029_30 VARCHAR)")
    con.executemany(
        "INSERT INTO silver_salaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows if rows is not None else [
            ("Alpha", "TST", 1, 60_000_000,
             20_000_000, 20_000_000, 20_000_000, None, None, None, None, None),
            ("Bravo", "TST", 2, 30_000_000,
             10_000_000, 10_000_000, 10_000_000, None, None, None, None, None),
            ("Charlie", "OTH", 3, 48_000_000,
             12_000_000, 12_000_000, 12_000_000, 12_000_000, None, None, None, None),
        ])
    return con


def salary_row(player, team, player_id, guaranteed, salaries, row_kind="roster"):
    padded = list(salaries) + [None] * (4 - len(salaries))
    return (player, team, player_id, guaranteed, *padded,
            None, None, None, None, row_kind, "2026-27")


def memory_dead_con(rows):
    import duckdb
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE silver_salaries ("
        "PLAYER_NAME VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, GUARANTEED BIGINT, "
        "SALARY_2026_27 BIGINT, SALARY_2027_28 BIGINT, SALARY_2028_29 BIGINT, "
        "SALARY_2029_30 BIGINT, "
        "OPTION_2026_27 VARCHAR, OPTION_2027_28 VARCHAR, OPTION_2028_29 VARCHAR, OPTION_2029_30 VARCHAR, "
        "ROW_KIND VARCHAR, _season VARCHAR)")
    con.executemany(
        "INSERT INTO silver_salaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows)
    return con


def project(con, moves, season="2026-27", team="TST"):
    from shared.tools.league.cap_projection import project_cap_scenario
    return project_cap_scenario(con, {"team": team, "season": season, "moves": moves})


def block(out, season):
    return next(s for s in out["seasons"] if s["season"] == season)


def test_baseline_no_moves_projects_warehouse_schedule_per_season():
    con = memory_con()
    try:
        out = project(con, [])
    finally:
        con.close()
    assert out["ok"] is True
    assert [s["season"] for s in out["seasons"]] == ["2026-27", "2027-28", "2028-29", "2029-30"]
    assert block(out, "2026-27")["pay_before"] == 30_000_000
    assert block(out, "2027-28")["pay_before"] == 30_000_000
    assert block(out, "2028-29")["pay_before"] == 30_000_000
    assert block(out, "2029-30")["pay_before"] == 0
    assert all(s["pay_after"] == s["pay_before"] for s in out["seasons"])


def test_one_year_signing_affects_only_its_target_season():
    con = memory_con()
    try:
        out = project(con, [{"kind": "signing", "amount": 5_000_000, "season": "2027-28"}])
    finally:
        con.close()
    assert block(out, "2026-27")["pay_after"] == 30_000_000
    assert block(out, "2027-28")["pay_after"] == 35_000_000
    assert block(out, "2028-29")["pay_after"] == 30_000_000
    assert any("one-year" in d for d in out["disclosures"])


def test_multi_year_signing_carries_salary_across_the_term():
    con = memory_con()
    try:
        out = project(con, [{"kind": "signing", "amount": 12_000_000, "years": 2,
                             "exception": "mle", "season": "2026-27"}])
    finally:
        con.close()
    assert block(out, "2026-27")["pay_after"] == 30_000_000 + 12_000_000
    assert block(out, "2027-28")["pay_after"] == 30_000_000 + 12_000_000
    assert block(out, "2028-29")["pay_after"] == 30_000_000
    first_year = block(out, "2026-27")
    second_year = block(out, "2027-28")
    mle_first = next(e for e in first_year["exceptions"] if e["exception"] == "mle")
    mle_second = next(e for e in second_year["exceptions"] if e["exception"] == "mle")
    assert mle_first["used"] == 12_000_000
    assert mle_second["used"] == 0
    assert first_year["roster_after"] == first_year["roster_before"] + 1
    assert second_year["roster_after"] == second_year["roster_before"]
    assert any("flat" in d for d in out["disclosures"])


def test_multi_year_signing_beyond_horizon_discloses_truncation():
    con = memory_con()
    try:
        out = project(con, [{"kind": "signing", "amount": 5_000_000, "years": 5,
                             "season": "2028-29"}])
    finally:
        con.close()
    assert block(out, "2028-29")["pay_after"] == 30_000_000 + 5_000_000
    assert block(out, "2029-30")["pay_after"] == 5_000_000
    assert any("horizon" in w for w in out["warnings"])


def rows_of(out, season):
    return {r["player"]: r for r in block(out, season)["players"]}


def test_trade_out_row_leaves_all_forward_seasons():
    con = memory_con()
    try:
        out = project(con, [{"kind": "trade_out", "player": "Alpha", "season": "2026-27"}])
    finally:
        con.close()
    for season in ("2026-27", "2027-28", "2028-29"):
        assert "Alpha" not in rows_of(out, season), f"Alpha row still present in {season}"
        assert "Bravo" in rows_of(out, season)


def test_trade_in_row_arrives_with_exact_salary_schedule():
    con = memory_con()
    try:
        out = project(con, [{"kind": "trade_in", "player": "Charlie", "season": "2026-27"}])
    finally:
        con.close()
    for season in ("2026-27", "2027-28", "2028-29", "2029-30"):
        row = rows_of(out, season).get("Charlie")
        assert row is not None, f"Charlie missing in {season}"
        assert row["salary"] == 12_000_000


def test_signing_row_carries_full_shape_across_the_term():
    con = memory_con()
    try:
        out = project(con, [{"kind": "signing", "label": "Demo Wing", "amount": 12_000_000,
                             "years": 2, "season": "2026-27"}])
    finally:
        con.close()
    row1 = rows_of(out, "2026-27").get("Demo Wing")
    row2 = rows_of(out, "2027-28").get("Demo Wing")
    assert row1 and row1["salary"] == 12_000_000
    assert row2 and row2["salary"] == 12_000_000
    assert "Demo Wing" not in rows_of(out, "2028-29")


def test_waive_removes_row_and_dead_money_never_appears_as_row():
    con = memory_con()
    try:
        out = project(con, [{"kind": "waive", "player": "Alpha", "season": "2026-27"}])
    finally:
        con.close()
    for season in ("2026-27", "2027-28", "2028-29"):
        rows = rows_of(out, season)
        assert "Alpha" not in rows, f"waived Alpha row present in {season}"
        assert all("dead" not in name.lower() for name in rows)


def test_declined_option_removes_row_from_that_season_forward():
    rows = [
        ("Alpha", "TST", 1, 60_000_000,
         20_000_000, 20_000_000, 20_000_000, None, None, "player", None, None),
        ("Bravo", "TST", 2, 30_000_000,
         10_000_000, 10_000_000, 10_000_000, None, None, None, None, None),
    ]
    con = memory_con(rows)
    try:
        out = project(con, [{"kind": "option_decision", "player": "Alpha", "exercise": False,
                             "season": "2027-28"}])
    finally:
        con.close()
    assert "Alpha" in rows_of(out, "2026-27")
    assert "Alpha" not in rows_of(out, "2027-28")
    assert "Alpha" not in rows_of(out, "2028-29")


def test_trade_out_removes_player_in_trade_season_and_forward():
    con = memory_con()
    try:
        out = project(con, [{"kind": "trade_out", "player": "Alpha", "season": "2026-27"}])
    finally:
        con.close()
    assert block(out, "2026-27")["pay_after"] == 10_000_000
    assert block(out, "2027-28")["pay_after"] == 10_000_000
    assert block(out, "2028-29")["pay_after"] == 10_000_000
    assert out["errors"] == []


def test_trade_in_adds_contract_schedule_in_trade_season_and_forward():
    con = memory_con()
    try:
        out = project(con, [{"kind": "trade_in", "player": "Charlie", "season": "2026-27"}])
    finally:
        con.close()
    assert block(out, "2026-27")["pay_after"] == 42_000_000
    assert block(out, "2027-28")["pay_after"] == 42_000_000
    assert block(out, "2028-29")["pay_after"] == 42_000_000
    assert block(out, "2029-30")["pay_after"] == 12_000_000


def test_future_trade_applies_only_from_its_season():
    con = memory_con()
    try:
        out = project(con, [{"kind": "trade_out", "player": "Alpha", "season": "2027-28"}])
    finally:
        con.close()
    assert block(out, "2026-27")["pay_after"] == 30_000_000
    assert block(out, "2027-28")["pay_after"] == 10_000_000
    assert block(out, "2028-29")["pay_after"] == 10_000_000


def test_non_stretch_waive_leaves_dead_money_across_remaining_years():
    con = memory_con()
    try:
        out = project(con, [{"kind": "waive", "player": "Alpha", "season": "2026-27"}])
    finally:
        con.close()
    y1 = block(out, "2026-27")
    assert y1["pay_after"] == 10_000_000 + 20_000_000
    y2 = block(out, "2027-28")
    assert y2["pay_after"] == 10_000_000 + 20_000_000
    dead = [e for e in y2["effects"] if e["kind"] == "waive_dead"]
    assert dead and dead[0]["exactness"] == "proxy"
    assert "per-year guarantee allocations unavailable" in dead[0]["disclosure"]


def test_stretch_waive_spreads_installments_forward():
    con = memory_con()
    try:
        out = project(con, [{"kind": "waive", "player": "Bravo", "stretch": True, "season": "2026-27"}])
    finally:
        con.close()
    y1 = block(out, "2026-27")
    installments = [e for s in out["seasons"] for e in s["effects"] if e["kind"] == "waive_stretch"]
    assert installments, "stretch installments must project forward"
    assert all(e["delta"] == installments[0]["delta"] for e in installments)
    assert y1["pay_after"] < 30_000_000


def test_preexisting_dead_money_enters_baseline_with_exact_fixture_figures():
    rows = [
        salary_row("Roster Wing", "DAL", 1, 10_000_000, [10_000_000]),
        salary_row("Klay Thompson", "DAL", 2, 7_660_317, [7_660_317], "dead_money"),
        salary_row("Olivier-Maxence Prosper", "DAL", 3, 1_002_360, [1_002_360], "dead_money"),
    ]
    con = memory_dead_con(rows)
    try:
        out = project(con, [], team="DAL")
    finally:
        con.close()
    base = block(out, "2026-27")
    assert base["roster_payroll"] == 10_000_000
    assert base["dead_money"] == 8_662_677
    assert base["pay_before"] == 18_662_677
    assert base["pay_after"] == 18_662_677
    assert base["cap_room"] == base["lines"]["cap"] - 18_662_677
    assert base["state"]["room_apron2"] == base["lines"]["apron2"] - 18_662_677
    detail = {row["player"]: row["salary"] for row in base["dead_money_detail"]}
    assert detail == {"Klay Thompson": 7_660_317,
                      "Olivier-Maxence Prosper": 1_002_360}
    alias = {row["player"]: row["salary"] for row in base["dead_money_players"]}
    assert alias == detail
    assert [row["player"] for row in base["players"]] == ["Roster Wing"]
    assert base["roster_before"] == 1


def test_dead_money_rows_follow_their_own_schedule_length():
    rows = [
        salary_row("Roster Wing", "DAL", 1, 30_000_000,
                   [10_000_000, 10_000_000, 10_000_000]),
        salary_row("Klay Thompson", "DAL", 2, 10_660_317,
                   [7_660_317, 3_000_000], "dead_money"),
        salary_row("Olivier-Maxence Prosper", "DAL", 3, 1_002_360,
                   [1_002_360], "dead_money"),
    ]
    con = memory_dead_con(rows)
    try:
        out = project(con, [], team="DAL")
    finally:
        con.close()
    assert block(out, "2026-27")["dead_money"] == 8_662_677
    assert block(out, "2026-27")["pay_before"] == 18_662_677
    assert block(out, "2027-28")["dead_money"] == 3_000_000
    assert block(out, "2027-28")["pay_before"] == 13_000_000
    assert block(out, "2028-29")["dead_money"] == 0
    assert block(out, "2028-29")["dead_money_detail"] == []
    assert block(out, "2028-29")["pay_before"] == 10_000_000


def test_dead_money_uses_only_the_latest_salary_snapshot():
    current = salary_row("Klay Thompson", "DAL", 2, 7_660_317, [7_660_317], "dead_money")
    stale = tuple(list(current[:-1]) + ["2025-26"])
    rows = [
        salary_row("Roster Wing", "DAL", 1, 10_000_000, [10_000_000]),
        current,
        stale,
    ]
    con = memory_dead_con(rows)
    try:
        out = project(con, [], team="DAL")
    finally:
        con.close()
    base = block(out, "2026-27")
    assert base["dead_money"] == 7_660_317
    assert base["pay_before"] == 17_660_317
    assert len(base["dead_money_detail"]) == 1


def test_dead_money_rows_do_not_count_as_roster_players():
    rows = [salary_row(f"Roster {i}", "DAL", i, 1_000_000, [1_000_000])
            for i in range(1, 15)]
    rows.extend([
        salary_row("Klay Thompson", "DAL", 20, 7_660_317, [7_660_317], "dead_money"),
        salary_row("Olivier-Maxence Prosper", "DAL", 21, 1_002_360, [1_002_360], "dead_money"),
    ])
    con = memory_dead_con(rows)
    try:
        out = project(con, [], team="DAL")
    finally:
        con.close()
    base = block(out, "2026-27")
    assert base["roster_before"] == 14
    assert base["roster_after"] == 14
    assert len(base["players"]) == 14
    assert base["roster_issues"] == []


def test_hypothetical_waive_dead_money_stacks_with_preexisting_dead_money_once():
    rows = [
        salary_row("Alpha", "TST", 1, 15_000_000, [10_000_000, 10_000_000]),
        salary_row("Klay Thompson", "TST", 2, 10_660_317,
                   [7_660_317, 3_000_000], "dead_money"),
    ]
    con = memory_dead_con(rows)
    try:
        out = project(con, [{"kind": "waive", "player": "Alpha", "season": "2026-27"}])
    finally:
        con.close()
    first = block(out, "2026-27")
    second = block(out, "2027-28")
    assert first["pay_before"] == 17_660_317
    assert first["pay_after"] == 17_660_317
    assert first["roster_after"] == 0
    assert second["dead_money"] == 3_000_000
    assert second["pay_before"] == 13_000_000
    assert second["pay_after"] == 8_000_000
    hypo = [e for e in second["effects"] if e["kind"] == "waive_dead"]
    assert len(hypo) == 1
    assert hypo[0]["delta"] == 5_000_000


def test_signing_beyond_cap_room_is_flagged_order_dependent():
    rows = [
        ("Alpha", "TST", 1, 60_000_000,
         20_000_000, 20_000_000, 20_000_000, None, None, None, None, None),
        ("Maxed", "TST", 2, 500_000_000,
         160_000_000, 160_000_000, 160_000_000, None, None, None, None, None),
    ]
    con = memory_con(rows)
    try:
        out = project(con, [{"kind": "signing", "amount": 30_000_000, "season": "2026-27"}])
    finally:
        con.close()
    notes = block(out, "2026-27")["ordering_notes"]
    assert notes and "order-dependent" in notes[0]


def test_trade_out_before_sign_opens_room_sign_before_trade_is_flagged():
    rows = [
        ("Alpha", "TST", 1, 30_000_000,
         30_000_000, 30_000_000, None, None, None, None, None, None),
        ("Maxed", "TST", 2, 500_000_000,
         140_000_000, 140_000_000, 140_000_000, None, None, None, None, None),
    ]
    con = memory_con(rows)
    try:
        trade_first = project(con, [
            {"kind": "trade_out", "player": "Alpha", "season": "2026-27"},
            {"kind": "signing", "amount": 20_000_000, "season": "2026-27"},
        ])
        sign_first = project(con, [
            {"kind": "signing", "amount": 20_000_000, "season": "2026-27"},
            {"kind": "trade_out", "player": "Alpha", "season": "2026-27"},
        ])
    finally:
        con.close()
    trade_notes = block(trade_first, "2026-27")["ordering_notes"]
    sign_notes = block(sign_first, "2026-27")["ordering_notes"]
    assert len(sign_notes) > len(trade_notes), (
        "signing before the salary-clearing trade must raise the ordering flag that trading first avoids")


def test_option_decline_removes_only_the_declined_season():
    rows = [
        ("Alpha", "TST", 1, 60_000_000,
         20_000_000, 20_000_000, 20_000_000, None, None, None, None, None),
        ("Opt", "TST", 2, 10_000_000,
         None, 10_000_000, None, None, None, "team", None, None),
    ]
    con = memory_con(rows)
    try:
        out = project(con, [{"kind": "option_decision", "player": "Opt", "exercise": False, "season": "2027-28"}])
    finally:
        con.close()
    assert block(out, "2026-27")["pay_after"] == 20_000_000
    assert block(out, "2027-28")["pay_after"] == 20_000_000
    assert block(out, "2028-29")["pay_after"] == 20_000_000


def test_moves_outside_horizon_error_honestly():
    con = memory_con()
    try:
        out = project(con, [{"kind": "signing", "amount": 1, "season": "2031-32"}])
    finally:
        con.close()
    assert out["errors"] and "outside the projection horizon" in out["errors"][0]["error"]


def test_exactness_labels_present_on_effects():
    con = memory_con()
    try:
        out = project(con, [
            {"kind": "trade_out", "player": "Alpha"},
            {"kind": "signing", "amount": 2_000_000},
        ])
    finally:
        con.close()
    for season in out["seasons"]:
        for effect in season["effects"]:
            assert effect["exactness"] in ("exact", "derived", "proxy", "unresolved")


def test_extend_stacks_after_contract_end_with_unvalidated_label():
    con = memory_con()
    try:
        out = project(con, [{"kind": "extend", "player": "Alpha", "years": 2,
                             "first_year_amount": 25_000_000, "season": "2026-27"}])
    finally:
        con.close()
    assert out["errors"] == []
    assert block(out, "2028-29")["pay_after"] == 30_000_000
    y4 = block(out, "2029-30")
    assert y4["pay_after"] == 25_000_000
    ext = [e for e in y4["effects"] if e["kind"] == "extend"]
    assert ext and ext[0]["exactness"] == "unvalidated"
    assert "unvalidated against max-extension rules" in ext[0]["disclosure"]


def test_extend_rejects_players_not_on_team():
    con = memory_con()
    try:
        out = project(con, [{"kind": "extend", "player": "Charlie", "years": 2,
                             "first_year_amount": 25_000_000}])
    finally:
        con.close()
    assert out["errors"] and "could not match" in out["errors"][0]["error"]


def test_mle_signing_skips_room_check_and_triggers_hard_cap_state():
    rows = [
        ("Alpha", "TST", 1, 60_000_000,
         20_000_000, 20_000_000, 20_000_000, None, None, None, None, None),
        ("Maxed", "TST", 2, 500_000_000,
         160_000_000, 160_000_000, 160_000_000, None, None, None, None, None),
    ]
    con = memory_con(rows)
    try:
        out = project(con, [{"kind": "signing", "amount": 13_000_000,
                             "exception": "mle", "season": "2026-27"}])
    finally:
        con.close()
    y1 = block(out, "2026-27")
    assert y1["ordering_notes"] == [], "exception signings are not room-checked"
    assert y1["hard_cap"] == "mle apron"
    assert y1["exception_usage"] == ["mle"]
    assert y1["hard_cap_violation"] == "" or "hard-capped" in y1["hard_cap_violation"]


def test_cap_room_signing_still_room_checked_by_default():
    rows = [
        ("Alpha", "TST", 1, 60_000_000,
         20_000_000, 20_000_000, 20_000_000, None, None, None, None, None),
        ("Maxed", "TST", 2, 500_000_000,
         160_000_000, 160_000_000, 160_000_000, None, None, None, None, None),
    ]
    con = memory_con(rows)
    try:
        out = project(con, [{"kind": "signing", "amount": 13_000_000, "season": "2026-27"}])
    finally:
        con.close()
    assert block(out, "2026-27")["ordering_notes"], "default cap-room signings stay room-checked"


def test_unknown_exception_errors_honestly():
    con = memory_con()
    try:
        out = project(con, [{"kind": "signing", "amount": 1_000_000, "exception": "tpje"}])
    finally:
        con.close()
    assert out["errors"] and "unknown exception" in out["errors"][0]["error"]


def test_hard_cap_violation_fires_over_first_apron():
    rows = [
        ("Alpha", "TST", 1, 60_000_000,
         20_000_000, 20_000_000, 20_000_000, None, None, None, None, None),
        ("Maxed", "TST", 2, 800_000_000,
         200_000_000, 200_000_000, 200_000_000, None, None, None, None, None),
    ]
    con = memory_con(rows)
    try:
        out = project(con, [{"kind": "signing", "amount": 13_000_000,
                             "exception": "mle", "season": "2026-27"}])
    finally:
        con.close()
    y1 = block(out, "2026-27")
    assert y1["pay_after"] == 233_000_000
    assert "hard-capped at the first apron" in y1["hard_cap_violation"]


def memory_con_with_holds(fa_rows):
    con = memory_con()
    con.execute(
        "CREATE TABLE silver_free_agents ("
        "PLAYER_NAME VARCHAR, TEAM VARCHAR, BREF_SLUG VARCHAR, FA_YEAR BIGINT, "
        "FA_TYPE VARCHAR, PRIOR_SALARY BIGINT, CAP_HOLD_EST BIGINT)")
    con.executemany("INSERT INTO silver_free_agents VALUES (?, ?, ?, ?, ?, ?, ?)", fa_rows)
    return con


def test_cap_holds_enter_base_season_payroll_only():
    con = memory_con_with_holds([("Departed", "TST", "depart01", 2026, "ufa", 15_000_000, 20_000_000)])
    try:
        out = project(con, [])
    finally:
        con.close()
    assert out["ok"] is True
    base = block(out, "2026-27")
    assert base["pay_before"] == 50_000_000
    assert base["cap_holds"] == 20_000_000
    assert base["cap_hold_details"][0]["player"] == "Departed"
    assert base["cap_hold_details"][0]["amount"] == 20_000_000
    assert block(out, "2027-28")["pay_before"] == 30_000_000
    assert "cap_holds" not in block(out, "2027-28")
    assert any("cap holds are included" in d for d in out["disclosures"])


def test_renounce_releases_hold_and_ordering_is_sensitive():
    con = memory_con_with_holds([("Departed", "TST", "depart01", 2026, "ufa", 15_000_000, 20_000_000)])
    try:
        room_before = 164_961_000 - 50_000_000
        signing = room_before + 10_000_000
        out = project(con, [
            {"kind": "renounce", "player": "Departed"},
            {"kind": "signing", "amount": signing},
        ])
        out_reversed = project(con, [
            {"kind": "signing", "amount": signing},
            {"kind": "renounce", "player": "Departed"},
        ])
    finally:
        con.close()
    base = block(out, "2026-27")
    renounce_effect = next(e for e in base["effects"] if e["kind"] == "renounce")
    assert renounce_effect["delta"] == -20_000_000
    assert base["ordering_notes"] == []
    reversed_base = block(out_reversed, "2026-27")
    assert len(reversed_base["ordering_notes"]) == 1
    assert "order-dependent" in reversed_base["ordering_notes"][0]


def test_renounce_without_hold_errors_honestly():
    con = memory_con()
    try:
        out = project(con, [{"kind": "renounce", "player": "Alpha"}])
    finally:
        con.close()
    assert any("no active cap hold" in e["error"] for e in out["errors"])


def test_renounce_in_forward_season_applies_where_the_hold_lives():
    con = memory_con_with_holds([("Departing", "TST", "depart02", 2027, "ufa", 15_000_000, 18_000_000)])
    try:
        out = project(con, [{"kind": "renounce", "player": "Departing", "season": "2027-28"}])
    finally:
        con.close()
    forward = block(out, "2027-28")
    assert forward["pay_before"] == 48_000_000
    assert forward["cap_holds"] == 18_000_000
    renounce_effect = next(e for e in forward["effects"] if e["kind"] == "renounce")
    assert renounce_effect["delta"] == -18_000_000
    assert forward["pay_after"] == 30_000_000
    assert out["errors"] == []


def test_renounce_in_season_without_a_hold_errors_honestly():
    con = memory_con_with_holds([("Departed", "TST", "depart01", 2026, "ufa", 15_000_000, 20_000_000)])
    try:
        out = project(con, [{"kind": "renounce", "player": "Departed", "season": "2027-28"}])
    finally:
        con.close()
    assert any("no active cap hold" in e["error"] for e in out["errors"])


def test_double_renounce_errors():
    con = memory_con_with_holds([("Departed", "TST", "depart01", 2026, "ufa", 15_000_000, 20_000_000)])
    try:
        out = project(con, [
            {"kind": "renounce", "player": "Departed"},
            {"kind": "renounce", "player": "Departed"},
        ])
    finally:
        con.close()
    assert any("already renounced" in e["error"] for e in out["errors"])


def test_exceptions_block_tracks_usage_and_remaining():
    con = memory_con()
    try:
        out = project(con, [{"kind": "signing", "amount": 10_000_000, "exception": "mle"}])
    finally:
        con.close()
    rows = {r["exception"]: r for r in block(out, "2026-27")["exceptions"]}
    assert rows["mle"]["amount"] == 15_044_000
    assert rows["mle"]["used"] == 10_000_000
    assert rows["mle"]["remaining"] == 5_044_000
    assert rows["mle"]["hard_caps"] is True
    assert rows["bae"]["used"] == 0
    assert rows["bae"]["hard_caps"] is False
    assert any("scenario moves only" in d for d in out["disclosures"])


def test_signing_above_exception_amount_is_flagged_not_spilled():
    con = memory_con()
    try:
        out = project(con, [{"kind": "signing", "amount": 20_000_000, "exception": "mle"}])
    finally:
        con.close()
    rows = {r["exception"]: r for r in block(out, "2026-27")["exceptions"]}
    assert rows["mle"]["exceeds"] == 20_000_000
    assert rows["mle"]["remaining"] == 0


def test_exceptions_scale_with_forward_cap_growth():
    con = memory_con()
    try:
        out = project(con, [])
    finally:
        con.close()
    base_rows = {r["exception"]: r for r in block(out, "2026-27")["exceptions"]}
    forward_rows = {r["exception"]: r for r in block(out, "2027-28")["exceptions"]}
    base = block(out, "2026-27")
    forward = block(out, "2027-28")
    ratio = forward["lines"]["cap"] / base["lines"]["cap"]
    assert abs(forward_rows["mle"]["amount"] - round(base_rows["mle"]["amount"] * ratio, -3)) <= 1000


def test_over_apron_marks_ntmle_unavailable():
    con = memory_con()
    try:
        out = project(con, [{"kind": "signing", "amount": 220_000_000, "exception": "bird"}])
    finally:
        con.close()
    rows = {r["exception"]: r for r in block(out, "2026-27")["exceptions"]}
    assert rows["mle"]["unavailable"] is True
    assert rows["bae"]["unavailable"] is True
    assert rows["room"]["unavailable"] is False

def test_trade_exceptions_disclosed_per_season_with_no_payroll_effect():
    con = memory_con()
    try:
        from shared.tools.league.cap_projection import project_cap_scenario
        tpes = [
            {"team": "TST", "amount": 10_534_956, "kind": "ordinary",
             "origin_year": 2026, "exactness": "scenario_derived"},
            {"team": "TST", "amount": 5_000_000, "kind": "ordinary",
             "origin_year": 2024, "exactness": "user_declared"},
            {"team": "OTH", "amount": 9_000_000, "kind": "ordinary",
             "origin_year": 2026, "exactness": "user_declared"},
        ]
        out = project_cap_scenario(con, {"team": "TST", "season": "2026-27", "moves": [], "tpes": tpes})
        first = block(out, "2026-27")
        disclosed = first.get("trade_exceptions") or []
        assert len(disclosed) == 2
        amounts = sorted(row["amount"] for row in disclosed)
        assert amounts == [5_000_000, 10_534_956]
        active = next(row for row in disclosed if row["amount"] == 10_534_956)
        assert active["status"] == "active"
        assert active["exactness"] == "scenario_derived"
        assert "no payroll effect" in active["note"]
        expired = next(row for row in disclosed if row["amount"] == 5_000_000)
        assert expired["status"] == "expired"
        plain = project(con, [])
        assert first["pay_after"] == block(plain, "2026-27")["pay_after"]
        later = block(out, "2028-29")
        later_amounts = sorted(row["amount"] for row in (later.get("trade_exceptions") or []))
        assert later_amounts == sorted(row["amount"] for row in disclosed)
    finally:
        con.close()
