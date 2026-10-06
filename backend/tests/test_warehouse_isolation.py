import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from v2.adapters import coverage
from v2.adapters import core as adapter_core
from v2.adapters.capabilities import CAPABILITIES

_FETCHED_AT = "2026-01-01T00:00:00+00:00"

def _make_warehouse(db: Path) -> None:
    _make_warehouse_with_season(db, "2024-25")

@pytest.fixture()
def scratch(monkeypatch):
    directory = Path(tempfile.mkdtemp(prefix="whiso_", dir="/tmp"))
    db = directory / "wh.duckdb"
    _make_warehouse(db)
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", directory / ".write.lock")
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    store.warehouse_identity_cache_clear()
    coverage.coverage_cache_clear()
    yield directory
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    store.warehouse_identity_cache_clear()
    coverage.coverage_cache_clear()
    shutil.rmtree(directory, ignore_errors=True)

def _read_view_rows(view: Path) -> list:
    con = store.connect_to(view, read_only=True)
    try:
        return sorted(
            row[0] for row in con.execute("SELECT x FROM t").fetchall())
    finally:
        con.close()

def test_capability_reads_open_read_only(scratch, monkeypatch):
    modes: list = []
    real_connect = duckdb.connect

    def spy(*args, **kwargs):
        modes.append(kwargs.get("read_only"))
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", spy)
    assert store.tables() == {"t", "fetch_log"}
    assert store.read_frame("t").height == 2
    assert store.read_frame_optional("absent_table").height == 0
    rows = store._read_df("SELECT x FROM t ORDER BY x", [])
    assert [row["x"] for row in rows] == [1, 2]
    assert store.last_fetch("t", "2024-25") == _FETCHED_AT
    assert store.seasons_with_data(table="t") == ["2024-25"]
    assert coverage.warehouse_tables() == {"t", "fetch_log"}
    assert coverage.table_seasons("t") == frozenset({"2024-25"})
    verdict = coverage.coverage_check("PTS", "2024-25", table="t")
    assert verdict["covered"] is True
    envelope = adapter_core.build_envelope(
        CAPABILITIES["team_totals"],
        {"season": "2024-25"},
        {"tool": "get_team_leaders", "ok": True,
         "rows": [{"TEAM_ID": 1, "TOTAL": 5}],
         "meta": {"source": "warehouse", "season": "2024-25"}})
    assert envelope.source_identity is not None
    assert envelope.source_identity.kind == "warehouse"
    assert modes
    assert all(mode is True for mode in modes)

def test_parallel_runs_isolated_and_write_conflict_loud(scratch):
    import subprocess
    first = store.snapshot_warehouse(scratch / "run-a.duckdb")
    second = store.snapshot_warehouse(scratch / "run-b.duckdb")
    owned = store.snapshot_warehouse(scratch / "run-w.duckdb")
    assert _read_view_rows(first) == [1, 2]
    assert _read_view_rows(second) == [1, 2]
    writer = store.connect_to(owned, read_only=False)
    try:
        writer.execute("BEGIN TRANSACTION")
        writer.execute(
            "INSERT INTO t VALUES ('0022400099', '2024-25', 99)")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda view: [_read_view_rows(view) for _ in range(5)],
                [first, second]))
        for seen_runs in results:
            for seen in seen_runs:
                assert seen == [1, 2]
        child = (
            "import sys; sys.path.insert(0, "
            f"{str(Path(__file__).resolve().parent.parent)!r}); "
            "from shared import store; "
            f"store.connect_to({str(owned)!r}, read_only=False)")
        start = time.monotonic()
        proc = subprocess.run(
            [sys.executable, "-c", child],
            capture_output=True, text=True, timeout=60)
        elapsed = time.monotonic() - start
        assert proc.returncode != 0
        assert "WriteConflictError" in proc.stderr
        assert elapsed < 10.0
    finally:
        try:
            writer.execute("ROLLBACK")
        except Exception:
            pass
        writer.close()
    assert _read_view_rows(owned) == [1, 2]
    assert _read_view_rows(first) == [1, 2]
    assert _read_view_rows(second) == [1, 2]

def test_coverage_freshness_discriminates_same_size_same_mtime():
    directory = Path(tempfile.mkdtemp(prefix="whfresh_", dir="/tmp"))
    try:
        size = 20000
        same_ns = 1700000000000000000
        first = directory / "a.bin"
        second = directory / "b.bin"
        first.write_bytes(b"A" * size)
        second.write_bytes(
            b"A" * (size // 2) + b"B" + b"A" * (size - size // 2 - 1))
        os.utime(first, ns=(same_ns, same_ns))
        os.utime(second, ns=(same_ns, same_ns))
        assert first.stat().st_size == second.stat().st_size == size
        assert first.stat().st_mtime_ns == second.stat().st_mtime_ns
        assert coverage._freshness(first) is not None
        assert (coverage._freshness(first)
                != coverage._freshness(second))
    finally:
        shutil.rmtree(directory, ignore_errors=True)

def _make_warehouse_with_season(db: Path, season: str) -> None:
    con = duckdb.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE t(GAME_ID VARCHAR, _season VARCHAR, x INTEGER)")
        con.execute(
            "INSERT INTO t VALUES "
            f"('0022400001', '{season}', 1), "
            f"('0022400002', '{season}', 2)")
        con.execute(
            "CREATE TABLE fetch_log(dataset VARCHAR, season VARCHAR, "
            "entity VARCHAR, source VARCHAR, fetched_at VARCHAR, "
            "rows INTEGER)")
        con.execute(
            "INSERT INTO fetch_log VALUES "
            f"('t', '{season}', '', 'test', '{_FETCHED_AT}', 2)")
        con.execute("CHECKPOINT")
    finally:
        con.close()

def test_coverage_cache_keyed_on_content_identity(scratch):
    db = store.DB_PATH
    assert coverage.warehouse_tables() == {"t", "fetch_log"}
    assert coverage.table_seasons("t") == frozenset({"2024-25"})
    before = db.stat()
    other = scratch / "other.duckdb"
    _make_warehouse_with_season(other, "2025-26")
    assert other.stat().st_size == before.st_size
    os.replace(other, db)
    os.utime(db, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert db.stat().st_mtime_ns == before.st_mtime_ns
    assert db.stat().st_size == before.st_size
    assert coverage.warehouse_tables() == {"t", "fetch_log"}
    assert coverage.table_seasons("t") == frozenset({"2025-26"})
