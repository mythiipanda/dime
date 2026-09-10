"""store.connect lock-contention tests (Ticket C).

DuckDB holds an exclusive file lock while any process keeps a
read-write connection open -- even idle, even for read_only openers,
which fail with "Conflicting lock is held". Seed scripts and the app
server both open short-lived write connections, so transient lock
contention is normal. store.connect must ride it out with retries
instead of failing the read.

These tests hold a real write connection open in another thread and
assert a read_only connect succeeds (without the retry it raises).
"""

import sys
import threading
import time
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store


def _hold_write_conn(path: str, hold_s: float):
    """Open a read-write connection and keep it open for hold_s."""
    con = duckdb.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS __lockt(x INT)")
    time.sleep(hold_s)
    con.close()


def test_read_only_connect_retries_through_writer_lock(tmp_path,
                                                       monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "lock.duckdb")
    t = threading.Thread(target=_hold_write_conn,
                         args=(str(tmp_path / "lock.duckdb"), 2.0))
    t.start()
    time.sleep(0.3)  # let the writer grab the lock
    try:
        con = store.connect(read_only=True)
    finally:
        t.join()
    try:
        con.execute("SELECT 1").fetchone()
    finally:
        con.close()


def test_read_write_connect_retries_through_writer_lock(tmp_path,
                                                        monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "lock2.duckdb")
    t = threading.Thread(target=_hold_write_conn,
                         args=(str(tmp_path / "lock2.duckdb"), 1.5))
    t.start()
    time.sleep(0.3)
    try:
        con = store.connect()
    finally:
        t.join()
    con.close()


def test_no_contention_connects_immediately(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "free.duckdb")
    con = store.connect()  # creates the file
    con.close()
    con = store.connect(read_only=True)
    con.close()
    con = store.connect()
    con.close()
