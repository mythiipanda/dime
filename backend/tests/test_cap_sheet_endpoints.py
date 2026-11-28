import pytest

from shared import store


@pytest.fixture()
def con():
    try:
        conn = store.connect(read_only=True)
    except Exception:
        pytest.skip("warehouse unreachable")
    yield conn
    conn.close()


def memory_salary_con():
    import duckdb
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE silver_salaries ("
        "PLAYER_NAME VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, GUARANTEED BIGINT, "
        "SALARY_2026_27 BIGINT, SALARY_2027_28 BIGINT, SALARY_2028_29 BIGINT, "
        "OPTION_2026_27 VARCHAR, OPTION_2027_28 VARCHAR, OPTION_2028_29 VARCHAR)")
    con.executemany(
        "INSERT INTO silver_salaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [("Option Player", "TST", 1, 50_000_000,
          10_000_000, 15_000_000, 20_000_000, None, None, "team"),
         ("Steady Player", "TST", 2, 90_000_000,
          30_000_000, 30_000_000, 30_000_000, None, None, None)])
    return con


def memory_dead_money_con():
    import duckdb
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE silver_salaries ("
        "PLAYER_NAME VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, GUARANTEED BIGINT, "
        "SALARY_2026_27 BIGINT, ROW_KIND VARCHAR)")
    con.executemany(
        "INSERT INTO silver_salaries VALUES (?, ?, ?, ?, ?, ?)",
        [("Roster Wing", "DAL", 1, 10_000_000, 10_000_000, "roster"),
         ("Klay Thompson", "DAL", 2, 7_660_317, 7_660_317, "dead_money"),
         ("Olivier-Maxence Prosper", "DAL", 3, 1_002_360, 1_002_360, "dead_money")])
    return con


def test_future_option_decision_uses_option_year_salary_and_baseline():
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    con = memory_salary_con()
    try:
        out = evaluate_cap_scenario(con, {
            "team": "TST", "season": "2026-27",
            "moves": [{"kind": "option_decision", "player": "Option Player",
                       "season": "2028-29", "exercise": False}]})
    finally:
        con.close()
    assert out["ok"] is True
    assert out["season"] == "2028-29"
    assert out["pay_before"] == 50_000_000
    assert out["pay_after"] == 30_000_000
    option_steps = [s for s in out["steps"] if "option" in s["detail"]]
    assert option_steps and option_steps[0]["delta"] == -20_000_000
    assert out["lines"]["cap"] > 164_961_000
    assert out["errors"] == []


def test_mixed_scenario_rejects_cross_season_option_without_wrong_subtraction():
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    con = memory_salary_con()
    try:
        out = evaluate_cap_scenario(con, {
            "team": "TST", "season": "2026-27",
            "moves": [{"kind": "signing", "label": "X", "amount": 5_000_000},
                      {"kind": "option_decision", "player": "Option Player",
                       "season": "2028-29", "exercise": False}]})
    finally:
        con.close()
    assert out["ok"] is True
    assert out["season"] == "2026-27"
    assert out["pay_before"] == 40_000_000
    assert out["pay_after"] == 45_000_000
    assert any("2028-29" in e["error"] and "one season" in e["error"]
               for e in out["errors"])


def test_option_decision_rejects_missing_per_year_option_data():
    import duckdb
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE silver_salaries ("
            "PLAYER_NAME VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, GUARANTEED BIGINT, "
            "SALARY_2026_27 BIGINT, SALARY_2028_29 BIGINT)")
        con.execute(
            "INSERT INTO silver_salaries VALUES "
            "('Option Player', 'TST', 1, 30000000, 10000000, 20000000)")
        out = evaluate_cap_scenario(con, {
            "team": "TST", "season": "2026-27",
            "moves": [{"kind": "option_decision", "player": "Option Player",
                       "season": "2028-29", "exercise": False}]})
    finally:
        con.close()
    assert out["ok"] is True
    assert out["pay_after"] == out["pay_before"]
    assert any("per-year option data unavailable" in e["error"]
               for e in out["errors"])


def test_projected_cap_room_rows_disclose_projected_lines():
    import duckdb
    from shared.tools.league.cap_sheet import cap_lines_for_season
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE silver_cap_room (CAP_SEASON VARCHAR, PROJECTED_CAP BIGINT, "
            "PROJECTED_TAX BIGINT, PROJECTED_APRON1 BIGINT, PROJECTED_APRON2 BIGINT)")
        con.execute(
            "INSERT INTO silver_cap_room VALUES "
            "('2027-28', 176000000, 214000000, 224000000, 237000000)")
        lines, projected = cap_lines_for_season(con, "2027-28")
    finally:
        con.close()
    assert lines == {"cap": 176_000_000, "tax": 214_000_000,
                     "apron1": 224_000_000, "apron2": 237_000_000}
    assert projected is True


def test_dead_money_rows_are_labeled_components_not_roster_players():
    from shared.tools.league.cap_sheet import cap_sheet_rows
    con = memory_dead_money_con()
    try:
        out = cap_sheet_rows(con, "DAL", "2026-27")
    finally:
        con.close()
    assert out["ok"] is True
    assert [row["player"] for row in out["players"]] == ["Roster Wing"]
    entry = out["totals"]["2026-27"]
    assert entry["roster_payroll"] == 10_000_000
    assert entry["dead_money"] == 8_662_677
    assert entry["committed"] == 18_662_677
    assert entry["payroll"] == 18_662_677
    assert entry["committed"] == entry["roster_payroll"] + entry["dead_money"]
    assert entry["dead_money_detail"] == [
        {"player": "Klay Thompson", "team": "DAL", "salary": 7_660_317},
        {"player": "Olivier-Maxence Prosper", "team": "DAL", "salary": 1_002_360},
    ]
    assert out["dead_money_detail"] == entry["dead_money_detail"]
    assert out["dead_money_unit"] == "usd_dollars"
    assert entry["component_availability"]["dead_money"] is True
    assert entry["component_availability"]["roster_payroll"] is True


def test_payroll_adds_holds_and_charges_without_double_counting_dead_money():
    from shared.tools.league.cap_sheet import cap_sheet_rows
    con = memory_dead_money_con()
    try:
        con.execute(
            "CREATE TABLE silver_cap_room ("
            "TEAM VARCHAR, CAP_SEASON VARCHAR, FA_HOLDS_EST BIGINT, "
            "INCOMPLETE_ROSTER_CHARGES BIGINT)")
        con.execute(
            "INSERT INTO silver_cap_room VALUES ('DAL', '2026-27', 1000000, 500000)")
        out = cap_sheet_rows(con, "DAL", "2026-27")
    finally:
        con.close()
    entry = out["totals"]["2026-27"]
    assert entry["committed"] == 18_662_677
    assert entry["cap_holds"] == 1_000_000
    assert entry["incomplete_roster_charges"] == 500_000
    assert entry["payroll"] == 20_162_677
    assert entry["payroll"] == (entry["committed"] + entry["cap_holds"]
                                + entry["incomplete_roster_charges"])
    assert entry["component_availability"]["cap_holds"] is True
    assert entry["component_availability"]["incomplete_roster_charges"] is True


def test_unlabeled_salary_rows_keep_legacy_aggregate_behavior():
    from shared.tools.league.cap_sheet import cap_sheet_rows
    con = memory_salary_con()
    try:
        out = cap_sheet_rows(con, "TST", "2026-27")
    finally:
        con.close()
    entry = out["totals"]["2026-27"]
    assert len(out["players"]) == 2
    assert entry["roster_payroll"] == 40_000_000
    assert entry["dead_money"] == 0
    assert entry["committed"] == 40_000_000
    assert entry["component_availability"]["dead_money"] is False
    assert entry["component_availability"]["roster_payroll"] is False


def test_sheet_shape_boston(con):
    from shared.tools.league.cap_sheet import cap_sheet_rows
    out = cap_sheet_rows(con, "BOS", "2026-27")
    assert out["ok"] is True, out.get("error")
    assert "2026-27" in out["lines"]
    assert out["lines"]["2026-27"]["cap"] == 164_961_000
    assert out["lines"]["2026-27"]["projected"] is False
    assert len(out["players"]) >= 10
    first = out["players"][0]
    assert first["player"]
    assert first["years"]
    year = first["years"][0]
    assert set(year) == {"season", "salary", "option", "guaranteed"}
    totals = out["totals"]
    assert "2026-27" in totals
    entry = totals["2026-27"]
    for key in ("committed", "roster_payroll", "pending_option", "dead_money",
                "dead_money_detail", "cap_holds", "incomplete_roster_charges",
                "payroll", "component_availability"):
        assert key in entry
    assert entry["committed"] == entry["roster_payroll"] + entry["dead_money"]
    assert entry["payroll"] == (entry["committed"] + entry["cap_holds"]
                                + entry["incomplete_roster_charges"])
    assert {"over_tax", "over_apron1", "over_apron2", "room_apron1", "room_apron2", "room_under_apron2"} <= set(out["state"])


def test_sheet_multi_year_matrix(con):
    from shared.tools.league.cap_sheet import cap_sheet_rows
    out = cap_sheet_rows(con, "BOS", "2026-27")
    seasons = set()
    for player in out["players"]:
        for year in player["years"]:
            seasons.add(year["season"])
    assert len(seasons) >= 5
    assert any("2028" in s or "2029" in s for s in seasons)


def test_cap_lines_projection_behavior(con):
    from shared.tools.league.cap_sheet import cap_lines_for_season
    lines, projected = cap_lines_for_season(con, "2026-27")
    assert projected is False
    assert lines["cap"] == 164_961_000
    lines27, projected27 = cap_lines_for_season(con, "2027-28")
    assert lines27["cap"] > 0
    lines31, projected31 = cap_lines_for_season(con, "2031-32")
    assert projected31 is True
    assert lines31["cap"] > lines27["cap"]
    assert lines31["apron2"] > lines31["apron1"] > lines31["tax"] > lines31["cap"]


def test_scenario_signing_matches_tool_arithmetic(con):
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    out = evaluate_cap_scenario(con, {
        "team": "BOS", "season": "2026-27",
        "moves": [{"kind": "signing", "label": "X", "amount": 12_000_000}]})
    assert out["ok"] is True
    assert out["pay_after"] == out["pay_before"] + 12_000_000
    kinds = [s["kind"] for s in out["steps"]]
    assert kinds == ["payroll", "signing"]
    assert out["steps"][1]["delta"] == 12_000_000


def test_scenario_partial_errors_never_fail_whole_eval(con):
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    out = evaluate_cap_scenario(con, {
        "team": "BOS", "season": "2026-27",
        "moves": [{"kind": "signing", "amount": -5},
                  {"kind": "trade_in", "player": "Nobody Real Ever"},
                  {"kind": "signing", "label": "good", "amount": 5_000_000}]})
    assert out["ok"] is True
    assert len(out["errors"]) == 2
    assert out["pay_after"] == out["pay_before"] + 5_000_000


def test_scenario_unknown_kind_error(con):
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    out = evaluate_cap_scenario(con, {
        "team": "BOS", "season": "2026-27",
        "moves": [{"kind": "teleport", "player": "X"}]})
    assert out["ok"] is True
    assert any("unknown move kind" in e["error"] for e in out["errors"])


def test_scenario_trade_matching_verdict(con):
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    out = evaluate_cap_scenario(con, {
        "team": "BOS", "season": "2026-27",
        "moves": [{"kind": "trade_out", "player": "Payton Pritchard"},
                  {"kind": "trade_in", "player": "Jrue Holiday"}]})
    assert out["ok"] is True
    assert out["matching"] is not None
    assert out["matching"]["legal"] is False
    assert out["matching"]["incoming"] > out["matching"]["allowed_incoming"]


def test_scenario_waive_relief_bounded(con):
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    out = evaluate_cap_scenario(con, {
        "team": "BOS", "season": "2026-27",
        "moves": [{"kind": "waive", "player": "Payton Pritchard"}]})
    assert out["ok"] is True
    deltas = [s["delta"] for s in out["steps"] if s["kind"] == "waive"]
    assert deltas and deltas[0] <= 0
    stretched = evaluate_cap_scenario(con, {
        "team": "BOS", "season": "2026-27",
        "moves": [{"kind": "waive", "player": "Payton Pritchard", "stretch": True}]})
    stretch_deltas = [s["delta"] for s in stretched["steps"] if s["kind"] == "waive"]
    assert stretch_deltas and stretch_deltas[0] <= 0


def test_scenario_requires_moves(con):
    from shared.tools.league.cap_sheet import evaluate_cap_scenario
    out = evaluate_cap_scenario(con, {"team": "BOS", "season": "2026-27", "moves": []})
    assert out["ok"] is False
    out2 = evaluate_cap_scenario(con, {"team": "", "season": "2026-27",
                                       "moves": [{"kind": "signing", "amount": 1}]})
    assert out2["ok"] is False


def test_endpoint_wrappers():
    from analyst.direct_data import product_cap_scenario_eval, product_cap_sheet
    bad = product_cap_sheet.invoke({"team": "", "season": "2026-27"})
    assert bad["ok"] is False
    bad2 = product_cap_scenario_eval.invoke({"payload": {"team": "", "moves": []}})
    assert bad2["ok"] is False


def test_projection_openapi_documents_dead_money_decomposition():
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "analyst" / "http-assets" / "openapi.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    item = spec["paths"]["/api/cap/projection"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["seasons"]["items"]
    properties = item["properties"]
    for key in ("pay_before", "pay_after", "roster_payroll", "dead_money",
                "dead_money_detail", "dead_money_players"):
        assert key in properties
    assert item["additionalProperties"] is True
