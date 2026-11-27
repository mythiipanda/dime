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


def _seed_trade_guard_warehouse(con):
    con.execute('CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY_2026_27 BIGINT)')
    con.executemany('INSERT INTO silver_salaries VALUES (?, ?, ?)', [
        ('A Example', 'BKN', 10_000_000),
        ('B Example', 'BOS', 10_000_000),
    ])
    con.execute('CREATE TABLE silver_player_season (PLAYER VARCHAR, TEAM VARCHAR, _season VARCHAR)')
    con.executemany('INSERT INTO silver_player_season VALUES (?, ?, ?)', [
        ('A Example', 'BKN', '2026-27'),
        ('B Example', 'BOS', '2026-27'),
    ])


def _seed_alias_salary_row(con):
    con.execute('CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY_2026_27 BIGINT)')
    con.execute("INSERT INTO silver_salaries VALUES ('Alias Example', 'BRK', 10000000)")


def _seed_alias_production_warehouse(con):
    con.execute('CREATE TABLE silver_leaders_pts (PLAYER VARCHAR, TEAM VARCHAR, GP INTEGER, MIN DOUBLE, PTS DOUBLE, REB DOUBLE, AST DOUBLE, STL DOUBLE, BLK DOUBLE, TOV DOUBLE, _season VARCHAR)')
    con.execute("INSERT INTO silver_leaders_pts VALUES ('Alias Example', 'BRK', 70, 2100.0, 20.0, 5.0, 4.0, 1.0, 0.5, 2.0, '2025-26')")
    _seed_alias_salary_row(con)


def _force_fallback_team_lookup(monkeypatch):
    import shared.tools.league as league_pkg

    monkeypatch.setattr(league_pkg, 'last_completed_season', lambda: None)
    monkeypatch.setattr(league_pkg, 'season_static', lambda season: False)


def _force_salary_team_lookup(monkeypatch):
    import shared.tools.league as league_pkg

    monkeypatch.setattr(league_pkg, 'last_completed_season', lambda: '2025-26')
    monkeypatch.setattr(league_pkg, 'season_static', lambda season: True)


def test_trade_guard_accepts_alias_and_canonical_inputs_identically(monkeypatch):
    from shared.tools.league.trade_value import get_trade_check

    con = duckdb.connect(':memory:')
    try:
        _seed_trade_guard_warehouse(con)
        _install_in_memory_warehouse(monkeypatch, con)
        results = [get_trade_check.invoke({
            'team_a': team,
            'players_a': 'A Example',
            'team_b': 'BOS',
            'players_b': 'B Example',
            'season': '2026-27',
        }) for team in ('BRK', 'BKN')]
        assert [result['ok'] for result in results] == [True, True]
        assert results[0] == results[1]
    finally:
        con.close()


def test_payroll_cap_fallback_matches_stored_alias_for_either_spelling():
    con = duckdb.connect(':memory:')
    try:
        con.execute('CREATE TABLE silver_cap_players (player VARCHAR, team VARCHAR, salary BIGINT)')
        con.execute("INSERT INTO silver_cap_players VALUES ('Fallback Example', 'BRK', 10000000)")
        canonical = _payroll('BKN', con)
        raw = _payroll('BRK', con)
        assert canonical == raw
        assert canonical[0] == 10_000_000
        assert [row['player'] for row in canonical[1]] == ['Fallback Example']
    finally:
        con.close()


def test_stale_trade_resolution_canonicalizes_target_and_candidate(monkeypatch):
    from shared.tools.league.cba_cap import _resolve_stale_trade_player

    _force_fallback_team_lookup(monkeypatch)
    con = duckdb.connect(':memory:')
    try:
        _seed_alias_salary_row(con)
        canonical = _resolve_stale_trade_player('Alias Example', 'BKN', con)
        raw = _resolve_stale_trade_player('Alias Example', 'BRK', con)
        assert canonical == ('Alias Example', 10_000_000)
        assert raw == canonical
    finally:
        con.close()


def test_locate_player_team_returns_canonical_alias(monkeypatch):
    from shared.tools.league.cba_cap import _locate_player_team

    _force_salary_team_lookup(monkeypatch)
    con = duckdb.connect(':memory:')
    try:
        _seed_alias_salary_row(con)
        assert _locate_player_team('Alias Example', con) == ('Alias Example', 'BKN', 10_000_000)
    finally:
        con.close()


def test_auto_correct_side_treats_alias_old_team_as_same_team(monkeypatch):
    from shared.tools.league.cba_cap import _auto_correct_side

    _force_fallback_team_lookup(monkeypatch)
    con = duckdb.connect(':memory:')
    try:
        _seed_alias_salary_row(con)
        assert _auto_correct_side(['Alias Example'], 'BRK', 'Alias Example', con) is None
    finally:
        con.close()


def test_norm_trade_teams_canonicalizes_alias_inputs():
    from shared.tools.league.cba_cap import _norm_trade_teams

    assert _norm_trade_teams('BRK', 'Brooklyn Nets') is None
    assert _norm_trade_teams('BRK', 'BOS') == ('BKN', 'BOS')
    assert _norm_trade_teams('NJN', 'BOS') == ('NJN', 'BOS')


def test_cap_scenario_recognizes_alias_located_player_as_already_on_team(monkeypatch):
    from shared.tools.league.cap_scenario import get_cap_scenario

    _force_salary_team_lookup(monkeypatch)
    con = duckdb.connect(':memory:')
    try:
        _seed_alias_salary_row(con)
        _install_in_memory_warehouse(monkeypatch, con)
        results = [get_cap_scenario.invoke({
            'team': team,
            'in_players': 'Alias Example',
            'season': '2026-27',
        }) for team in ('BRK', 'BKN')]
        assert [result['ok'] for result in results] == [False, False]
        assert all('already on BKN' in result['error'] for result in results)
        assert results[0] == results[1]
    finally:
        con.close()


def test_value_contracts_does_not_mark_alias_production_as_moved(monkeypatch):
    from shared.tools.league.value_contracts import get_value_contracts

    con = duckdb.connect(':memory:')
    try:
        _seed_alias_production_warehouse(con)
        _install_in_memory_warehouse(monkeypatch, con)
        canonical = get_value_contracts.invoke({'team': 'BKN', 'season': '2025-26'})
        raw = get_value_contracts.invoke({'team': 'BRK', 'season': '2025-26'})
        assert canonical['ok'] is True
        assert raw == canonical
        row = next(r for r in canonical['rows'] if r['player'] == 'Alias Example')
        assert 'production_team' not in row
    finally:
        con.close()


def test_trade_targets_does_not_mark_alias_production_as_moved(monkeypatch):
    from shared.tools.league.trade_targets import get_trade_targets

    con = duckdb.connect(':memory:')
    try:
        _seed_alias_production_warehouse(con)
        _install_in_memory_warehouse(monkeypatch, con)
        result = get_trade_targets.invoke({'season': '2025-26'})
        assert result['ok'] is True
        row = next(r for r in result['rows'] if r['player'] == 'Alias Example')
        assert row['team'] == 'BKN'
        assert 'production_team' not in row
    finally:
        con.close()


def test_product_trade_assets_canonicalizes_pick_holders(monkeypatch):
    from analyst.direct_data import product_trade_assets

    con = duckdb.connect(':memory:')
    try:
        _seed_partner_salaries(con)
        con.execute('CREATE TABLE silver_future_picks (DRAFT_YEAR INTEGER, ROUND INTEGER, ORIG_TEAM VARCHAR, PROTECTION VARCHAR, CONDITIONAL BOOLEAN, SUMMARY VARCHAR, HELD_BY VARCHAR)')
        con.execute("INSERT INTO silver_future_picks VALUES (2028, 1, 'BRK', NULL, false, 'incoming pick', 'BRK')")
        _install_in_memory_warehouse(monkeypatch, con)
        canonical = product_trade_assets.invoke({'team': 'BKN', 'season': '2026-27'})
        raw = product_trade_assets.invoke({'team': 'BRK', 'season': '2026-27'})
        assert canonical == raw
        assert canonical['ok'] is True
        assert len(canonical['picks']) == 1
        assert canonical['picks'][0]['summary'] == 'incoming pick'
    finally:
        con.close()
