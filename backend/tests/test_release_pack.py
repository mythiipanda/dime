import importlib.util
import fcntl
import hashlib
import json
import subprocess
import sys
import shutil
import time
import zipfile
from pathlib import Path

import duckdb

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release_pack.py"


def _load():
    spec = importlib.util.spec_from_file_location("release_pack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_db(path, rows):
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE t1 (id INTEGER)")
    for i in range(rows):
        con.execute("INSERT INTO t1 VALUES (?)", [i])
    con.execute("CHECKPOINT")
    con.close()


def test_sample_digest_stable_and_hex(tmp_path):
    rp = _load()
    db = tmp_path / "a.duckdb"
    _make_db(db, 3)
    first = rp.sample_digest(db)
    second = rp.sample_digest(db)
    assert first == second
    assert len(first) == 64
    int(first, 16)


def test_sample_digest_changes_on_append(tmp_path):
    rp = _load()
    db = tmp_path / "a.duckdb"
    _make_db(db, 3)
    before = rp.sample_digest(db)
    con = duckdb.connect(str(db))
    con.execute("INSERT INTO t1 VALUES (99)")
    con.execute("CHECKPOINT")
    con.close()
    assert rp.sample_digest(db) != before


def test_sample_digest_tiny_file(tmp_path):
    rp = _load()
    tiny = tmp_path / "tiny.bin"
    tiny.write_bytes(b"abc")
    digest = rp.sample_digest(tiny)
    assert len(digest) == 64
    int(digest, 16)


def test_fingerprint_db_reports_tables_and_counts(tmp_path):
    rp = _load()
    db = tmp_path / "a.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE t1 (id INTEGER)")
    con.execute("CREATE TABLE t2 (name VARCHAR)")
    con.execute("INSERT INTO t1 VALUES (1), (2), (3)")
    con.execute("INSERT INTO t1 VALUES (4)")
    con.execute("INSERT INTO t2 VALUES ('x')")
    con.execute("CHECKPOINT")
    con.close()
    fp = rp.fingerprint_db(db)
    assert fp["tables"] == {"t1": 4, "t2": 1}
    assert fp["size"] == db.stat().st_size
    assert len(fp["sample"]) == 64


def test_fingerprint_db_copy_matches(tmp_path):
    rp = _load()
    src = tmp_path / "a.duckdb"
    dst = tmp_path / "b.duckdb"
    _make_db(src, 5)
    shutil.copyfile(src, dst)
    assert rp.fingerprint_db(src) == rp.fingerprint_db(dst)


def test_compare_identical_copies_no_drift(tmp_path):
    rp = _load()
    src = tmp_path / "a.duckdb"
    dst = tmp_path / "b.duckdb"
    _make_db(src, 5)
    shutil.copyfile(src, dst)
    changed = rp.compare_fingerprints(rp.fingerprint_db(src), rp.fingerprint_db(dst))
    assert changed == []
    assert rp.fingerprints_drift(rp.fingerprint_db(src), rp.fingerprint_db(dst)) is False


def test_compare_one_row_diff_detected(tmp_path):
    rp = _load()
    src = tmp_path / "a.duckdb"
    dst = tmp_path / "b.duckdb"
    _make_db(src, 5)
    shutil.copyfile(src, dst)
    con = duckdb.connect(str(dst))
    con.execute("INSERT INTO t1 VALUES (99)")
    con.execute("CHECKPOINT")
    con.close()
    changed = rp.compare_fingerprints(rp.fingerprint_db(src), rp.fingerprint_db(dst))
    assert changed == ["t1"]
    assert rp.fingerprints_drift(rp.fingerprint_db(src), rp.fingerprint_db(dst)) is True


def test_compare_added_table_detected(tmp_path):
    rp = _load()
    src = tmp_path / "a.duckdb"
    dst = tmp_path / "b.duckdb"
    _make_db(src, 5)
    shutil.copyfile(src, dst)
    con = duckdb.connect(str(dst))
    con.execute("CREATE TABLE t2 (id INTEGER)")
    con.execute("CHECKPOINT")
    con.close()
    changed = rp.compare_fingerprints(rp.fingerprint_db(src), rp.fingerprint_db(dst))
    assert changed == ["t2"]
    assert rp.fingerprints_drift(rp.fingerprint_db(src), rp.fingerprint_db(dst)) is True


def test_compare_db_paths_end_to_end(tmp_path):
    rp = _load()
    src = tmp_path / "a.duckdb"
    same = tmp_path / "same.duckdb"
    diff = tmp_path / "diff.duckdb"
    _make_db(src, 4)
    shutil.copyfile(src, same)
    shutil.copyfile(src, diff)
    con = duckdb.connect(str(diff))
    con.execute("DELETE FROM t1 WHERE id = 0")
    con.execute("CHECKPOINT")
    con.close()
    drift_same, changed_same = rp.compare_db(src, same)
    assert drift_same is False
    assert changed_same == []
    drift_diff, changed_diff = rp.compare_db(src, diff)
    assert drift_diff is True
    assert changed_diff == ["t1"]


def _sha_chunked(path):
    h = hashlib.new("sha256")
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_build_pack_layout_and_sha(tmp_path):
    rp = _load()
    src = tmp_path / "warehouse.duckdb"
    _make_db(src, 6)
    dest = tmp_path / "dime_data_test.zip"
    sha = rp.build_pack(src, dest)
    assert sha == _sha_chunked(dest)
    names = zipfile.ZipFile(dest).namelist()
    assert names == ["data/warehouse.duckdb"]
    out = tmp_path / "out"
    out.mkdir()
    zipfile.ZipFile(dest).extractall(out)
    assert rp.fingerprint_db(out / "data" / "warehouse.duckdb") == rp.fingerprint_db(src)


def test_prepare_updates_three_diffs(tmp_path):
    rp = _load()
    tag = "dime-data-20990101"
    zip_name = "dime_data_20990101.zip"
    sha = "0" * 64
    before = {p: p.read_bytes() for p in (rp.FETCH_SH, rp.WORKFLOW_YML, rp.README_MD)}
    diffs = rp.prepare_updates(tag, zip_name, sha)
    assert sorted(diffs) == [".github/workflows/build-backend.yml", "README.md", "scripts/fetch-data.sh"]
    assert tag in diffs["scripts/fetch-data.sh"]
    assert sha in diffs["scripts/fetch-data.sh"]
    assert tag + "/" + zip_name in diffs[".github/workflows/build-backend.yml"]
    assert tag in diffs["README.md"]
    assert "dime-data-20260930" in diffs["scripts/fetch-data.sh"]
    after = {p: p.read_bytes() for p in (rp.FETCH_SH, rp.WORKFLOW_YML, rp.README_MD)}
    assert before == after


def _run_cli(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_cli_no_drift_verdict_schema(tmp_path):
    rp = _load()
    warehouse = tmp_path / "warehouse.duckdb"
    _make_db(warehouse, 3)
    baseline = tmp_path / "dime_data_base.zip"
    rp.build_pack(warehouse, baseline)
    proc = _run_cli(["--warehouse", str(warehouse), "--pack-path", str(baseline)], tmp_path)
    assert proc.returncode == 0
    verdict = json.loads(proc.stdout)
    assert sorted(verdict) == ["drift", "fingerprint", "pack", "pack_path", "released_at", "sha256", "tables_changed"]
    assert verdict["drift"] is False
    assert verdict["tables_changed"] == []
    assert verdict["pack_path"] is None
    assert verdict["sha256"] is None


def test_cli_drift_rebuilds_and_second_run_clean(tmp_path):
    rp = _load()
    stage = tmp_path / "stage"
    stage.mkdir()
    canonical = tmp_path / "warehouse.duckdb"
    _make_db(canonical, 3)
    baseline = stage / "dime_data_base.zip"
    rp.build_pack(canonical, baseline)
    con = duckdb.connect(str(canonical))
    con.execute("INSERT INTO t1 VALUES (7)")
    con.execute("CHECKPOINT")
    con.close()
    proc = _run_cli(
        ["--warehouse", str(canonical), "--pack-path", str(baseline),
         "--stage-dir", str(stage), "--name", "dime_data_t1"],
        tmp_path,
    )
    assert proc.returncode == 0
    verdict = json.loads(proc.stdout)
    assert verdict["drift"] is True
    assert verdict["tables_changed"] == ["t1"]
    staged = Path(verdict["pack_path"])
    assert staged.parent == stage
    assert staged.exists()
    assert verdict["sha256"] == _sha_chunked(staged)
    assert zipfile.ZipFile(staged).namelist() == ["data/warehouse.duckdb"]
    again = _run_cli(
        ["--warehouse", str(canonical), "--pack-path", str(staged), "--stage-dir", str(stage)],
        tmp_path,
    )
    assert again.returncode == 0
    assert json.loads(again.stdout)["drift"] is False


def test_cli_prepare_writes_diffs_without_touching_repo(tmp_path):
    rp = _load()
    stage = tmp_path / "stage"
    stage.mkdir()
    prep = tmp_path / "prep"
    canonical = tmp_path / "warehouse.duckdb"
    _make_db(canonical, 2)
    baseline = stage / "dime_data_base.zip"
    rp.build_pack(canonical, baseline)
    con = duckdb.connect(str(canonical))
    con.execute("INSERT INTO t1 VALUES (8)")
    con.execute("CHECKPOINT")
    con.close()
    before = {p: p.read_bytes() for p in (rp.FETCH_SH, rp.WORKFLOW_YML, rp.README_MD)}
    proc = _run_cli(
        ["--warehouse", str(canonical), "--pack-path", str(baseline),
         "--stage-dir", str(stage), "--name", "dime_data_t2",
         "--prepare", "--prepare-dir", str(prep)],
        tmp_path,
    )
    assert proc.returncode == 0
    verdict = json.loads(proc.stdout)
    assert verdict["drift"] is True
    written = sorted(p.name for p in prep.iterdir())
    assert written == ["README.md.diff", "build-backend.yml.diff", "fetch-data.sh.diff"]
    assert verdict["sha256"] in (prep / "fetch-data.sh.diff").read_text()
    after = {p: p.read_bytes() for p in (rp.FETCH_SH, rp.WORKFLOW_YML, rp.README_MD)}
    assert before == after


def test_cli_flock_single_flight_exits_cleanly(tmp_path):
    lock = tmp_path / "release-pack.lock"
    lock.write_bytes(b"")
    warehouse = tmp_path / "warehouse.duckdb"
    _make_db(warehouse, 1)
    baseline = tmp_path / "dime_data_base.zip"
    rp = _load()
    rp.build_pack(warehouse, baseline)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        proc = _run_cli(
            ["--warehouse", str(warehouse), "--pack-path", str(baseline),
             "--lock-path", str(lock)],
            tmp_path,
        )
        fcntl.flock(fh, fcntl.LOCK_UN)
    assert proc.returncode == 0
    verdict = json.loads(proc.stdout)
    assert verdict["drift"] is False


def test_newest_staged_pack_picks_latest(tmp_path):
    rp = _load()
    stage = tmp_path / "stage"
    stage.mkdir()
    assert rp.newest_staged_pack(stage) is None
    old = stage / "dime_data_old.zip"
    new = stage / "dime_data_new.zip"
    old.write_bytes(b"old")
    time.sleep(0.02)
    new.write_bytes(b"new")
    assert rp.newest_staged_pack(stage) == new
