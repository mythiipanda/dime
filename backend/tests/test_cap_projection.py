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
