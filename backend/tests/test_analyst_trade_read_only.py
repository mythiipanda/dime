import duckdb
from shared import store
from shared.tools import get_trade_check


def test_trade_checker_reads_configured_warehouse_without_write_access(monkeypatch, tmp_path):
    path = tmp_path / 'configured.duckdb'
    with duckdb.connect(str(path)) as con:
        con.execute('CREATE TABLE silver_salaries(PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY INTEGER, _season VARCHAR)')
        con.execute("INSERT INTO silver_salaries VALUES ('Luka Doncic', 'LAL', 50000000, '2026-27')")
    monkeypatch.setattr(store, 'DB_PATH', path)
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    original = store.connect
    modes = []
    def connect(**kwargs):
        modes.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(store, 'connect', connect)
    with duckdb.connect(str(path), read_only=True):
        result = get_trade_check.invoke({'team_a': 'DAL', 'team_b': 'NYK', 'players_a': 'Luka Doncic', 'players_b': 'Karl-Anthony Towns', 'season': '2026-27'})
    assert modes and all(mode == {'read_only': True} for mode in modes)
    assert result['ok'] is False
    assert 'salary data lists Luka Doncic with LAL, not DAL' in result['error']
    store.warehouse_pool_clear()


def test_product_trade_returns_domain_errors_instead_of_mcp_exceptions(monkeypatch):
    from analyst.direct_data import product_trade
    from shared import tools
    from types import SimpleNamespace
    def fail(args):
        raise ValueError('Invalid season: garbage')
    monkeypatch.setattr(tools, 'get_trade_check', SimpleNamespace(invoke=fail))
    result = product_trade.invoke({'team_a': 'DAL', 'players_a': 'A', 'team_b': 'NYK', 'players_b': 'B', 'season': 'garbage'})
    assert result == {'ok': False, 'error': 'Invalid season: garbage'}
