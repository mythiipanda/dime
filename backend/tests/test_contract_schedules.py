import importlib.util
from pathlib import Path

import duckdb
import polars as pl
import pytest

from shared import store
from shared.contracts import contract_details, resolve_player_ids, salary_records
from shared.sources import salaries
from shared.tools import league


HTML = '''<table id="contracts"><thead><tr>
<th data-stat="y1">2026-27</th><th data-stat="y2">2027-28</th>
<th data-stat="y3">2028-29</th><th data-stat="y4">2029-30</th>
<th data-stat="y5">2030-31</th><th data-stat="y6">2031-32</th>
</tr></thead><tbody><tr>
<th data-stat="player"><a href="/players/e/example01.html">André Example Jr.</a></th>
<td data-stat="y1" csk="100">$100</td>
<td class="right salary-pl" data-stat="y2" csk="110">$110</td>
<td data-stat="y3" class="salary-tm" csk="120">$120</td>
<td data-stat="y4" csk="130" class="salary-et">$130</td>
<td data-stat="y5" csk="140">$140</td><td data-stat="y6"></td>
<td data-stat="remain_gtd" csk="90">$90</td>
</tr><tr><th data-stat="player">Team Totals</th><td data-stat="y1" csk="999"></td></tr>
</tbody></table>'''


def test_parser_retains_seasons_options_slug_and_guaranteed():
    season, rows = salaries._parse_contracts(HTML, 'BRK')
    assert season == '2026-27'
    assert len(rows) == 1
    row = rows[0]
    assert row['PLAYER_NAME'] == 'Andre Example Jr.'
    assert row['TEAM'] == 'BKN'
    assert row['BREF_SLUG'] == 'example01'
    assert row['SALARY'] == row['SALARY_2026_27'] == 100
    assert row['SALARY_2030_31'] == 140
    assert row['SALARY_2031_32'] is None
    assert row['OPTION_2027_28'] == 'player'
    assert row['OPTION_2028_29'] == 'team'
    assert row['OPTION_2029_30'] == 'early-termination'
    assert row['GUARANTEED'] == 90


def test_parser_does_not_invent_guarantees():
    _, rows = salaries._parse_contracts(HTML.replace('csk="90"', ''), 'BOS')
    assert rows[0]['GUARANTEED'] is None


def test_parser_empty_and_malformed():
    assert salaries._parse_contracts(HTML.replace('/players/e/example01.html', '/teams/BOS.html'), 'BOS')[1] == []
    with pytest.raises(ValueError, match='table missing'):
        salaries._parse_contracts('<html></html>', 'BOS')
    with pytest.raises(ValueError, match='season headers'):
        salaries._parse_contracts(HTML.replace('2026-27', 'unknown'), 'BOS')


def test_fetch_fails_closed_instead_of_publishing_partial_teams(monkeypatch):
    monkeypatch.setattr(salaries.time, 'sleep', lambda _: None)
    monkeypatch.setenv('DIME_LIVE_ATTEMPTS', '1')
    def fetch(url):
        if url == salaries.URL:
            return '<th data-stat="y1">2026-27</th><a href="/contracts/BOS.html">BOS</a><a href="/contracts/NYK.html">NYK</a>'
        if 'BOS' in url:
            return HTML
        raise ValueError('team fetch failed')
    monkeypatch.setattr(salaries, '_get', fetch)
    result = salaries.get_contracts()
    assert not result.ok
    assert 'team fetch failed' in result.error


def test_identity_resolution_normalization_team_ambiguity_and_missing():
    con = duckdb.connect(':memory:')
    try:
        con.execute('CREATE TABLE silver_leaders_pts (PLAYER_ID BIGINT, PLAYER VARCHAR, TEAM VARCHAR, _season VARCHAR)')
        con.execute("INSERT INTO silver_leaders_pts VALUES (1, 'Andre Example', 'BOS', '2025-26'), (2, 'Shared Name', 'NYK', '2025-26'), (3, 'Shared Name Jr.', 'BOS', '2025-26'), (4, 'Ambiguous Name', 'BOS', '2025-26'), (5, 'Ambiguous Name II', 'BOS', '2025-26')")
        frame = pl.DataFrame({'PLAYER_NAME': ['André Ex-ample, Jr.', 'Shared Name', 'Ambiguous Name', 'Nobody Here'], 'TEAM': ['BOS'] * 4})
        resolved = resolve_player_ids(frame, con)
        assert resolved['PLAYER_ID'].to_list() == [1, 3, None, None]
    finally:
        con.close()
    con = duckdb.connect(':memory:')
    try:
        assert resolve_player_ids(frame, con)['PLAYER_ID'].null_count() == 4
    finally:
        con.close()


@pytest.fixture
def warehouse(tmp_path, monkeypatch):
    path = tmp_path / 'contracts.duckdb'
    monkeypatch.setattr(store, 'DB_PATH', path)
    monkeypatch.setattr(store, 'LOCK_PATH', tmp_path / '.write.lock')
    monkeypatch.setattr(league, 'last_completed_season', lambda: '2025-26')
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    yield path
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()


def _new_warehouse(path):
    con = duckdb.connect(str(path))
    con.execute('CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, SALARY BIGINT, BREF_SLUG VARCHAR, GUARANTEED BIGINT, SALARY_2026_27 BIGINT, SALARY_2027_28 BIGINT, OPTION_2026_27 VARCHAR, OPTION_2027_28 VARCHAR, _season VARCHAR)')
    con.execute("INSERT INTO silver_salaries VALUES ('Different Salary Name', 'BOS', 1, 100, 'example01', 90, 100, 110, NULL, 'player', '2026-27'), ('Fallback Example Jr.', 'NYK', NULL, 200, 'fallback01', 200, 200, NULL, NULL, NULL, '2026-27')")
    con.execute('CREATE TABLE silver_leaders_pts (PLAYER VARCHAR, TEAM VARCHAR, PLAYER_ID BIGINT, GP INTEGER, PTS INTEGER, REB INTEGER, AST INTEGER, STL INTEGER, BLK INTEGER, TOV INTEGER, FG3M INTEGER, FG3_PCT DOUBLE, _season VARCHAR)')
    con.execute("INSERT INTO silver_leaders_pts VALUES ('Different Stats Name', 'BOS', 1, 40, 800, 100, 100, 20, 10, 20, 10, .4, '2025-26'), ('Fallback Example', 'NYK', 2, 40, 1200, 100, 100, 20, 10, 20, 10, .4, '2025-26')")
    con.close()


def test_cap_legacy_snapshot_compat_and_explicitly_unavailable(warehouse):
    con = duckdb.connect(str(warehouse))
    con.execute('CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY_2025_26 BIGINT, _season VARCHAR)')
    con.execute("INSERT INTO silver_salaries VALUES ('Legacy Example', 'BOS', 100, '2026-27')")
    con.close()
    result = league.get_cap_ledger.invoke({'team': 'BOS'})
    assert result['ok']
    assert result['rows']['payroll'] == 100
    player = result['rows']['players'][0]
    assert player['years_remaining'] is None
    assert player['future_salaries'] is None
    assert player['option_years'] is None
    assert player['contract_schedule_available'] is False


def test_cap_new_schedule_and_wrapper(warehouse):
    _new_warehouse(warehouse)
    result = league.get_cap_ledger.invoke({'team': 'BOS'})
    assert result['ok']
    player = result['rows']['players'][0]
    assert player['player_id'] == 1
    assert player['years_remaining'] == 2
    assert player['future_salaries'] == {'2027-28': 110}
    assert player['option_years'] == {'2027-28': 'player'}
    from analyst.tools import cba
    wrapped = cba.register()['get_cap_ledger'].invoke({'team': 'BOS'})
    assert wrapped['rows'][0]['players'][0]['future_salaries'] == {'2027-28': 110}


def test_contract_value_id_join_and_name_fallback(warehouse):
    _new_warehouse(warehouse)
    result = league.get_contract_value.invoke({'season': '2025-26'})
    assert result['ok'], result
    rows = {r['PLAYER']: r for r in result['rows']}
    assert rows['Different Salary Name']['years_remaining'] == 2
    assert rows['Fallback Example Jr.']['SALARY'] == 200
    from analyst.tools import cba
    wrapped = cba.register()['get_contract_value'].invoke({'season': '2025-26'})
    assert wrapped['ok']
    assert wrapped['rows'][0]['years_remaining'] is not None


def test_contract_value_legacy_cap_name_fallback(warehouse):
    con = duckdb.connect(str(warehouse))
    con.execute('CREATE TABLE silver_cap_players (player VARCHAR, team VARCHAR, salary BIGINT)')
    con.execute("INSERT INTO silver_cap_players VALUES ('First Example', 'BOS', 100), ('Second Example', 'NYK', 200)")
    con.execute('CREATE TABLE silver_leaders_pts (PLAYER VARCHAR, TEAM VARCHAR, GP INTEGER, PTS INTEGER, REB INTEGER, AST INTEGER, STL INTEGER, BLK INTEGER, TOV INTEGER, _season VARCHAR)')
    con.execute("INSERT INTO silver_leaders_pts VALUES ('First Example', 'BOS', 40, 100, 0, 0, 0, 0, 0, '2025-26'), ('Second Example', 'NYK', 40, 200, 0, 0, 0, 0, 0, '2025-26')")
    con.close()
    result = league.get_contract_value.invoke({'season': '2025-26'})
    assert result['ok'], result
    assert all(r['years_remaining'] is None for r in result['rows'])


def test_trade_value_id_join_name_fallback_and_wrapper(warehouse):
    _new_warehouse(warehouse)
    result = league.get_trade_value.invoke({'team_a': 'BOS', 'players_a': 'Different Salary Name', 'team_b': 'NYK', 'players_b': 'Fallback Example Jr.'})
    assert result['ok'], result
    first = result['rows']['team_a']['players'][0]
    assert first['salary_26_27'] == 100
    assert first['years_remaining'] == 2
    assert result['rows']['team_b']['players'][0]['salary_26_27'] == 200
    from analyst.tools.cba import _trade_value_rows
    assert _trade_value_rows(result['rows'])[0]['option_years'] == {'2027-28': 'player'}


def test_empty_and_conflicting_id_contracts(warehouse):
    _new_warehouse(warehouse)
    con = duckdb.connect(str(warehouse))
    con.execute('UPDATE silver_salaries SET PLAYER_ID = 99, PLAYER_NAME = \'Different Stats Name\' WHERE PLAYER_ID = 1')
    con.close()
    result = league.get_contract_value.invoke({'season': '2025-26'})
    assert not result['ok']
    assert 'not enough qualified' in result['error']
    assert contract_details(None)['years_remaining'] is None


def test_vendor_fallback_does_not_override_primary_salary(warehouse):
    _new_warehouse(warehouse)
    con = duckdb.connect(str(warehouse))
    try:
        con.execute('CREATE TABLE silver_cap_players (player VARCHAR, team VARCHAR, salary BIGINT)')
        con.execute("INSERT INTO silver_cap_players VALUES ('Different Salary Name', 'BOS', 999), ('Vendor Only', 'NYK', 300)")
        records = salary_records(con, '2026-27', include_fallback=True)
        assert len(records) == 3
        by_name = {r['PLAYER_NAME']: r['salary'] for r in records}
        assert by_name['Different Salary Name'] == 100
        assert by_name['Vendor Only'] == 300
    finally:
        con.close()


def test_schedule_availability_depends_on_salary_data_not_slug():
    row = {'SALARY': 100, 'SALARY_2026_27': 100, 'SALARY_2027_28': 110, '_season': '2026-27'}
    assert contract_details(row)['years_remaining'] == 2
    row['SALARY'] = None
    row['SALARY_2026_27'] = None
    row['SALARY_2027_28'] = None
    assert contract_details(row)['years_remaining'] is None


def test_primary_salary_obligations_are_not_deduplicated_by_id(warehouse):
    _new_warehouse(warehouse)
    con = duckdb.connect(str(warehouse))
    try:
        con.execute("INSERT INTO silver_salaries SELECT PLAYER_NAME, 'NYK', PLAYER_ID, 50, BREF_SLUG, GUARANTEED, 50, SALARY_2027_28, OPTION_2026_27, OPTION_2027_28, _season FROM silver_salaries WHERE PLAYER_ID = 1")
        assert len(salary_records(con)) == 3
        total, players = league._payroll('NYK', con)
        assert total == 250
        assert len(players) == 2
    finally:
        con.close()


def test_seed_rejects_canonical_database(monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'scripts/seed_salaries.py'
    spec = importlib.util.spec_from_file_location('seed_salaries_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr('sys.argv', [str(path), '--scratch-db', str(store.CANONICAL_DB_PATH)])
    with pytest.raises(SystemExit):
        module.main()
