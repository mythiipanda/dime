
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store

@pytest.fixture(autouse=True)
def _isolated_pool():
    store.warehouse_pool_clear()
    yield
    store.warehouse_pool_clear()

def test_concurrent_reads_all_succeed():
    def _read(_i):
        con = store.connect(read_only=True)
        try:
            con.execute("SELECT 1").fetchone()
        finally:
            con.close()
        return True

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_read, range(32)))
    assert all(results)

def test_concurrent_read_frames_no_binder_error():
    def _read(_i):
        return store.read_frame_optional("definitely_not_a_table")

    with ThreadPoolExecutor(max_workers=8) as pool:
        frames = list(pool.map(_read, range(32)))
    assert all(f.height == 0 for f in frames)

def test_concurrent_absent_reads_all_raise_table_absent():
    def _read(_i):
        return store.read_frame("definitely_not_a_table")

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_read, i) for i in range(32)]
        raised = [f.exception() for f in futures]

    assert all(isinstance(exc, store.TableAbsent) for exc in raised)
    assert all(exc.table == "definitely_not_a_table" for exc in raised)
    assert all(str(exc.warehouse).endswith(".duckdb") for exc in raised)

def test_read_frame_opens_frozen_warehouse_read_only(monkeypatch):
    calls=[]
    real=store.connect
    def observed(read_only=False):
        calls.append(read_only)
        return real(read_only=True)
    monkeypatch.setattr(store,"connect",observed)
    store.read_frame("fetch_log")
    assert calls == [True]

def test_default_connect_keeps_canonical_warehouse_immutable(monkeypatch):
    calls=[]
    monkeypatch.setattr(store, "_connect_once", lambda read_only: calls.append(read_only) or object())
    store.connect()
    assert calls == [True]

def test_canonical_write_fails_before_duckdb_open(monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", store.CANONICAL_DB_PATH)
    opened=[]
    monkeypatch.setattr(store.duckdb,"connect",lambda *a,**k: opened.append((a,k)))
    import pytest
    with pytest.raises(PermissionError, match="immutable"):
        store.connect(read_only=False)
    assert opened == []

def test_operational_state_cannot_alias_canonical(monkeypatch):
    monkeypatch.setattr(store,"STATE_PATH",store.CANONICAL_DB_PATH)
    import pytest
    with pytest.raises(PermissionError, match="cannot target"):
        store.state_connect()

def test_representative_read_and_state_workflow_preserves_canonical(monkeypatch, tmp_path):
    import hashlib
    before = hashlib.sha256(store.CANONICAL_DB_PATH.read_bytes()).hexdigest()
    monkeypatch.setattr(store, "DB_PATH", store.CANONICAL_DB_PATH)
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.duckdb")
    monkeypatch.setattr(store, "STATE_LOCK_PATH", tmp_path / ".state.lock")
    frame = store.read_frame("silver_team_games", "_season = ?", ["2025-26"])
    assert frame.height > 0
    store.save_chat("thread", "human", "hello", owner="owner")
    store.save_facts("thread", ["fact"], owner="owner")
    store.save_run("thread", "q", "a", [], [], owner="owner")
    assert store.chat_history("thread")[-1]["text"] == "hello"
    assert store.thread_facts("thread") == ["fact"]
    assert store.list_runs("thread", "owner")[0]["answer"] == "a"
    after = hashlib.sha256(store.CANONICAL_DB_PATH.read_bytes()).hexdigest()
    assert after == before

def test_absent_warehouse_fails_fast_without_retry_burn(monkeypatch, tmp_path):
    import pytest
    import time as time_mod
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "absent.duckdb")
    sleeps = []
    monkeypatch.setattr(time_mod, "sleep", lambda s: sleeps.append(s))
    start = time_mod.monotonic()
    with pytest.raises(FileNotFoundError, match="warehouse absent"):
        store.connect(read_only=True)
    assert time_mod.monotonic() - start < 5.0
    assert sleeps == []
