"""Concurrent same-process duckdb.connect() race regression.

Two threads opening the warehouse at once race duckdb's attach step;
the loser used to get BinderException 'Cannot attach "warehouse" -
already attached', which connect() did not retry. get_compare's zones
sub-call swallowed that and silently emitted blank rim/three shares
(the test_compare_fastpath flake). connect() now retries it.
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store  # noqa: E402


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
        # Missing table returns an empty frame; the point is the connect
        # path must not raise BinderException under the attach race.
        return store.read_frame("definitely_not_a_table")

    with ThreadPoolExecutor(max_workers=8) as pool:
        frames = list(pool.map(_read, range(32)))
    assert all(f.height == 0 for f in frames)


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
