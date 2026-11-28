from shared.tools.league._helpers import declare_money, declare_units


def test_declare_units_writes_host_contract_shape():
    result = {"rows": []}
    out = declare_units(result, {"payroll": "usd_dollars"})
    assert out is result
    assert out["declared_column_semantics"]["payroll"]["unit"] == "usd_dollars"


def test_declare_units_merges_without_clobbering_existing_entries():
    result = {"declared_column_semantics": {"season": {"unit": "season_label", "note": "kept"}}}
    declare_units(result, {"payroll": "usd_dollars"})
    assert result["declared_column_semantics"]["season"]["note"] == "kept"
    assert result["declared_column_semantics"]["payroll"]["unit"] == "usd_dollars"


def test_declare_money_marks_each_field_usd_dollars():
    result = {}
    declare_money(result, ["payroll", "salary"])
    declared = result["declared_column_semantics"]
    assert declared["payroll"]["unit"] == "usd_dollars"
    assert declared["salary"]["unit"] == "usd_dollars"


def test_declaration_is_absent_when_nothing_declared():
    assert "declared_column_semantics" not in declare_units({}, {})


def _memory_con():
    import duckdb
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE silver_salaries ("
        "PLAYER_NAME VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, GUARANTEED BIGINT, "
        "SALARY_2026_27 BIGINT, SALARY_2027_28 BIGINT, SALARY_2028_29 BIGINT, "
        "SALARY_2029_30 BIGINT, "
        "OPTION_2026_27 VARCHAR, OPTION_2027_28 VARCHAR, OPTION_2028_29 VARCHAR, OPTION_2029_30 VARCHAR)")
    con.execute(
        "INSERT INTO silver_salaries VALUES "
        "('Alpha', 'TST', 1, 60000000, 20000000, 20000000, 20000000, NULL, NULL, NULL, NULL, NULL)")
    return con


def test_projection_declares_money_units_on_scenario_outputs():
    from shared.tools.league.cap_projection import project_cap_scenario
    con = _memory_con()
    try:
        out = project_cap_scenario(con, {"team": "TST", "season": "2026-27", "moves": []})
    finally:
        con.close()
    assert out["ok"] is True
    declared = out.get("declared_column_semantics") or {}
    for field in ("pay_before", "pay_after", "roster_payroll", "dead_money",
                  "cap_room", "salary", "delta", "cap_holds", "amount"):
        assert declared.get(field, {}).get("unit") == "usd_dollars", f"{field} undeclared"


def test_cap_ledger_declares_money_units():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "backend/shared/tools/league/cba_cap.py").read_text()
    assert 'declare_money(result, ["payroll", "room_under_apron2", "salary", "remaining_guaranteed"])' in src
    assert 'declare_money(res, ["payroll", "cap_room", "room_under_apron2"])' in src


def test_cap_scenario_declares_money_units():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "backend/shared/tools/league/cap_scenario.py").read_text()
    assert "declare_money(res, [" in src
    for field in ('"payroll_before"', '"payroll_after"', '"delta"'):
        assert field in src


def test_projection_source_declares_money_vocabulary():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "backend/shared/tools/league/cap_projection.py").read_text()
    for field in ('"pay_before"', '"pay_after"', '"cap_room"', '"salary"', '"delta"', '"cap_holds"', '"amount"'):
        assert field in src


def test_money_sweep_modules_declare_units():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "backend/shared/tools/league"
    expectations = {
        "free_agents.py": ['"cap_room"', '"salary"', '"amount"'],
        "salary_history.py": ['"salary"', '"salary_cap"', '"luxury_tax"'],
        "trade_value.py": ['"salary"', '"incoming"', '"outgoing"'],
        "trade_targets.py": ['"salary"'],
        "value_contracts.py": ['"salary"'],
        "draft_contracts.py": ['"SALARY"'],
        "fa_plan.py": ['"amount"', '"committed_salary"', '"max_room"'],
        "trade_legality.py": ['"amount"', '"salary"', '"allowed_incoming"'],
    }
    for name, fields in expectations.items():
        src = (root / name).read_text()
        assert "declare_money" in src or "declare_units" in src, f"{name} not wired"
        for field in fields:
            assert field in src, f"{name} missing {field}"


def test_trade_value_millions_fields_use_the_millions_token_not_raw_dollars():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "backend/shared/tools/league/trade_value.py").read_text()
    assert '"side_total_m": "usd_millions"' in src
    assert '"delta_m": "usd_millions"' in src
    assert '"side_total_m": "usd_dollars"' not in src
