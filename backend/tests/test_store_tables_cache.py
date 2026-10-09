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

def test_warm_hit_avg_under_1ms_no_requery(warehouse_db, show_counter):
    import time
    assert store.tables() == {"t1"}
    assert len(show_counter) == 1
    calls = 50
    start = time.perf_counter()
    for _ in range(calls):
        assert store.tables() == {"t1"}
    elapsed = time.perf_counter() - start
    assert elapsed / calls < 0.001
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

def test_external_writer_new_table_visible_without_pool_event(tmp_path):
    db = tmp_path / "ext.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE t1(x INTEGER)")
    con.execute("INSERT INTO t1 VALUES (1)")
    con.close()
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    try:
        assert store.tables(db) == {"t1"}
        writer = duckdb.connect(str(db))
        try:
            writer.execute("CREATE TABLE t2(y VARCHAR)")
            writer.execute("INSERT INTO t2 VALUES ('a')")
        finally:
            writer.close()
        assert store.tables(db) == {"t1", "t2"}
    finally:
        store.warehouse_pool_clear()
        store.warehouse_tables_cache_clear()

def test_freshness_key_discriminates_same_size_same_mtime(tmp_path):
    import os
    size = 20000
    same_ns = 1700000000000000000
    f1 = tmp_path / "a.bin"
    f2 = tmp_path / "b.bin"
    f1.write_bytes(b"A" * size)
    f2.write_bytes(b"A" * (size // 2) + b"B" + b"A" * (size - size // 2 - 1))
    os.utime(f1, ns=(same_ns, same_ns))
    os.utime(f2, ns=(same_ns, same_ns))
    s1 = os.stat(f1)
    s2 = os.stat(f2)
    assert s1.st_size == s2.st_size == size
    assert s1.st_mtime_ns == s2.st_mtime_ns == same_ns
    assert f1.read_bytes() != f2.read_bytes()
    assert store._warehouse_freshness_key(f1) != store._warehouse_freshness_key(f2)

def test_external_rewrite_restored_mtime_visible_through_tables(tmp_path):
    import os
    db = tmp_path / "rewrite.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE t1(x INTEGER)")
    con.execute("INSERT INTO t1 VALUES (1)")
    con.close()
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    try:
        assert store.tables(db) == {"t1"}
        st = os.stat(db)
        other = tmp_path / "other.duckdb"
        w = duckdb.connect(str(other))
        w.execute("CREATE TABLE t2(y VARCHAR)")
        w.execute("INSERT INTO t2 VALUES ('a')")
        w.close()
        os.replace(other, db)
        os.utime(db, ns=(st.st_atime_ns, st.st_mtime_ns))
        assert store.tables(db) == {"t2"}
    finally:
        store.warehouse_pool_clear()
        store.warehouse_tables_cache_clear()
