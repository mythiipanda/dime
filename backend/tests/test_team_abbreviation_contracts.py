import duckdb
import polars as pl
import pytest

from shared import store
from shared.contracts import (
    canonical_team_abbr,
    match_record,
    resolve_player_ids,
    salary_records,
    warehouse_player_ids,
)
from shared.tools.league.cba_cap import _payroll
from shared.tools.league.trade_value import get_trade_partners


class _NoCloseConnection:
    def __init__(self, real):
        self.real = real

    def __getattr__(self, name):
        return getattr(self.real, name)

    def close(self):
        pass


def _install_in_memory_warehouse(monkeypatch, con):
    proxy = _NoCloseConnection(con)

    def connect(*args, **kwargs):
        return proxy

    monkeypatch.setattr(store, 'connect', connect)


def _seed_partner_salaries(con):
    con.execute('CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY_2026_27 BIGINT)')
    rows = [
        ('Star Example', 'BOS', 10_000_000),
        ('Partner Example', 'BRK', 10_000_000),
        ('Partner Depth', 'BRK', 10_000_000),
    ]
    con.executemany('INSERT INTO silver_salaries VALUES (?, ?, ?)', rows)


@pytest.mark.parametrize('raw,expected', [
    ('WSH', 'WAS'),
    ('BRK', 'BKN'),
    ('CHO', 'CHA'),
    ('PHO', 'PHX'),
    ('WAS', 'WAS'),
    ('NJN', 'NJN'),
    ('CHH', 'CHH'),
    ('NOH', 'NOH'),
])
def test_canonical_team_abbr_pins_modern_aliases_and_historical_codes(raw, expected):
    assert canonical_team_abbr(raw) == expected


def test_canonical_team_abbr_normalizes_case_and_whitespace():
    assert canonical_team_abbr(' wsh ') == 'WAS'
    assert canonical_team_abbr('brk') == 'BKN'
    assert canonical_team_abbr('sea') == 'SEA'
    assert canonical_team_abbr(None) == ''


@pytest.mark.parametrize('stored,incoming', [
    ('WSH', 'WAS'),
    ('WAS', 'WSH'),
    ('brk', 'BKN'),
    ('CHO', 'cha'),
    ('pho', 'PHX'),
])
def test_match_record_canonicalizes_both_sides_for_name_disambiguation(stored, incoming):
    rows = [
        {'PLAYER_NAME': 'Shared Example', 'TEAM': stored},
        {'PLAYER_NAME': 'Shared Example', 'TEAM': 'BOS'},
    ]
    assert match_record(rows, 'Shared Example', team=incoming) is rows[0]


def test_match_record_canonicalizes_both_sides_for_id_disambiguation():
    rows = [
        {'PLAYER_NAME': 'Shared Example', 'PLAYER_ID': 7, 'TEAM': 'WSH'},
        {'PLAYER_NAME': 'Shared Example', 'PLAYER_ID': 7, 'TEAM': 'BOS'},
    ]
    assert match_record(rows, 'Shared Example', 7, 'WAS') is rows[0]
    flipped = [dict(row, TEAM='WAS' if row['TEAM'] == 'WSH' else row['TEAM']) for row in rows]
    assert match_record(flipped, 'Shared Example', 7, 'wsh') is flipped[0]


def test_salary_records_canonicalizes_rows_and_fallback_team_match():
    con = duckdb.connect(':memory:')
    try:
        con.execute('CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY BIGINT)')
        con.execute("INSERT INTO silver_salaries VALUES ('Shared Example', 'WSH', NULL), ('Shared Example', 'BOS', 200), ('Solo Example', 'PHO', 300)")
        con.execute('CREATE TABLE silver_cap_players (player VARCHAR, team VARCHAR, salary BIGINT)')
        con.execute("INSERT INTO silver_cap_players VALUES ('Shared Example', 'WAS', 125)")
        records = salary_records(con, include_fallback=True)
        assert len(records) == 3
        by_team = {row['TEAM']: row for row in records}
        assert set(by_team) == {'WAS', 'BOS', 'PHX'}
        assert by_team['WAS']['salary'] == 125
        assert by_team['BOS']['salary'] == 200
        assert by_team['PHX']['salary'] == 300
    finally:
        con.close()


def test_identity_rows_canonicalize_and_resolve_team_aliases():
    con = duckdb.connect(':memory:')
    try:
        con.execute('CREATE TABLE silver_leaders_pts (PLAYER_ID BIGINT, PLAYER VARCHAR, TEAM VARCHAR, _season VARCHAR)')
        con.execute("INSERT INTO silver_leaders_pts VALUES (1, 'Shared Example', 'WSH', '2025-26'), (2, 'Shared Example', 'BOS', '2025-26')")
        identity_rows = warehouse_player_ids(con)
        assert {row['TEAM'] for row in identity_rows} == {'WAS', 'BOS'}
        frame = pl.DataFrame({'PLAYER_NAME': ['Shared Example'], 'TEAM': ['wsh']})
        assert resolve_player_ids(frame, con)['PLAYER_ID'].to_list() == [1]
    finally:
        con.close()


def test_payroll_canonicalizes_season_lookup_and_requested_team():
    con = duckdb.connect(':memory:')
    try:
        con.execute('CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY_2026_27 BIGINT)')
        con.execute("INSERT INTO silver_salaries VALUES ('Payroll Example', 'BRK', 10000000)")
        con.execute('CREATE TABLE silver_player_season (PLAYER VARCHAR, TEAM VARCHAR, _season VARCHAR)')
        con.execute("INSERT INTO silver_player_season VALUES ('Payroll Example', 'BRK', '2026-27')")
        canonical = _payroll('BKN', con, '2026-27')
        raw = _payroll('BRK', con, '2026-27')
        assert canonical == raw
        assert canonical[0] == 10_000_000
        assert [row['team'] for row in canonical[1]] == ['BKN']
    finally:
        con.close()


def test_product_trade_assets_canonicalizes_requested_team(monkeypatch):
    from analyst.direct_data import product_trade_assets

    con = duckdb.connect(':memory:')
    try:
        _seed_partner_salaries(con)
        _install_in_memory_warehouse(monkeypatch, con)
        canonical = product_trade_assets.invoke({'team': 'BKN', 'season': '2026-27'})
        raw = product_trade_assets.invoke({'team': 'BRK', 'season': '2026-27'})
        assert canonical == raw
        assert canonical['ok'] is True
        assert canonical['team'] == 'BKN'
        assert [row['name'] for row in canonical['players']] == ['Partner Example', 'Partner Depth']
    finally:
        con.close()


def test_trade_partners_canonicalizes_restrict_entries(monkeypatch):
    con = duckdb.connect(':memory:')
    try:
        _seed_partner_salaries(con)
        _install_in_memory_warehouse(monkeypatch, con)
        canonical = get_trade_partners.invoke({
            'player': 'Star Example',
            'season': '2026-27',
            'teams': 'BKN',
            'max_packages': 3,
        })
        raw = get_trade_partners.invoke({
            'player': 'Star Example',
            'season': '2026-27',
            'teams': 'BRK',
            'max_packages': 3,
        })
        assert canonical['ok'] is True
        assert raw['ok'] is True
        assert canonical['rows'] == raw['rows']
        assert canonical['rows']
        assert {row['team'] for row in canonical['rows']} == {'BKN'}
    finally:
        con.close()
