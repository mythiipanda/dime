
import sys
import threading
import time
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store

def _hold_write_conn(path: str, hold_s: float):
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
    time.sleep(0.3)
    try:
        con = store.connect(read_only=True)
    finally:
        t.join()
    try:
        assert con.execute("SELECT 1").fetchone()[0] == 1
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
    try:
        assert con.execute("SELECT 1").fetchone()[0] == 1
    finally:
        con.close()

def _hold_read_conn(path: str, hold_s: float):
    con = duckdb.connect(path, read_only=True)
    time.sleep(hold_s)
    con.close()


def test_write_connect_retries_through_racing_read_lock(tmp_path,
                                                        monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "lockr.duckdb")
    duckdb.connect(str(tmp_path / "lockr.duckdb")).close()
    t = threading.Thread(target=_hold_read_conn,
                         args=(str(tmp_path / "lockr.duckdb"), 0.8))
    t.start()
    time.sleep(0.2)
    try:
        con = store.connect(read_only=False)
    finally:
        t.join()
    try:
        assert con.execute("SELECT 1").fetchone()[0] == 1
    finally:
        con.close()


def test_write_connect_still_fails_when_read_truly_held(tmp_path,
                                                        monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "lockh.duckdb")
    duckdb.connect(str(tmp_path / "lockh.duckdb")).close()
    held = duckdb.connect(str(tmp_path / "lockh.duckdb"), read_only=True)
    try:
        try:
            store.connect(read_only=False)
            raise AssertionError("write must fail while a read is held")
        except store.WriteConflictError:
            pass
    finally:
        held.close()


def test_no_contention_connects_immediately(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "free.duckdb")
    con = store.connect()
    try:
        assert con.execute("SELECT 1").fetchone()[0] == 1
    finally:
        con.close()
    con = store.connect(read_only=True)
    try:
        assert con.execute("SELECT 1").fetchone()[0] == 1
    finally:
        con.close()
    con = store.connect()
    try:
        assert con.execute("SELECT 1").fetchone()[0] == 1
    finally:
        con.close()


def test_concurrent_write_units_serialize_without_conflicts(tmp_path,
                                                            monkeypatch):
    import polars as pl
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "lockw.duckdb")
    duckdb.connect(str(tmp_path / "lockw.duckdb")).close()
    errors = []

    def writer(i):
        try:
            frame = pl.DataFrame({"game_id": [str(i)], "val": [i]})
            store.write_unit("t_units", frame, "2025-26", "test",
                             f"e{i}", "1=0", [])
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"concurrent writes raised: {errors}"
    con = duckdb.connect(str(tmp_path / "lockw.duckdb"), read_only=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM t_units").fetchone()[0]
        assert n == 4
    finally:
        con.close()
