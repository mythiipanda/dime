import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb

from shared.contracts import salary_records
from shared.tools.league.cba_cap import _payroll


def _con(with_kind: bool):
    con = duckdb.connect()
    kind_col = ", ROW_KIND VARCHAR" if with_kind else ""
    con.execute(f"CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY_2026_27 INTEGER, _season VARCHAR{kind_col})")
    return con


def test_dead_money_rows_excluded_when_column_present():
    con = _con(with_kind=True)
    con.execute("INSERT INTO silver_salaries VALUES ('Klay Thompson', 'DAL', 7660317, '2026-27', 'dead_money')")
    con.execute("INSERT INTO silver_salaries VALUES ('Klay Thompson', 'MIA', 5600000, '2026-27', 'roster')")
    rows = [r for r in salary_records(con, salary_season='2026-27') if r['PLAYER_NAME'] == 'Klay Thompson']
    assert len(rows) == 1
    assert rows[0]['TEAM'] == 'MIA'
    assert rows[0]['salary'] == 5600000


def test_all_rows_read_when_column_absent():
    con = _con(with_kind=False)
    con.execute("INSERT INTO silver_salaries VALUES ('Klay Thompson', 'DAL', 7660317, '2026-27')")
    rows = [r for r in salary_records(con, salary_season='2026-27') if r['PLAYER_NAME'] == 'Klay Thompson']
    assert len(rows) == 1


def _degraded_con(column_name, row_value):
    con = duckdb.connect()
    con.execute(
        f"CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
        f"SALARY_2026_27 INTEGER, _season VARCHAR, {column_name} VARCHAR)")
    con.execute("INSERT INTO silver_salaries VALUES ('Roster Player', 'TST', 10000000, '2026-27', 'roster')")
    con.execute(
        "INSERT INTO silver_salaries VALUES ('Dead Player', 'TST', 2000000, '2026-27', ?)",
        [row_value])
    return con


def test_salary_records_normalize_row_kind_column_and_value_case():
    for column_name, row_value in (("row_kind", "dead_money"), ("ROW_KIND", "DEAD_MONEY")):
        con = _degraded_con(column_name, row_value)
        try:
            rows = salary_records(con, salary_season='2026-27')
        finally:
            con.close()
        assert [r['PLAYER_NAME'] for r in rows] == ['Roster Player']
        assert rows[0]['salary'] == 10000000


def test_payroll_normalizes_row_kind_column_and_value_case():
    for column_name, row_value in (("row_kind", "dead_money"), ("ROW_KIND", "DEAD_MONEY")):
        con = _degraded_con(column_name, row_value)
        try:
            total, players, dead = _payroll('TST', con)
        finally:
            con.close()
        assert total == 12000000
        assert [r['player'] for r in players] == ['Roster Player']
        assert dead == [{'player': 'Dead Player', 'salary': 2000000, 'team': 'TST'}]


def test_payroll_counts_dead_money_without_roster_rows():
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
        "SALARY_2026_27 INTEGER, _season VARCHAR, ROW_KIND VARCHAR)")
    con.execute(
        "INSERT INTO silver_salaries VALUES ('Dead Player', 'TST', 2000000, '2026-27', 'dead_money')")
    try:
        total, players, dead = _payroll('TST', con)
    finally:
        con.close()
    assert total == 2000000
    assert players == []
    assert dead == [{'player': 'Dead Player', 'salary': 2000000, 'team': 'TST'}]
