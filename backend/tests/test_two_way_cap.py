import duckdb

from shared.tools.league.cba_cap import _payroll


def _salary_table(con):
    con.execute(
        "CREATE TABLE silver_salaries ("
        "PLAYER_NAME VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, SALARY BIGINT, "
        "SALARY_2026_27 BIGINT, GUARANTEED BIGINT, SALARY_2027_28 BIGINT, "
        "_season VARCHAR, ROW_KIND VARCHAR)")


def _transaction_table(con):
    con.execute(
        "CREATE TABLE silver_transactions ("
        "txn_date VARCHAR, txn_type VARCHAR, player VARCHAR, player_id BIGINT, "
        "team VARCHAR, team_id BIGINT, detail VARCHAR, _season VARCHAR)")


def _clayton_warehouse(con):
    _salary_table(con)
    con.executemany(
        "INSERT INTO silver_salaries VALUES (?,?,?,?,?,?,?,?,?)",
        [
            ("Walter Clayton Jr.", "MEM", 1642383, 4_190_520, 4_190_520,
             4_190_520, None, "2026-27", "roster"),
            ("Standard Mav", "DAL", 900001, 10_000_000, 10_000_000,
             10_000_000, None, "2026-27", "roster"),
            ("Standard Grizzly", "MEM", 900002, 20_000_000, 20_000_000,
             20_000_000, None, "2026-27", "roster"),
        ])
    con.execute(
        "CREATE TABLE silver_player_season (PLAYER VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, _season VARCHAR)")
    con.execute(
        "INSERT INTO silver_player_season VALUES "
        "('Walter Clayton Jr.', 'DAL', 1642383, '2026-27')")
    _transaction_table(con)
    con.executemany(
        "INSERT INTO silver_transactions VALUES (?,?,?,?,?,?,?,?)",
        [
            ("2026-10-19", "Waive", "walter-clayton-jr", 1642383,
             "grizzlies", 1610612763,
             "Memphis Grizzlies waived guard Walter Clayton Jr..", "2026-27"),
            ("2026-10-21", "Signing", "walter-clayton-jr", 1642383,
             "mavericks", 1610612742,
             "Dallas Mavericks signed guard Walter Clayton Jr. to a Two-Way Contract.",
             "2026-27"),
        ])


def test_clayton_two_way_is_not_dallas_salary_and_memphis_keeps_dead_money():
    con = duckdb.connect()
    try:
        _clayton_warehouse(con)
        dal_total, dal_roster, dal_dead = _payroll("DAL", con, "2026-27")
        assert dal_total == 10_000_000
        assert [row["player"] for row in dal_roster] == ["Standard Mav"]
        assert dal_dead == []

        mem_total, mem_roster, mem_dead = _payroll("MEM", con, "2026-27")
        assert mem_total == 24_190_520
        assert [row["player"] for row in mem_roster] == ["Standard Grizzly"]
        assert len(mem_roster) == 1
        assert len(mem_dead) == 1
        assert mem_dead[0]["player"] == "Walter Clayton Jr."
        assert mem_dead[0]["salary"] == 4_190_520
        assert mem_dead[0]["team"] == "MEM"
    finally:
        con.close()


def test_explicit_two_way_row_kind_is_excluded_from_payroll_and_roster_count():
    con = duckdb.connect()
    try:
        _salary_table(con)
        con.executemany(
            "INSERT INTO silver_salaries VALUES (?,?,?,?,?,?,?,?,?)",
            [
                ("Two Way Wing", "DAL", 800001, 678_882, 678_882,
                 91_000, None, "2026-27", "two_way"),
                ("Standard Mav", "DAL", 800002, 10_000_000, 10_000_000,
                 10_000_000, None, "2026-27", "roster"),
            ])
        _transaction_table(con)
        total, roster, dead = _payroll("DAL", con, "2026-27")
        assert total == 10_000_000
        assert [row["player"] for row in roster] == ["Standard Mav"]
        assert dead == []
    finally:
        con.close()


def test_conversion_to_nba_contract_restores_standard_salary():
    con = duckdb.connect()
    try:
        _salary_table(con)
        con.execute(
            "INSERT INTO silver_salaries VALUES "
            "('Converted Wing', 'DAL', 800003, 2_000_000, 2_000_000, "
            "2_000_000, NULL, '2026-27', 'roster')")
        _transaction_table(con)
        con.executemany(
            "INSERT INTO silver_transactions VALUES (?,?,?,?,?,?,?,?)",
            [
                ("2026-10-01", "Signing", "converted-wing", 800003,
                 "mavericks", 1610612742,
                 "Dallas Mavericks signed forward Converted Wing to a Two-Way Contract.",
                 "2026-27"),
                ("2026-11-01", "ContractConverted", "converted-wing", 800003,
                 "mavericks", 1610612742,
                 "Dallas Mavericks converted the contract of forward Converted Wing to an NBA Contract.",
                 "2026-27"),
            ])
        total, roster, dead = _payroll("DAL", con, "2026-27")
        assert total == 2_000_000
        assert [row["player"] for row in roster] == ["Converted Wing"]
        assert dead == []
    finally:
        con.close()


def test_contracts_two_way_flag_is_used_when_transaction_coverage_is_absent():
    con = duckdb.connect()
    try:
        _salary_table(con)
        con.executemany(
            "INSERT INTO silver_salaries VALUES (?,?,?,?,?,?,?,?,?)",
            [
                ("Flagged Two Way", "SAC", 810001, 559_782, 559_782,
                 50_000, None, "2026-27", "roster"),
                ("Standard King", "SAC", 810002, 8_000_000, 8_000_000,
                 8_000_000, None, "2026-27", "roster"),
            ])
        con.execute(
            "CREATE TABLE silver_contracts (PLAYER_NAME VARCHAR, PLAYER_ID BIGINT, TEAM VARCHAR, "
            "SALARY BIGINT, TWO_WAY BOOLEAN, TERMINATED BOOLEAN, _season VARCHAR)")
        con.execute(
            "INSERT INTO silver_contracts VALUES "
            "('Flagged Two Way', 810001, 'SAC', 559782, TRUE, FALSE, '2026-27')")
        total, roster, dead = _payroll("SAC", con, "2026-27")
        assert total == 8_000_000
        assert [row["player"] for row in roster] == ["Standard King"]
        assert dead == []
    finally:
        con.close()
