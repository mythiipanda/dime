import base64
import io

import duckdb
import polars as pl
import pytest

from analyst import dataset_engine as engine
from shared import store
from shared.sources.base import FetchMeta, FetchResult


@pytest.fixture
def warehouse(monkeypatch, tmp_path):
    path = tmp_path / 'shots.duckdb'
    with duckdb.connect(str(path)) as con:
        con.execute('CREATE TABLE silver_shots(LOC_X INTEGER, LOC_Y INTEGER, _season VARCHAR, _entity VARCHAR, _source VARCHAR, _fetched_at VARCHAR)')
        con.execute("INSERT INTO silver_shots VALUES (1, 2, '2025-26', 'player:2544', 'cached', 'stamp'), (3, 4, '2024-25', 'player:201939', 'cached', 'stamp')")
    modes = []
    def read_connect():
        modes.append(True)
        return duckdb.connect(str(path), read_only=True)
    def refuse_write(*args, **kwargs):
        pytest.fail('Shot datasets must not write to the warehouse')
    monkeypatch.setattr(store, 'DB_PATH', path)
    monkeypatch.setattr(store, 'read_connect', read_connect)
    monkeypatch.setattr(store, 'tables', lambda: ['silver_shots'])
    monkeypatch.setattr(store, 'save_frame', refuse_write)
    before = path.read_bytes()
    yield path, modes
    assert all(modes)
    assert path.read_bytes() == before


def live_result(frame=None, error=''):
    return FetchResult(frame=frame if frame is not None else pl.DataFrame(), meta=FetchMeta('nba_stats', '2025-26', 'live-stamp'), ok=not error, error=error)


def test_cached_shots_are_read_only_and_entity_scoped(warehouse, monkeypatch):
    monkeypatch.setattr(engine, '_datasets_fetch_live', lambda *args: pytest.fail('Unexpected live fetch'))
    out = engine.dataset('shots', season='2025-26', player_id=2544)
    assert warehouse[1] == [True, True]
    assert out['data'][0]['LOC_X'] == 1
    assert out['meta']['cached'] is True


@pytest.mark.parametrize('fmt', ['json', 'csv', 'parquet'])
def test_live_shots_never_save_or_reread_the_warehouse(warehouse, monkeypatch, fmt):
    frame = pl.DataFrame({'LOC_X': [100], 'LOC_Y': [200], 'SHOT_MADE_FLAG': [1]})
    monkeypatch.setattr(engine, '_datasets_fetch_live', lambda *args: live_result(frame))
    out = engine.dataset('shots', season='2025-26', player_id=201939, fmt=fmt)
    if fmt == 'json':
        assert out['ok'] is True
        assert out['data'] == frame.to_dicts()
        assert out['meta'] == {'season': '2025-26', 'rows': 1, 'cached': False, 'source': 'nba_stats', 'fetched_at': 'live-stamp'}
    else:
        data = io.BytesIO(base64.b64decode(out['body']))
        decoded = pl.read_csv(data) if fmt == 'csv' else pl.read_parquet(data)
        assert decoded.to_dicts() == frame.to_dicts()


@pytest.mark.parametrize('missing_table', [False, True])
@pytest.mark.parametrize('error', ['', 'empty upstream response', 'NBA shot endpoint unavailable'])
def test_no_shots_and_upstream_failures_are_readable(warehouse, monkeypatch, missing_table, error):
    if missing_table:
        monkeypatch.setattr(store, 'tables', lambda: [])
    monkeypatch.setattr(engine, '_datasets_fetch_live', lambda *args: live_result(error=error))
    out = engine.dataset('shots', season='2025-26', player_id=201939)
    if error == 'NBA shot endpoint unavailable':
        assert out['ok'] is False
        assert out['error'] == error
    else:
        assert out['ok'] is True
        assert out['data'] == []
        assert out['meta']['rows'] == 0
