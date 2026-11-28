import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import pytest

from shared.contracts import salary_records
from shared.tools.league.cap_projection import project_cap_scenario
from shared.tools.league.cap_sheet import cap_sheet_rows
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


def test_row_kind_predicates_trim_and_normalize_hyphens_like_python():
    for row_value in (' dead-money ', 'DEAD-MONEY'):
        con = _degraded_con('ROW_KIND', row_value)
        try:
            rows = salary_records(con, salary_season='2026-27')
            total, players, dead = _payroll('TST', con)
        finally:
            con.close()
        assert [r['PLAYER_NAME'] for r in rows] == ['Roster Player']
        assert total == 12000000
        assert [r['player'] for r in players] == ['Roster Player']
        assert dead == [{'player': 'Dead Player', 'salary': 2000000, 'team': 'TST'}]


_CONTROL_WHITESPACE_CHARS = tuple(
    chr(codepoint) for codepoint in (0x0b, 0x85, 0x1c, 0x1d, 0x1e, 0x1f))

_CONTROL_KIND_EXPECTATIONS = {
    'dead_money': {
        'classification': ('dead', 5000000, False),
        'total': 15000000,
        'roster_payroll': 10000000,
        'dead_money': 5000000,
    },
    'roster': {
        'classification': ('roster', None, False),
        'total': 15000000,
        'roster_payroll': 15000000,
        'dead_money': 0,
    },
    'two_way': {
        'classification': ('excluded', None, False),
        'total': 10000000,
        'roster_payroll': 10000000,
        'dead_money': 0,
    },
    'unknown': {
        'classification': ('unknown_obligation', None, True),
        'total': 10000000,
        'roster_payroll': 10000000,
        'dead_money': 0,
    },
}


def _cross_surface_con(kind_value):
    con = duckdb.connect()
    con.execute(
        'CREATE TABLE silver_salaries ('
        'PLAYER_NAME VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, SALARY BIGINT, '
        'SALARY_2026_27 BIGINT, GUARANTEED BIGINT, SALARY_2027_28 BIGINT, '
        '_season VARCHAR, ROW_KIND VARCHAR)')
    con.executemany(
        'INSERT INTO silver_salaries VALUES (?,?,?,?,?,?,?,?,?)',
        [
            ('Probe Player', 'TST', 1, 5000000, 5000000,
             5000000, None, '2026-27', kind_value),
            ('Standard Player', 'TST', 2, 10000000, 10000000,
             10000000, None, '2026-27', 'roster'),
        ])
    con.execute(
        'CREATE TABLE silver_transactions ('
        'txn_date VARCHAR, txn_type VARCHAR, player VARCHAR, player_id BIGINT, '
        'team VARCHAR, team_id BIGINT, detail VARCHAR, _season VARCHAR)')
    return con


def _probe_classification(player_names, dead_rows):
    in_roster = 'Probe Player' in player_names
    matches = [row for row in dead_rows if row.get('player') == 'Probe Player']
    if in_roster and matches:
        return ('both', None, False)
    if in_roster:
        return ('roster', None, False)
    if len(matches) > 1:
        return ('duplicate_dead', None, False)
    if matches:
        row = matches[0]
        if row.get('amount_unknown'):
            return ('unknown_obligation', row.get('salary'), True)
        return ('dead', row.get('salary'), False)
    return ('excluded', None, False)


@pytest.mark.parametrize('kind', tuple(_CONTROL_KIND_EXPECTATIONS))
@pytest.mark.parametrize('char', _CONTROL_WHITESPACE_CHARS)
def test_control_whitespace_row_kinds_classify_once_across_cap_surfaces(kind, char):
    con = _cross_surface_con(char + kind + char)
    try:
        total, roster, dead = _payroll('TST', con, '2026-27')
        sheet = cap_sheet_rows(con, 'TST', '2026-27')
        projection = project_cap_scenario(
            con, {'team': 'TST', 'season': '2026-27', 'moves': []})
    finally:
        con.close()
    base = next(row for row in projection['seasons'] if row['season'] == '2026-27')
    sheet_totals = sheet['totals']['2026-27']
    observed = {
        'payroll': _probe_classification([row['player'] for row in roster], dead),
        'cap_sheet': _probe_classification(
            [row['player'] for row in sheet['players']], sheet_totals['dead_money_detail']),
        'projection': _probe_classification(
            [row['player'] for row in base['players']], base['dead_money_detail']),
    }
    expected = _CONTROL_KIND_EXPECTATIONS[kind]
    assert observed == {surface: expected['classification'] for surface in observed}
    assert total == expected['total']
    assert sheet_totals['roster_payroll'] == expected['roster_payroll']
    assert sheet_totals['dead_money'] == expected['dead_money']
    assert sheet_totals['payroll'] == expected['total']
    assert base['roster_payroll'] == expected['roster_payroll']
    assert base['dead_money'] == expected['dead_money']
    assert base['pay_before'] == expected['total']
