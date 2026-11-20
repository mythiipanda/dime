from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import duckdb
import pytest

from analyst import dataset_engine as engine
from shared import store


@pytest.fixture
def warehouse(monkeypatch, tmp_path):
    path = str(tmp_path / 'views.duckdb')
    con = duckdb.connect(path)
    con.execute('CREATE TABLE silver_sample(value INTEGER, _season VARCHAR, _fetched_at VARCHAR)')
    con.execute("INSERT INTO silver_sample SELECT range, '2025-26', '2026-04-13' FROM range(80)")
    con.execute("INSERT INTO silver_sample VALUES (99, '2024-25', '2025-04-13')")
    con.execute('CREATE TABLE silver_empty(value DOUBLE)')
    con.execute('CREATE TABLE private_state(secret VARCHAR)')
    con.close()
    modes = []
    def connect(**kwargs):
        modes.append(kwargs)
        return duckdb.connect(path, **kwargs)
    monkeypatch.setattr(store, 'connect', connect)
    return path, modes


def test_table_detail_actual_schema_bounded_rows_and_seasons(warehouse):
    _, modes = warehouse
    result = engine.warehouse_table('silver_sample', '2025-26')
    assert result['count'] == 80
    assert len(result['rows']) == result['limit'] == 50
    assert result['columns'][0] == {'name': 'value', 'type': 'INTEGER'}
    assert result['seasons'] == ['2025-26', '2024-25']
    assert result['last_fetch'] == '2026-04-13'
    assert modes == [{'read_only': True}]
    assert engine.warehouse_table('silver_sample', "' OR 1=1 --")['rows'] == []


def test_empty_and_unknown_tables(warehouse):
    result = engine.warehouse_table('silver_empty')
    assert result['columns'] == [{'name': 'value', 'type': 'DOUBLE'}]
    assert result['rows'] == [] and result['count'] == 0
    for table in ['silver_missing', 'private_state', 'silver_sample;DROP TABLE silver_sample', '../silver_sample']:
        assert engine.warehouse_table(table)['ok'] is False


def test_home_has_no_samples_when_sources_absent(warehouse):
    result = engine.home_snapshot()
    assert result['schedule']['available'] is False
    assert result['schedule']['games'] == []
    assert result['schedule']['next_date'] is None
    assert result['snapshot']['rows'] == []


def test_home_real_schedule_next_date_ratings_and_citations(warehouse):
    path, _ = warehouse
    today = datetime.now(ZoneInfo('America/New_York')).date()
    tomorrow = today + timedelta(days=1)
    with duckdb.connect(path) as con:
        con.execute('CREATE TABLE silver_scoreboard(GAME_ID VARCHAR, GAME_DATE_EST VARCHAR, HOME_TEAM_ABBREVIATION VARCHAR, _season VARCHAR, _fetched_at VARCHAR)')
        con.execute('INSERT INTO silver_scoreboard VALUES (?, ?, ?, ?, ?), (?, ?, ?, ?, ?)', ['today', str(today), 'BOS', '2026-27', 'stamp', 'next', str(tomorrow), 'NYK', '2026-27', 'stamp'])
        con.execute('CREATE TABLE silver_team_ratings(TEAM_NAME VARCHAR, GP INTEGER, NET_RATING DOUBLE, _season VARCHAR, _fetched_at VARCHAR)')
        con.execute("INSERT INTO silver_team_ratings VALUES ('Boston', 82, 10.3, '2025-26', 'fetched'), ('Old', 82, 30.0, '2024-25', 'old')")
    result = engine.home_snapshot()
    assert result['schedule']['games'][0]['GAME_ID'] == 'today'
    assert result['schedule']['next_date'] == str(tomorrow)
    assert result['schedule']['seasons'] == ['2026-27']
    assert result['snapshot']['table'] == 'silver_team_ratings'
    assert result['snapshot']['season'] == '2025-26'
    assert result['snapshot']['last_fetch'] == 'fetched'
    assert result['snapshot']['rows'][0]['TEAM_NAME'] == 'Boston'
    with duckdb.connect(path) as con:
        con.execute("DELETE FROM silver_scoreboard WHERE GAME_ID = 'today'")
    result = engine.home_snapshot()
    assert result['schedule']['available'] is True
    assert result['schedule']['games'] == []
    assert result['schedule']['next_date'] == str(tomorrow)


def test_home_team_schedule_uses_eastern_dates_and_deduplicates_games(warehouse):
    path, _ = warehouse
    today = datetime.now(ZoneInfo('America/New_York')).date()
    tomorrow = today + timedelta(days=1)
    following = today + timedelta(days=2)
    with duckdb.connect(path) as con:
        con.execute('CREATE TABLE silver_schedule(id VARCHAR, date VARCHAR, name VARCHAR, _season VARCHAR, _fetched_at VARCHAR)')
        con.execute('INSERT INTO silver_schedule VALUES (?, ?, ?, ?, ?)', ['next', f'{following}T01:30Z', 'New York Knicks at Boston Celtics', '2026-27', 'stamp'])
    result = engine.home_snapshot()['schedule']
    assert result['table'] == 'silver_schedule'
    assert result['games'] == []
    assert result['next_date'] == str(tomorrow)
    assert result['last_fetch'] == 'stamp'
    with duckdb.connect(path) as con:
        for _ in range(2):
            con.execute('INSERT INTO silver_schedule VALUES (?, ?, ?, ?, ?)', ['today', f'{tomorrow}T01:30Z', 'Atlanta Hawks at Toronto Raptors', '2026-27', 'stamp'])
    result = engine.home_snapshot()['schedule']
    assert len(result['games']) == 1
    assert result['games'][0]['id'] == 'today'
    assert result['seasons'] == ['2026-27']


def test_warehouse_errors_are_not_replaced_by_fixtures(monkeypatch):
    def fail(**kwargs):
        raise RuntimeError('offline')
    monkeypatch.setattr(store, 'connect', fail)
    for operation in [engine.home_snapshot, lambda: engine.warehouse_table('silver_sample')]:
        with pytest.raises(RuntimeError, match='offline'):
            operation()


def test_zone_dataset_uses_zero_floor_and_keeps_formats(monkeypatch):
    from types import SimpleNamespace
    from shared.tools import player
    calls = []
    def invoke(args):
        calls.append(args)
        return {'ok': True, 'rows': [{'zone': 'rim', 'FGA': 1}], 'meta': {'source': 'warehouse:test', 'season': '2025-26'}}
    monkeypatch.setattr(player, 'get_shot_zones', SimpleNamespace(invoke=invoke))
    result = engine.dataset('zone_splits', player_id=2544)
    assert result['data'] == [{'zone': 'rim', 'FGA': 1}]
    assert calls[0]['min_attempts'] == 0
    for fmt in ['csv', 'parquet']:
        assert engine.dataset('zone_splits', player_id=2544, fmt=fmt)['encoding'] == 'base64'
    assert engine.dataset('zone_splits')['ok'] is False
    monkeypatch.setattr(player, 'get_shot_zones', SimpleNamespace(invoke=lambda args: {'ok': False, 'error': 'no shots'}))
    assert engine.dataset('zone_splits', player_id=2544)['error'] == 'no shots'


def test_zero_floor_is_not_clamped(monkeypatch):
    from shared.tools.player import shot_profile
    seen = []
    monkeypatch.setattr(shot_profile, '_hist_shot_zone_result', lambda player, season, floor, year: seen.append(floor) or {'ok': True, 'rows': []})
    shot_profile.get_shot_zones.invoke({'player_id': 2544, 'season': '2025-26', 'min_attempts': 0})
    shot_profile.get_shot_zones.invoke({'player_id': 2544, 'season': '2025-26', 'min_attempts': 1})
    assert seen == [0, 10]


def test_zero_floor_keeps_low_volume_zones_without_dividing_by_zero():
    from shared.tools import player
    from shared.tools.player.shot_profile import _hist_zone_rows
    attempts = {zone: [0, 0] for zone in player._HIST_ZONE_KEYS}
    zone = next(iter(attempts))
    attempts[zone] = [1, 2]
    league = {zone: [0, 0] for zone in attempts}
    rows, excluded = _hist_zone_rows(attempts, league, 2, 0)
    assert len(rows) == 1
    assert rows[0]['FGA'] == 2
    assert rows[0]['FG_PCT'] == 0.5
    assert len(excluded) == len(attempts) - 1
