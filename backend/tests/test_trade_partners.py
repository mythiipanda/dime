import duckdb
from shared import store
from shared.tools import get_trade_partners


def _seed_warehouse(path):
    with duckdb.connect(str(path)) as con:
        con.execute('CREATE TABLE silver_salaries(PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY_2026_27 INTEGER, _season VARCHAR)')
        rows = [
            ("Jaylen Brown", "BOS", 50_000_000),
        ] + [(f"Bos Filler {i}", "BOS", 26_000_000) for i in range(5)] + [
            ("Lauri Markkanen", "UTA", 46_000_000),
            ("Walker Kessler", "UTA", 12_000_000),
            ("John Collins", "UTA", 15_000_000),
        ] + [(f"Uta Filler {i}", "UTA", 17_000_000) for i in range(6)] + [
            ("Stephen Curry", "GSW", 55_000_000),
        ] + [(f"Gsw Filler {i}", "GSW", 25_000_000) for i in range(7)] + [
            ("Paolo Banchero", "ORL", 10_000_000),
            ("Franz Wagner", "ORL", 9_000_000),
        ] + [(f"Orl Filler {i}", "ORL", 12_000_000) for i in range(13)]
        con.executemany(
            "INSERT INTO silver_salaries VALUES (?, ?, ?, '2026-27')", rows)


def _use_warehouse(monkeypatch, tmp_path):
    path = tmp_path / 'partners.duckdb'
    _seed_warehouse(path)
    monkeypatch.setattr(store, 'DB_PATH', path)
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    return path


def test_trade_partners_returns_legal_packages(monkeypatch, tmp_path):
    _use_warehouse(monkeypatch, tmp_path)
    result = get_trade_partners.invoke({'player': 'Jaylen Brown', 'season': '2026-27'})
    assert result['ok'] is True
    meta = result['meta']
    assert meta['player'] == 'Jaylen Brown'
    assert meta['player_team'] == 'BOS'
    assert meta['player_salary'] == 50_000_000
    assert meta['season'] == '2026-27'
    rows = result['rows']
    assert rows
    uta = [r for r in rows if r['team'] == 'UTA']
    assert uta and all(r['legal'] for r in uta)
    assert any(r['players'] == 'Lauri Markkanen' for r in uta)
    assert all(r['package_salary'] <= meta['max_return_salary'] for r in rows)
    assert all(r['package_salary'] >= r['incoming'] * 0.79 for r in uta)


def test_trade_partners_second_apron_team_cannot_aggregate(monkeypatch, tmp_path):
    _use_warehouse(monkeypatch, tmp_path)
    result = get_trade_partners.invoke({'player': 'Jaylen Brown', 'season': '2026-27'})
    gsw = [r for r in result['rows'] if r['team'] == 'GSW']
    assert gsw
    assert all(',' not in r['players'] for r in gsw)
    assert all(r['over_apron2'] for r in gsw)


def test_trade_partners_lists_teams_without_fit(monkeypatch, tmp_path):
    _use_warehouse(monkeypatch, tmp_path)
    result = get_trade_partners.invoke({'player': 'Jaylen Brown', 'season': '2026-27'})
    assert 'ORL' in result['meta']['teams_without_fit']


def test_trade_partners_teams_filter(monkeypatch, tmp_path):
    _use_warehouse(monkeypatch, tmp_path)
    result = get_trade_partners.invoke({'player': 'Jaylen Brown', 'season': '2026-27', 'teams': 'UTA'})
    assert result['ok'] is True
    assert {r['team'] for r in result['rows']} == {'UTA'}


def test_trade_partners_unknown_player(monkeypatch, tmp_path):
    _use_warehouse(monkeypatch, tmp_path)
    result = get_trade_partners.invoke({'player': 'Nobody Here', 'season': '2026-27'})
    assert result['ok'] is False
    assert 'unknown player' in result['error']


def test_trade_partners_reads_configured_warehouse_without_write_access(monkeypatch, tmp_path):
    path = _use_warehouse(monkeypatch, tmp_path)
    original = store.connect
    modes = []
    def connect(**kwargs):
        modes.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(store, 'connect', connect)
    with duckdb.connect(str(path), read_only=True):
        get_trade_partners.invoke({'player': 'Jaylen Brown', 'season': '2026-27'})
    assert modes and all(mode == {'read_only': True} for mode in modes)
    store.warehouse_pool_clear()
