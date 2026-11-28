import duckdb

from shared.tools.league.cap_projection import project_cap_scenario
from shared.tools.league.cap_sheet import cap_sheet_rows
from shared.tools.league.cba_cap import _payroll, _season_player_team
from shared.tools.league.cba_two_way import two_way_state_for_record, two_way_states


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
            ("Walter Clayton", "MEM", 1642383, 4_190_520, 4_190_520,
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
        assert _season_player_team(
            con, "Walter Clayton", "2026-27", player_id=1642383) == "DAL"
        dal_total, dal_roster, dal_dead = _payroll("DAL", con, "2026-27")
        assert dal_total == 10_000_000
        assert [row["player"] for row in dal_roster] == ["Standard Mav"]
        assert dal_dead == []

        mem_total, mem_roster, mem_dead = _payroll("MEM", con, "2026-27")
        assert mem_total == 24_190_520
        assert [row["player"] for row in mem_roster] == ["Standard Grizzly"]
        assert len(mem_roster) == 1
        assert len(mem_dead) == 1
        assert mem_dead[0]["player"] == "Walter Clayton"
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


def _transaction_table_with_ordering(con):
    con.execute(
        "CREATE TABLE silver_transactions ("
        "txn_date VARCHAR, txn_type VARCHAR, player VARCHAR, player_id BIGINT, "
        "team VARCHAR, team_id BIGINT, detail VARCHAR, _season VARCHAR, "
        "group_sort VARCHAR, additional_sort DOUBLE)")


def _insert_ordered_transactions(con, rows):
    con.executemany(
        "INSERT INTO silver_transactions VALUES (?,?,?,?,?,?,?,?,?,?)", rows)


def _single_two_way_salary(con, name="Offseason Two Way", salary=678_882):
    _salary_table(con)
    con.executemany(
        "INSERT INTO silver_salaries VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (name, "DAL", 820001, salary, salary, 91_000,
             None, "2026-27", "roster"),
            ("Standard Mav", "DAL", 820002, 10_000_000, 10_000_000,
             10_000_000, None, "2026-27", "roster"),
        ])


def test_offseason_signing_for_upcoming_league_year_is_excluded():
    con = duckdb.connect()
    try:
        _single_two_way_salary(con)
        _transaction_table(con)
        con.execute(
            "INSERT INTO silver_transactions VALUES "
            "('2026-08-15', 'Signing', 'offseason-two-way', 820001, "
            "'mavericks', 1610612742, "
            "'Dallas Mavericks signed forward Offseason Two Way to a Two-Way Contract.', "
            "'2025-26')")
        total, roster, dead = _payroll("DAL", con, "2026-27")
        assert total == 10_000_000
        assert [row["player"] for row in roster] == ["Standard Mav"]
        assert dead == []
    finally:
        con.close()


def test_continuing_two_way_across_season_boundary_is_excluded():
    con = duckdb.connect()
    try:
        _single_two_way_salary(con, "Continuing Two Way")
        _transaction_table(con)
        con.execute(
            "INSERT INTO silver_transactions VALUES "
            "('2025-08-15', 'Signing', 'continuing-two-way', 820001, "
            "'mavericks', 1610612742, "
            "'Dallas Mavericks signed forward Continuing Two Way to a Two-Way Contract.', "
            "'2024-25')")
        total, roster, dead = _payroll("DAL", con, "2026-27")
        assert total == 10_000_000
        assert [row["player"] for row in roster] == ["Standard Mav"]
        assert dead == []
    finally:
        con.close()


def test_preseason_conversion_overrides_stale_contracts_two_way_flag():
    con = duckdb.connect()
    try:
        _single_two_way_salary(con, "Converted Before Season", 2_000_000)
        con.execute(
            "CREATE TABLE silver_contracts (PLAYER_NAME VARCHAR, PLAYER_ID BIGINT, TEAM VARCHAR, "
            "SALARY BIGINT, TWO_WAY BOOLEAN, TERMINATED BOOLEAN, _season VARCHAR)")
        con.execute(
            "INSERT INTO silver_contracts VALUES "
            "('Converted Before Season', 820001, 'DAL', 2000000, TRUE, FALSE, '2026-27')")
        _transaction_table(con)
        con.executemany(
            "INSERT INTO silver_transactions VALUES (?,?,?,?,?,?,?,?)",
            [
                ("2026-07-10", "Signing", "converted-before-season", 820001,
                 "mavericks", 1610612742,
                 "Dallas Mavericks signed forward Converted Before Season to a Two-Way Contract.",
                 "2025-26"),
                ("2026-09-20", "ContractConverted", "converted-before-season", 820001,
                 "mavericks", 1610612742,
                 "Dallas Mavericks converted the contract of forward Converted Before Season to an NBA Contract.",
                 "2025-26"),
            ])
        total, roster, dead = _payroll("DAL", con, "2026-27")
        assert total == 12_000_000
        assert {row["player"] for row in roster} == {"Converted Before Season", "Standard Mav"}
        assert dead == []
    finally:
        con.close()


def test_two_way_then_waived_is_on_no_standard_roster_and_dead_money_survives():
    con = duckdb.connect()
    try:
        _clayton_warehouse(con)
        con.execute(
            "INSERT INTO silver_transactions VALUES "
            "('2026-11-05', 'Waive', 'walter-clayton-jr', 1642383, "
            "'mavericks', 1610612742, "
            "'Dallas Mavericks waived guard Walter Clayton Jr..', '2026-27')")
        dal_total, dal_roster, dal_dead = _payroll("DAL", con, "2026-27")
        mem_total, mem_roster, mem_dead = _payroll("MEM", con, "2026-27")
        assert dal_total == 10_000_000
        assert [row["player"] for row in dal_roster] == ["Standard Mav"]
        assert dal_dead == []
        assert mem_total == 24_190_520
        assert [row["player"] for row in mem_roster] == ["Standard Grizzly"]
        assert len(mem_dead) == 1
        assert mem_dead[0]["player"] == "Walter Clayton"
        assert mem_dead[0]["salary"] == 4_190_520
        assert "Walter Clayton" not in {row["player"] for row in dal_roster + mem_roster}
    finally:
        con.close()


def test_two_way_then_converted_does_not_count_terminated_row_on_new_team():
    con = duckdb.connect()
    try:
        _clayton_warehouse(con)
        con.execute(
            "INSERT INTO silver_transactions VALUES "
            "('2026-11-05', 'ContractConverted', 'walter-clayton-jr', 1642383, "
            "'mavericks', 1610612742, "
            "'Dallas Mavericks converted the contract of guard Walter Clayton Jr. to an NBA Contract.', "
            "'2026-27')")
        dal_total, dal_roster, dal_dead = _payroll("DAL", con, "2026-27")
        mem_total, mem_roster, mem_dead = _payroll("MEM", con, "2026-27")
        assert dal_total == 10_000_000
        assert [row["player"] for row in dal_roster] == ["Standard Mav"]
        assert dal_dead == []
        assert mem_total == 24_190_520
        assert [row["player"] for row in mem_roster] == ["Standard Grizzly"]
        assert len(mem_dead) == 1
        assert mem_dead[0]["salary"] == 4_190_520
    finally:
        con.close()


def test_same_date_ordering_is_deterministic_without_ordering_columns():
    def build(rows):
        con = duckdb.connect()
        _salary_table(con)
        con.execute(
            "INSERT INTO silver_salaries VALUES "
            "('Duane Washington Jr', 'NYK', 1630613, 1000000, 1000000, "
            "1000000, NULL, '2026-27', 'roster')")
        _transaction_table(con)
        con.executemany("INSERT INTO silver_transactions VALUES (?,?,?,?,?,?,?,?)", rows)
        return con

    base_rows = [
        ("2026-10-17", "Signing", "duane-washington-jr", 1630613,
         "knicks", 1610612752,
         "New York Knicks signed guard Duane Washington Jr. to a Two-Way Contract.",
         "2026-27"),
        ("2026-10-17", "Waive", "duane-washington-jr", 1630613,
         "knicks", 1610612752,
         "New York Knicks waived guard Duane Washington Jr..", "2026-27"),
    ]
    outcomes = []
    for rows in (base_rows, list(reversed(base_rows))):
        con = build(rows)
        try:
            states = two_way_states(con, "2026-27", {"silver_transactions"})
            state = two_way_state_for_record(states, "Duane Washington Jr", 1630613)
            total, roster, _dead = _payroll("NYK", con, "2026-27")
            outcomes.append((state["active_team"], state["two_way_end"]["kind"], total,
                             tuple(row["player"] for row in roster)))
        finally:
            con.close()
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][0] == ""
    assert outcomes[0][1] == "waive"


def test_group_sort_breaks_same_date_waive_and_sign_ties():
    def build(rows):
        con = duckdb.connect()
        _clayton_warehouse(con)
        con.execute("DROP TABLE silver_transactions")
        _transaction_table_with_ordering(con)
        _insert_ordered_transactions(con, rows)
        return con

    rows = [
        ("2026-10-19", "Waive", "walter-clayton-jr", 1642383,
         "grizzlies", 1610612763,
         "Memphis Grizzlies waived guard Walter Clayton Jr..", "2026-27",
         "Waive 1150001", 0.0),
        ("2026-10-19", "Signing", "walter-clayton-jr", 1642383,
         "mavericks", 1610612742,
         "Dallas Mavericks signed guard Walter Clayton Jr. to a Two-Way Contract.",
         "2026-27", "Signing 1150002", 0.0),
    ]
    outcomes = []
    for ordered in (rows, list(reversed(rows))):
        con = build(ordered)
        try:
            mem_total, mem_roster, mem_dead = _payroll("MEM", con, "2026-27")
            outcomes.append((mem_total, len(mem_dead)))
        finally:
            con.close()
    assert outcomes == [(24_190_520, 1), (24_190_520, 1)]


def test_additional_sort_breaks_ties_when_group_sort_is_missing():
    def build(rows):
        con = duckdb.connect()
        _clayton_warehouse(con)
        con.execute("DROP TABLE silver_transactions")
        _transaction_table_with_ordering(con)
        _insert_ordered_transactions(con, rows)
        return con

    def rows(waive_sort, signing_sort):
        return [
            ("2026-10-19", "Waive", "walter-clayton-jr", 1642383,
             "grizzlies", 1610612763,
             "Memphis Grizzlies waived guard Walter Clayton Jr..", "2026-27",
             None, waive_sort),
            ("2026-10-19", "Signing", "walter-clayton-jr", 1642383,
             "mavericks", 1610612742,
             "Dallas Mavericks signed guard Walter Clayton Jr. to a Two-Way Contract.",
             "2026-27", None, signing_sort),
        ]

    outcomes = []
    for ordered in (rows(1.0, 2.0), list(reversed(rows(1.0, 2.0)))):
        con = build(ordered)
        try:
            mem_total, _mem_roster, mem_dead = _payroll("MEM", con, "2026-27")
            outcomes.append((mem_total, len(mem_dead)))
        finally:
            con.close()
    assert outcomes == [(24_190_520, 1), (24_190_520, 1)]

    con = build(rows(2.0, 1.0))
    try:
        mem_total, _mem_roster, mem_dead = _payroll("MEM", con, "2026-27")
        assert (mem_total, len(mem_dead)) == (20_000_000, 0)
    finally:
        con.close()


def test_cap_sheet_projection_and_payroll_use_same_two_way_baseline():
    con = duckdb.connect()
    try:
        _clayton_warehouse(con)
        payroll_total, payroll_roster, payroll_dead = _payroll("MEM", con, "2026-27")
        sheet = cap_sheet_rows(con, "MEM", "2026-27")
        projection = project_cap_scenario(
            con, {"team": "MEM", "season": "2026-27", "moves": []})
        base = next(row for row in projection["seasons"] if row["season"] == "2026-27")
        assert payroll_total == 24_190_520
        assert [row["player"] for row in payroll_roster] == ["Standard Grizzly"]
        assert len(payroll_dead) == 1
        assert payroll_dead[0]["salary"] == 4_190_520
        totals = sheet["totals"]["2026-27"]
        assert totals["committed"] == 20_000_000
        assert totals["dead_money"] == 4_190_520
        assert totals["payroll"] == payroll_total
        assert [row["player"] for row in sheet["players"]] == ["Standard Grizzly"]
        assert base["roster_payroll"] == totals["committed"]
        assert base["dead_money"] == totals["dead_money"]
        assert base["pay_before"] == payroll_total
        assert [row["player"] for row in base["players"]] == ["Standard Grizzly"]
    finally:
        con.close()


def test_explicit_dead_money_row_is_not_roster_payroll_or_double_counted():
    con = duckdb.connect()
    try:
        _salary_table(con)
        con.executemany(
            "INSERT INTO silver_salaries VALUES (?,?,?,?,?,?,?,?,?)",
            [
                ("Dead Money Wing", "MEM", 840001, 4_000_000, 4_000_000,
                 4_000_000, None, "2026-27", "dead_money"),
                ("Standard Grizzly", "MEM", 840002, 20_000_000, 20_000_000,
                 20_000_000, None, "2026-27", "roster"),
            ])
        _transaction_table(con)
        total, roster, dead = _payroll("MEM", con, "2026-27")
        sheet = cap_sheet_rows(con, "MEM", "2026-27")
        projection = project_cap_scenario(
            con, {"team": "MEM", "season": "2026-27", "moves": []})
        base = next(row for row in projection["seasons"] if row["season"] == "2026-27")
        assert total == 24_000_000
        assert [row["player"] for row in roster] == ["Standard Grizzly"]
        assert len(dead) == 1
        assert dead[0]["salary"] == 4_000_000
        assert sheet["totals"]["2026-27"]["committed"] == 20_000_000
        assert sheet["totals"]["2026-27"]["dead_money"] == 4_000_000
        assert base["roster_payroll"] == 20_000_000
        assert base["dead_money"] == 4_000_000
    finally:
        con.close()


def test_dead_money_only_salary_row_still_owns_team_payroll():
    con = duckdb.connect()
    try:
        _salary_table(con)
        con.execute(
            "INSERT INTO silver_salaries VALUES "
            "('Dead Money Wing', 'MEM', 850001, 4000000, 4000000, "
            "4000000, NULL, '2026-27', 'dead_money')")
        con.execute("CREATE TABLE silver_cap_players (player VARCHAR, salary BIGINT, team VARCHAR)")
        con.execute("INSERT INTO silver_cap_players VALUES ('Fallback Wing', 7000000, 'MEM')")
        _transaction_table(con)
        total, roster, dead = _payroll("MEM", con, "2026-27")
        assert total == 4_000_000
        assert roster == []
        assert len(dead) == 1
        assert dead[0]["player"] == "Dead Money Wing"
    finally:
        con.close()


def test_team_absent_from_salary_rows_falls_back_to_cap_players():
    con = duckdb.connect()
    try:
        _salary_table(con)
        con.execute(
            "INSERT INTO silver_salaries VALUES "
            "('Other Player', 'BOS', 830001, 5000000, 5000000, "
            "5000000, NULL, '2026-27', 'roster')")
        con.execute("CREATE TABLE silver_cap_players (player VARCHAR, salary BIGINT, team VARCHAR)")
        con.execute("INSERT INTO silver_cap_players VALUES ('Fallback Wing', 7000000, 'DAL')")
        total, roster, dead = _payroll("DAL", con, "2026-27")
        assert total == 7_000_000
        assert [row["player"] for row in roster] == ["Fallback Wing"]
        assert dead == []
    finally:
        con.close()
