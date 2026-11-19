
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
