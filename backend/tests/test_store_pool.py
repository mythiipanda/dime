import sys
import threading
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store

@pytest.fixture(autouse=True)
def _pooled_warehouse(monkeypatch, tmp_path):
    db = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE t(x INTEGER)")
    con.execute("INSERT INTO t VALUES (1), (2)")
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_pool_clear()
    yield
    store.warehouse_pool_clear()

def test_sequential_reads_share_underlying_connection():
    a = store.connect(read_only=True)
    b = store.connect(read_only=True)
    assert a._con is b._con
    assert a._real is b._real
    assert a.execute("SELECT COUNT(*) FROM t").fetchone() == (2,)
    assert b.execute("SELECT COUNT(*) FROM t").fetchone() == (2,)

def test_wrapper_close_is_noop_and_pool_survives():
    a = store.connect(read_only=True)
    a.close()
    b = store.connect(read_only=True)
    assert a._con is b._con
    assert a.execute("SELECT 1").fetchall() == [(1,)]
    assert b.execute("SELECT COUNT(*) FROM t").fetchone() == (2,)

def test_real_write_evicts_pooled_connection():
    a = store.connect(read_only=True)
    old = a._con
    assert a.execute("SELECT COUNT(*) FROM t").fetchone() == (2,)
    old.close()
    w = duckdb.connect(str(store.DB_PATH))
    try:
        w.execute("INSERT INTO t VALUES (3)")
    finally:
        w.close()
    b = store.connect(read_only=True)
    assert b._con is not old
    assert b.execute("SELECT COUNT(*) FROM t").fetchone() == (3,)

def test_write_connects_are_unpooled_with_real_close():
    a = store.connect(read_only=False)
    assert isinstance(a, duckdb.DuckDBPyConnection)
    assert not hasattr(a, "_con")
    assert not hasattr(a, "_real")
    assert getattr(store._pool_state, "entry", None) is None
    a.close()
    with pytest.raises(Exception):
        a.execute("SELECT 1")
    b = store.connect(read_only=False)
    assert b is not a
    assert isinstance(b, duckdb.DuckDBPyConnection)
    assert not hasattr(b, "_con")
    b.close()
    assert getattr(store._pool_state, "entry", None) is None

def test_pool_is_thread_local():
    main_con = store.connect(read_only=True)
    seen = []

    def _worker():
        try:
            wcon = store.connect(read_only=True)
            seen.append(wcon._con)
        finally:
            store.warehouse_pool_clear()

    th = threading.Thread(target=_worker)
    th.start()
    th.join()
    assert len(seen) == 1
    assert seen[0] is not main_con._con

def test_pool_clear_forces_fresh_connection():
    a = store.connect(read_only=True)
    old = a._con
    store.warehouse_pool_clear()
    b = store.connect(read_only=True)
    assert b._con is not old

def test_pooled_connection_supports_with_block():
    with store.connect(read_only=True) as c:
        assert c.execute("SELECT COUNT(*) FROM t").fetchone() == (2,)
        inner = c._con
    d = store.connect(read_only=True)
    assert d._con is inner
    assert d.execute("SELECT COUNT(*) FROM t").fetchone() == (2,)

def test_write_connect_succeeds_while_read_pooled():
    r = store.connect(read_only=True)
    assert r.execute("SELECT COUNT(*) FROM t").fetchone() == (2,)
    w = store.connect()
    try:
        w.execute("INSERT INTO t VALUES (99)")
        assert w.execute(
            "SELECT COUNT(*) FROM t WHERE x = 99").fetchone() == (1,)
    finally:
        w.close()
    b = store.connect(read_only=True)
    assert b.execute(
        "SELECT COUNT(*) FROM t WHERE x = 99").fetchone() == (1,)

def test_write_connect_evicts_pooled_reads():
    a = store.connect(read_only=True)
    old = a._con
    assert a.execute("SELECT COUNT(*) FROM t").fetchone() == (2,)
    w = store.connect()
    w.close()
    b = store.connect(read_only=True)
    assert b._con is not old
