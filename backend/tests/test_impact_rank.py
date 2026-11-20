import duckdb
from shared import store
from shared.tools import get_impact_rank


def _use_warehouse(monkeypatch, tmp_path, tables):
    path = tmp_path / 'impact.duckdb'
    with duckdb.connect(str(path)) as con:
        if 'impact' in tables:
            con.execute('CREATE TABLE silver_impact(PLAYER_NAME VARCHAR, TEAM VARCHAR, MP INTEGER, BPM DOUBLE, VORP DOUBLE, _source VARCHAR, _season VARCHAR)')
            con.executemany("INSERT INTO silver_impact VALUES (?, ?, ?, ?, ?, 'basketball-reference:advanced', '2025-26')", [
                ('Nikola Jokic', 'DEN', 2265, 14.2, 9.2),
                ('Shai Gilgeous-Alexander', 'OKC', 2259, 11.7, 7.8),
                ('Jaylen Brown', 'BOS', 2100, 4.5, 2.1),
                ('Bench Guy', 'ORL', 100, -3.0, -0.5)])
        if 'rapm' in tables:
            con.execute('CREATE TABLE silver_rapm(player_id INTEGER, name VARCHAR, rapm DOUBLE, possessions INTEGER, _source VARCHAR, _season VARCHAR)')
            con.executemany("INSERT INTO silver_rapm VALUES (?, ?, ?, ?, 'rapm-lite', '2025-26')", [
                (1, 'Nikola Jokic', 6.1, 4000),
                (2, 'Jaylen Brown', 2.4, 3800),
                (3, 'Bench Guy', -1.0, 900)])
        if 'rapm_prior' in tables:
            con.execute('CREATE TABLE silver_rapm_prior(player_id INTEGER, name VARCHAR, rapm DOUBLE, possessions INTEGER, _source VARCHAR, _season VARCHAR)')
            con.executemany("INSERT INTO silver_rapm_prior VALUES (?, ?, ?, ?, 'rapm-lite', '2024-25')", [
                (1, 'Nikola Jokic', 7.0, 6000),
                (2, 'Jaylen Brown', 3.1, 5200)])
        if 'raptor' in tables:
            con.execute('CREATE TABLE silver_raptor_player(PLAYER_NAME VARCHAR, RAPTOR_TOTAL DOUBLE, MP INTEGER, _source VARCHAR, _season VARCHAR)')
            con.executemany("INSERT INTO silver_raptor_player VALUES (?, ?, ?, 'fivethirtyeight:raptor', '2020-21')", [
                ('Nikola Jokic', 9.9, 2500),
                ('Jaylen Brown', 4.0, 2300)])
    monkeypatch.setattr(store, 'DB_PATH', path)
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    return path


def test_impact_rank_prefers_published_bpm(monkeypatch, tmp_path):
    _use_warehouse(monkeypatch, tmp_path, ('impact',))
    r = get_impact_rank.invoke({'player': 'Jaylen Brown', 'season': '2025-26'})
    assert r['ok'] is True
    row = r['rows'][0]
    assert row['metric'] == 'bpm'
    assert row['value'] == 4.5
    assert row['rank'] == 3
    assert row['players'] == 4
    assert row['source'] == 'basketball-reference:advanced'


def test_impact_rank_returns_one_row_per_metric(monkeypatch, tmp_path):
    _use_warehouse(monkeypatch, tmp_path, ('impact', 'rapm'))
    r = get_impact_rank.invoke({'player': 'Jaylen Brown', 'season': '2025-26'})
    metrics = {row['metric'] for row in r['rows']}
    assert metrics == {'bpm', 'rapm_lite'}
    rapm_row = next(row for row in r['rows'] if row['metric'] == 'rapm_lite')
    assert rapm_row['rank'] == 2


def test_impact_rank_falls_back_to_rapm_prior(monkeypatch, tmp_path):
    _use_warehouse(monkeypatch, tmp_path, ('rapm_prior',))
    r = get_impact_rank.invoke({'player': 'Jaylen Brown', 'season': '2024-25'})
    assert r['ok'] is True
    assert r['rows'][0]['metric'] == 'rapm_lite'
    assert r['rows'][0]['rank'] == 2


def test_impact_rank_falls_back_to_raptor(monkeypatch, tmp_path):
    _use_warehouse(monkeypatch, tmp_path, ('raptor',))
    r = get_impact_rank.invoke({'player': 'Jaylen Brown', 'season': '2020-21'})
    assert r['ok'] is True
    assert r['rows'][0]['metric'] == 'raptor_total'
    assert r['rows'][0]['rank'] == 2
    assert r['rows'][0]['source'] == 'fivethirtyeight:raptor'


def test_impact_rank_unknown_player(monkeypatch, tmp_path):
    _use_warehouse(monkeypatch, tmp_path, ('impact',))
    r = get_impact_rank.invoke({'player': 'Nobody Here', 'season': '2025-26'})
    assert r['ok'] is False
    assert 'unknown player' in r['error']


def test_impact_rank_uncovered_season(monkeypatch, tmp_path):
    _use_warehouse(monkeypatch, tmp_path, ('impact',))
    r = get_impact_rank.invoke({'player': 'Jaylen Brown', 'season': '1999-00'})
    assert r['ok'] is False
    assert 'coverage' in r['error']


def test_impact_rank_reads_configured_warehouse_without_write_access(monkeypatch, tmp_path):
    path = _use_warehouse(monkeypatch, tmp_path, ('impact',))
    original = store.connect
    modes = []
    def connect(**kwargs):
        modes.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(store, 'connect', connect)
    with duckdb.connect(str(path), read_only=True):
        get_impact_rank.invoke({'player': 'Jaylen Brown', 'season': '2025-26'})
    assert modes and all(mode == {'read_only': True} for mode in modes)
    store.warehouse_pool_clear()
