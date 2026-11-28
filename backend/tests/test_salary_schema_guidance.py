import re
from pathlib import Path

import pytest


def test_allowed_guidance_does_not_deny_bare_salary():
    paths = [
        Path("backend/shared/tools/league/sql_schema.py"),
        Path("backend/shared/tools/league/cba_cap.py"),
        Path("backend/analyst/skills/warehouse-reconciliation/SKILL.md"),
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        assert "no bare salary" not in text
        assert "there is no bare salary" not in text


def test_current_payroll_examples_never_pair_prior_year_column_with_current_rows():
    from shared.tools.league.sql_schema import _TEXT_TO_SQL_EXAMPLES

    blocks = re.findall(r"(Q: .*?)(?=\nQ: |\Z)", _TEXT_TO_SQL_EXAMPLES, flags=re.S)
    payroll_blocks = [block for block in blocks if "payroll" in block.lower()]
    assert payroll_blocks
    for block in payroll_blocks:
        if re.search(r"\b(?:\w+\.)?_season\s*=\s*'2026-27'", block):
            assert "SALARY_2025_26" not in block
            assert re.search(r"SUM\((?:\w+\.)?SALARY\)", block)


def test_salary_column_semantics_distinguish_row_season_and_contract_year():
    from shared.tools.league.sql_schema import _column_semantics

    unit, note = _column_semantics("silver_salaries", "SALARY")
    assert unit == "usd_dollars"
    assert "row's _season" in note
    assert "payroll" in note

    year_unit, year_note = _column_semantics("silver_salaries", "SALARY_2025_26")
    assert year_unit == "usd_dollars"
    assert "exactly 2025-26" in year_note
    assert "never as a substitute" in year_note


def test_requested_year_guidance_requires_unavailable_year_handling():
    from shared.tools.league.cba_cap import get_cap_table
    from shared.tools.league.sql_schema import _SALARY_GUIDANCE

    combined = _SALARY_GUIDANCE + get_cap_table.description
    assert "exact contract year" in combined
    assert "unavailable" in combined
    assert "substituting another year" in combined


def test_normalized_name_sql_matches_canonical_python_on_synthetic_variants():
    import duckdb

    from shared.contracts import normalize_name
    from shared.tools.league.sql_schema import _normalized_name_sql

    pairs = [
        ("Aurelio Testin", "AURELIO TESTÍN"),
        ("P.J. Example", "pj example"),
        ("Casey Da Roma", "CASEY da ROMA"),
        ("Sam Suffix Jr.", "sam suffix"),
        ("Multi Suffix Jr Sr.", "MULTI suffix"),
    ]
    con = duckdb.connect(":memory:")
    try:
        con.execute("CREATE TABLE left_names (name VARCHAR)")
        con.execute("CREATE TABLE right_names (name VARCHAR)")
        con.executemany("INSERT INTO left_names VALUES (?)", [(left,) for left, _ in pairs])
        con.executemany("INSERT INTO right_names VALUES (?)", [(right,) for _, right in pairs])
        left_key = _normalized_name_sql("l.name")
        right_key = _normalized_name_sql("r.name")
        rows = con.execute(
            "SELECT l.name, r.name, "
            f"{left_key}, {right_key} "
            "FROM left_names l JOIN right_names r "
            f"ON {left_key} = {right_key}"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == len(pairs)
    for left, right, left_key, right_key in rows:
        assert left_key == right_key
        assert left_key == normalize_name(left)
        assert right_key == normalize_name(right)


def test_reconciliation_skill_documents_honest_manual_normalized_join_pattern():
    text = Path("backend/analyst/skills/warehouse-reconciliation/SKILL.md").read_text(encoding="utf-8")
    assert "does not apply this as a tool-enforced rewrite" in text
    assert "regexp_replace" in text
    assert "strip_accents" in text
    assert "'[^a-z0-9\\s]'" in text
    assert "'(?:\\s+(?:jr|sr|ii|iii|iv|v))+$'" in text
    assert "shared.contracts.normalize_name" in text
    assert "Aurelio Testín" in text
    assert "P.J. Example" in text


def test_dollar_column_semantics_cover_cap_tables():
    from shared.tools.league.sql_schema import _column_semantics

    cases = [
        ("silver_cap_room", "COMMITTED_SALARY"),
        ("silver_cap_room", "PROJECTED_APRON2"),
        ("silver_cap_room", "PROJECTED_ROOM"),
        ("silver_cap_room", "FA_HOLDS_EST"),
        ("silver_cap_room", "NTMLE_EST"),
        ("silver_cap_room", "BAE_EST"),
        ("silver_cap_room", "TMLE_EST"),
        ("silver_cap_room", "ROSTER_CHARGE_MINIMUM"),
        ("silver_cap_players", "salary"),
        ("silver_contracts", "SALARY"),
        ("silver_hist_salaries", "SALARY"),
        ("silver_salaries", "GUARANTEED"),
        ("silver_free_agents", "PRIOR_SALARY"),
        ("silver_free_agents", "CAP_HOLD_EST"),
        ("silver_cap_history", "salary_cap"),
        ("silver_cap_history", "apron_1"),
        ("silver_cap_history", "apron_2"),
    ]
    for table, column in cases:
        unit, note = _column_semantics(table, column)
        assert unit == "usd_dollars", f"{table}.{column} unit={unit!r}"
        assert note, f"{table}.{column} missing note"
    _, roster_note = _column_semantics("silver_cap_room", "ROSTER_CHARGE_MINIMUM")
    assert roster_note == (
        "minimum salary used for incomplete-roster charges in US dollars")


def _numeric_census_type(type_name: object) -> bool:
    upper = str(type_name or "").upper()
    return any(token in upper for token in (
        "INT", "DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC"))


def _money_valued_census_column(name: object, type_name: object) -> bool:
    upper = str(name or "").upper()
    if upper.startswith("_") or not _numeric_census_type(type_name):
        return False
    if upper.endswith("_PCT") or upper.endswith("_COUNT"):
        return False
    markers = (
        "SALARY", "PAYROLL", "CAP", "TAX", "APRON", "ROOM", "HOLD",
        "CHARGE", "MLE", "BAE", "GUARANTEE", "MONEY", "MINIMUM",
        "EXCEPTION", "AMOUNT", "FLOOR", "BONUS", "INCENTIVE",
    )
    return any(marker in upper for marker in markers)


def _money_census_table(name: object) -> bool:
    table = str(name or "").lower()
    return table.startswith("silver_cap_") or any(
        marker in table for marker in (
            "salary", "salaries", "contract", "free_agent"))


def _present_money_census_schema() -> tuple[list[str], dict[str, dict[str, str]]]:
    from shared import store

    con = store.connect(read_only=True)
    try:
        present = {str(row[0]) for row in con.execute("SHOW TABLES").fetchall()}
        tables = sorted(table for table in present if _money_census_table(table))
        schema = {}
        for table in tables:
            schema[table] = {
                str(row[1]): str(row[2])
                for row in con.execute(f"PRAGMA table_info({table})").fetchall()
            }
        return tables, schema
    finally:
        con.close()


def test_cap_table_money_census_is_structurally_complete():
    from shared.tools.league.sql_schema import _column_semantics

    census_tables, schema = _present_money_census_schema()
    assert census_tables, "no cap, salary, contract or free-agent tables present"
    candidates = [
        (table, column)
        for table in census_tables
        for column, type_name in schema[table].items()
        if _money_valued_census_column(column, type_name)
    ]
    assert candidates, "no numeric money-valued census columns examined"
    omissions = []
    for table, column in candidates:
        unit, note = _column_semantics(table, column)
        if unit != "usd_dollars" or not note:
            omissions.append(f"{table}.{column} unit={unit!r}")
    assert not omissions, omissions


def test_present_cap_room_money_columns_keep_declared_units():
    from shared.tools.league.sql_schema import _column_semantics

    census_tables, schema = _present_money_census_schema()
    if "silver_cap_room" not in census_tables:
        pytest.skip("silver_cap_room not present in warehouse")
    actual = {
        str(column).upper(): column
        for column in schema["silver_cap_room"]
    }
    known_money_columns = (
        "COMMITTED_SALARY", "PENDING_OPTION_SALARY", "FA_HOLDS_EST",
        "INCOMPLETE_ROSTER_CHARGES", "ROSTER_CHARGE_MINIMUM",
        "PROJECTED_ROOM", "MAX_ROOM", "PROJECTED_CAP", "PROJECTED_TAX",
        "PROJECTED_APRON1", "PROJECTED_APRON2", "NTMLE_EST", "BAE_EST",
        "ROOM_EST", "TMLE_EST",
    )
    present_known = [
        upper for upper in known_money_columns if upper in actual]
    assert present_known, "silver_cap_room has no known money columns"
    omissions = []
    for upper in present_known:
        column = actual[upper]
        unit, note = _column_semantics("silver_cap_room", column)
        if unit != "usd_dollars" or not note:
            omissions.append(f"silver_cap_room.{column} unit={unit!r}")
    assert not omissions, omissions


def test_sql_exec_result_carries_declared_units_on_direct_projection():
    import asyncio

    from shared.tools.league.sql_schema import _clear_warehouse_schema_cache
    from shared.tools.sql_exec import sql_exec

    _clear_warehouse_schema_cache()

    async def run():
        return await sql_exec.ainvoke({
            "sql": "SELECT TEAM, COMMITTED_SALARY, PROJECTED_APRON2 FROM silver_cap_room WHERE TEAM = 'LAL'"
        })

    result = asyncio.run(run())
    assert result.get("ok"), result.get("error")
    declared = result.get("declared_column_semantics") or {}
    assert declared.get("COMMITTED_SALARY", {}).get("unit") == "usd_dollars"
    assert declared.get("PROJECTED_APRON2", {}).get("unit") == "usd_dollars"
