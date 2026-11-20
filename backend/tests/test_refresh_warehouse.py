import subprocess
import sys
import time
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import refresh_warehouse as rw


def _make_db(path: Path, tables: dict[str, int]) -> Path:
    con = duckdb.connect(str(path))
    for name, n in tables.items():
        con.execute(f'CREATE TABLE "{name}" AS '
                    f"SELECT * FROM range({n})")
    con.close()
    return path


def test_snapshot_counts(tmp_path):
    db = _make_db(tmp_path / "w.duckdb", {"a": 3, "b": 7})
    assert rw.snapshot_counts(db) == {"a": 3, "b": 7}


def test_check_counts_pass_on_growth(tmp_path):
    ok, problems = rw.check_counts({"a": 3}, {"a": 5, "new": 2}, False)
    assert ok and problems == []


def test_check_counts_equal_ok(tmp_path):
    ok, _ = rw.check_counts({"a": 3}, {"a": 3}, False)
    assert ok


def test_check_counts_shrink_fails(tmp_path):
    ok, problems = rw.check_counts({"a": 5}, {"a": 2}, False)
    assert not ok
    assert any("shrank" in p for p in problems)


def test_check_counts_shrink_allowed(tmp_path):
    ok, _ = rw.check_counts({"a": 5}, {"a": 2}, True)
    assert ok


def test_check_counts_dropped_table_fails(tmp_path):
    ok, problems = rw.check_counts({"a": 5, "b": 1}, {"a": 5}, False)
    assert not ok
    assert any("dropped" in p for p in problems)


def test_rollback_copy(tmp_path):
    backup = _make_db(tmp_path / "bak.duckdb", {"a": 1})
    target = _make_db(tmp_path / "w.duckdb", {"a": 9})
    rw.rollback_copy(target, backup)
    assert rw.snapshot_counts(target) == {"a": 1}


def test_dry_run_end_to_end(tmp_path, monkeypatch, capsys):
    local = _make_db(tmp_path / "local.duckdb", {"t": 4})
    monkeypatch.setattr(rw, "LOCAL_WAREHOUSE", local)
    work = tmp_path / "work"
    rc = rw.main(["--from-local", "--skip-seed", "--dry-run",
                  "--work-dir", str(work)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert '"dry_run": true' in out
    assert (work / "warehouse.rollback.duckdb").exists()


def test_failed_seeder_rolls_back(tmp_path, monkeypatch):
    local = _make_db(tmp_path / "local.duckdb", {"t": 4})
    monkeypatch.setattr(rw, "LOCAL_WAREHOUSE", local)
    monkeypatch.setattr(rw, "run_seeders",
                        lambda *a, **k: ["fake_seeder"])
    work = tmp_path / "work"
    rc = rw.main(["--from-local", "--dry-run",
                  "--work-dir", str(work)])
    assert rc == 3
    assert rw.snapshot_counts(work / "warehouse.duckdb") == {"t": 4}


def _stub_hub(monkeypatch, download):
    import types
    fake = types.SimpleNamespace(hf_hub_download=download)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake)


def test_pull_warehouse_pins_remote_main_revision(tmp_path, monkeypatch):
    seen = {}

    def fake_download(**kw):
        seen.update(kw)
        snap = tmp_path / "hub" / "snapshots" / "abc123"
        snap.mkdir(parents=True)
        (snap / "warehouse.duckdb").write_bytes(b"fresh")
        return str(snap / "warehouse.duckdb")

    _stub_hub(monkeypatch, fake_download)
    monkeypatch.setattr(rw, "_remote_head_sha", lambda d, t: "abc123")
    work = tmp_path / "work"
    work.mkdir()
    out = rw.pull_warehouse("org/ds", work, None)
    assert seen["revision"] == "abc123"
    assert (work / "warehouse.duckdb").read_bytes() == b"fresh"
    assert out == work / "warehouse.duckdb"


def test_pull_warehouse_rejects_stale_snapshot(tmp_path, monkeypatch):
    snap = tmp_path / "hub" / "snapshots" / "oldsha"
    snap.mkdir(parents=True)
    (snap / "warehouse.duckdb").write_bytes(b"stale")
    _stub_hub(monkeypatch,
              lambda **kw: str(snap / "warehouse.duckdb"))
    monkeypatch.setattr(rw, "_remote_head_sha", lambda d, t: "newsha")
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(RuntimeError, match="stale snapshot"):
        rw.pull_warehouse("org/ds", work, None)
    assert not (work / "warehouse.duckdb").exists()


def test_pull_warehouse_skips_check_when_remote_unknown(tmp_path, monkeypatch):
    snap = tmp_path / "hub" / "snapshots" / "anysha"
    snap.mkdir(parents=True)
    (snap / "warehouse.duckdb").write_bytes(b"data")
    _stub_hub(monkeypatch,
              lambda **kw: str(snap / "warehouse.duckdb"))
    monkeypatch.setattr(rw, "_remote_head_sha", lambda d, t: None)
    work = tmp_path / "work"
    work.mkdir()
    out = rw.pull_warehouse("org/ds", work, None)
    assert out.read_bytes() == b"data"


def test_ensure_writable_clears_stale_write_lock(tmp_path):
    wh = _make_db(tmp_path / "warehouse.duckdb", {"t": 1})
    lock = tmp_path / ".write.lock"
    lock.write_text(str(2 ** 23 - 1))
    rw.ensure_writable_workdir(tmp_path, wh)
    assert not lock.exists()


def test_ensure_writable_refuses_live_lock_holder(tmp_path):
    from shared import file_lock
    wh = _make_db(tmp_path / "warehouse.duckdb", {"t": 1})
    lock = tmp_path / ".write.lock"
    lock.write_text("4242")
    fh = open(lock, "r+")
    try:
        file_lock.try_lock_exclusive(fh)
        with pytest.raises(RuntimeError, match="live process"):
            rw.ensure_writable_workdir(tmp_path, wh)
    finally:
        file_lock.unlock(fh)
        fh.close()


def test_ensure_writable_refuses_duckdb_write_lock(tmp_path):
    wh = _make_db(tmp_path / "warehouse.duckdb", {"t": 1})
    holder = subprocess.Popen(
        [sys.executable, "-c",
         "import duckdb, time, sys\n"
         f"con = duckdb.connect({str(wh)!r})\n"
         "print('held', flush=True)\n"
         "time.sleep(30)\n"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        time.sleep(0.3)
        with pytest.raises(RuntimeError, match="not writable|write-locked"):
            rw.ensure_writable_workdir(tmp_path, wh)
    finally:
        holder.kill()
        holder.wait()
