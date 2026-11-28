import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb

from shared.contracts import salary_records


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
