import sys
import threading
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store


@pytest.fixture()
def warehouse_db(monkeypatch, tmp_path):
    db = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE t1(x INTEGER)")
    con.execute("INSERT INTO t1 VALUES (1)")
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    yield db
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()


class _CountingProxy:
    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def execute(self, sql=None, *args, **kwargs):
        if isinstance(sql, str) and sql.strip().upper().startswith("SHOW TABLES"):
            object.__getattribute__(self, "_counts").append(1)
        return object.__getattribute__(self, "_real").execute(sql, *args, **kwargs) if sql is not None else object.__getattribute__(self, "_real").execute()

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_real"), name)

    def close(self):
        try:
            return object.__getattribute__(self, "_real").close()
        except Exception:
            return None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture()
def show_counter(monkeypatch):
    counts = []
    real_connect = store.connect

    def _counting(*args, **kwargs):
        proxy = _CountingProxy(real_connect(*args, **kwargs))
        object.__setattr__(proxy, "_counts", counts)
        return proxy

    monkeypatch.setattr(store, "connect", _counting)
    return counts


def test_cache_hit_avoids_requery(warehouse_db, show_counter):
    first = store.tables()
    assert first == {"t1"}
    assert len(show_counter) == 1
    second = store.tables()
    assert second == {"t1"}
    assert len(show_counter) == 1
    assert second == first
    assert second is not first


def test_stat_change_invalidates(warehouse_db, show_counter):
    assert store.tables() == {"t1"}
    assert len(show_counter) == 1
    con = store.connect(read_only=True)
    try:
        con.execute("SELECT 1").fetchall()
    finally:
        con.close()
    saved = store._pool_state.entry
    store.warehouse_pool_clear()
    raw = duckdb.connect(str(warehouse_db))
    try:
        raw.execute("CREATE TABLE t2(y VARCHAR)")
        raw.execute("INSERT INTO t2 VALUES ('a')")
    finally:
        raw.close()
    store._pool_state.entry = saved
    con2 = store.connect(read_only=True)
    try:
        con2.execute("SELECT 1").fetchall()
    finally:
        con2.close()
    assert store.tables() == {"t1", "t2"}
    assert len(show_counter) == 2


def test_warm_hit_touches_no_filesystem(warehouse_db, show_counter, monkeypatch):
    assert store.tables() == {"t1"}
    assert len(show_counter) == 1
    import os as _os
    import pathlib as _pathlib

    def _boom(*args, **kwargs):
        raise AssertionError("touched")

    monkeypatch.setattr(_pathlib.Path, "stat", _boom)
    monkeypatch.setattr(_os, "stat", _boom)
    assert store.tables() == {"t1"}
    assert len(show_counter) == 1


def test_cache_clear_forces_requery(warehouse_db, show_counter):
    assert store.tables() == {"t1"}
    assert store.tables() == {"t1"}
    assert len(show_counter) == 1
    store.warehouse_tables_cache_clear()
    assert store.tables() == {"t1"}
    assert len(show_counter) == 2


def test_write_path_eviction_invalidates(warehouse_db, show_counter):
    assert store.tables() == {"t1"}
    assert len(show_counter) == 1
    assert store.tables() == {"t1"}
    assert len(show_counter) == 1
    con = store.connect(read_only=False)
    try:
        con.execute("CREATE TABLE t3(z INTEGER)")
    finally:
        con.close()
    names = store.tables()
    assert "t3" in names
    assert len(show_counter) == 2


def test_concurrent_access_is_consistent(warehouse_db):
    assert store.tables() == {"t1"}
    store.warehouse_tables_cache_clear()
    errors = []
    results = []
    barrier = threading.Barrier(8)

    def _worker():
        try:
            barrier.wait(timeout=10)
            results.append(store.tables())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=30)
    assert errors == []
    assert len(results) == 8
    for names in results:
        assert names == {"t1"}


def test_missing_path_falls_back_without_caching(warehouse_db, tmp_path):
    missing = tmp_path / "nope.duckdb"
    with pytest.raises(Exception):
        store.tables(path=missing)
    assert store.tables() == {"t1"}
