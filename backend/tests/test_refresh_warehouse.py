import sys
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
