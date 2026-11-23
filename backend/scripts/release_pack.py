import argparse
import datetime
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import file_lock

_SAMPLE_READ_BYTES = 8192
_PACK_MEMBER = "data/warehouse.duckdb"
CANONICAL_WAREHOUSE = Path.home() / "workspace" / "dime-r25-data" / "backend" / "data" / "warehouse-backfill.duckdb"
DEFAULT_STAGE_DIR = Path.home() / "workspace" / "dime-data-release"
VERDICT_KEYS = ["drift", "tables_changed", "pack_path", "sha256", "fingerprint", "pack", "released_at"]

def sample_digest(path):
    path = Path(path)
    size = path.stat().st_size
    h = hashlib.new("sha256")
    h.update(size.to_bytes(8, "little", signed=False))
    with open(path, "rb") as fh:
        for off in (0, size // 2, size - _SAMPLE_READ_BYTES):
            fh.seek(max(off, 0))
            h.update(fh.read(_SAMPLE_READ_BYTES))
    return h.hexdigest()

def fingerprint_db(path):
    path = Path(path)
    con = duckdb.connect(str(path), read_only=True)
    try:
        names = sorted(r[0] for r in con.execute("SHOW TABLES").fetchall())
        tables = {}
        for name in names:
            quoted = name.replace('"', '""')
            tables[name] = con.execute('SELECT COUNT(*) FROM "' + quoted + '"').fetchall()[0][0]
    finally:
        try:
            con.close()
        except Exception:
            pass
    return {"size": path.stat().st_size, "sample": sample_digest(path), "tables": tables}

def compare_fingerprints(warehouse_fp, pack_fp):
    names = set(warehouse_fp["tables"]) | set(pack_fp["tables"])
    return sorted(n for n in names if warehouse_fp["tables"].get(n) != pack_fp["tables"].get(n))

def fingerprints_drift(warehouse_fp, pack_fp):
    if warehouse_fp["sample"] != pack_fp["sample"]:
        return True
    if warehouse_fp["size"] != pack_fp["size"]:
        return True
    return bool(compare_fingerprints(warehouse_fp, pack_fp))

def compare_db(warehouse_path, pack_db_path):
    warehouse_fp = fingerprint_db(warehouse_path)
    pack_fp = fingerprint_db(pack_db_path)
    changed = compare_fingerprints(warehouse_fp, pack_fp)
    drift = fingerprints_drift(warehouse_fp, pack_fp)
    return drift, changed

def sha_file_hexdigest(path):
    h = hashlib.new("sha256")
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def build_pack(warehouse_path, dest_zip):
    warehouse_path = Path(warehouse_path)
    dest_zip = Path(dest_zip)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(warehouse_path, _PACK_MEMBER)
    return sha_file_hexdigest(dest_zip)

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="release_pack.py",
        description="Refresh the staged data pack when the warehouse moves. Compares the warehouse file against the staged pack and rebuilds the pack on drift. Never publishes.",
        epilog="Stdout is always one JSON verdict with keys drift, tables_changed, pack_path, sha256, fingerprint, pack, released_at. Drift is true when table names, row counts, or file bytes differ. Pack_path and sha256 are set only when a new pack is staged. Fingerprint holds warehouse and pack fingerprints with size, sample digest, and per-table counts.",
    )
    parser.add_argument("--warehouse", default=str(CANONICAL_WAREHOUSE),
                        help="Warehouse file to compare from. Opens read only.")
    parser.add_argument("--pack-path", default=None,
                        help="Baseline pack zip to compare against. Defaults to the newest dime_data zip in the stage dir.")
    parser.add_argument("--stage-dir", default=str(DEFAULT_STAGE_DIR),
                        help="Dir where new packs are staged and the default pack is found.")
    parser.add_argument("--name", default=None,
                        help="Stem for the new pack zip. Defaults to dime_data_YYYYMMDD.")
    parser.add_argument("--lock-path", default=None,
                        help="Lock file for single flight. Defaults to a lock file in the stage dir.")
    return parser.parse_args(argv)

def newest_staged_pack(stage_dir):
    zips = [p for p in Path(stage_dir).glob("dime_data*.zip") if p.is_file()]
    if not zips:
        return None
    return max(zips, key=lambda p: p.stat().st_mtime)

def emit_verdict(verdict):
    print(json.dumps(verdict))

def busy_verdict():
    return {
        "drift": False,
        "tables_changed": [],
        "pack_path": None,
        "sha256": None,
        "fingerprint": {},
        "pack": "busy",
        "released_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

def main(argv=None):
    args = parse_args(argv)
    stage_dir = Path(args.stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    if os.environ.get("TMPDIR", "/tmp") == "/tmp":
        os.environ["TMPDIR"] = str(stage_dir)
    lock_path = Path(args.lock_path) if args.lock_path else stage_dir / ".release-pack.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fh = open(lock_path, "w")
    try:
        file_lock.try_lock_exclusive(lock_fh)
    except BlockingIOError:
        emit_verdict(busy_verdict())
        return 0
    except OSError as exc:
        print("release_pack: lock could not be acquired: " + str(exc), file=sys.stderr)
        return 2
    with lock_fh:
        return _run(args, stage_dir)

def _run(args, stage_dir):
    warehouse = Path(args.warehouse)
    if not warehouse.is_file():
        print("release_pack: warehouse file not found: " + str(warehouse), file=sys.stderr)
        return 2
    if args.pack_path:
        baseline = Path(args.pack_path)
    else:
        baseline = newest_staged_pack(stage_dir)
    if baseline is None or not baseline.is_file():
        print("release_pack: no baseline pack found", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(dir=str(stage_dir)) as tmp:
        try:
            with zipfile.ZipFile(baseline) as zf:
                zf.extract(_PACK_MEMBER, path=tmp)
        except KeyError:
            print("release_pack: baseline pack has no " + _PACK_MEMBER, file=sys.stderr)
            return 2
        pack_db = Path(tmp) / _PACK_MEMBER
        warehouse_fp = fingerprint_db(warehouse)
        pack_fp = fingerprint_db(pack_db)
    changed = compare_fingerprints(warehouse_fp, pack_fp)
    drift = fingerprints_drift(warehouse_fp, pack_fp)
    pack_path = None
    sha256 = None
    pack = baseline.stem
    if drift:
        name = args.name or ("dime_data_" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"))
        if name.endswith(".zip"):
            name = name[:-4]
        dest = stage_dir / (name + ".zip")
        sha256 = build_pack(warehouse, dest)
        pack_path = str(dest)
        pack = name.replace("_", "-")
    verdict = {
        "drift": drift,
        "tables_changed": changed,
        "pack_path": pack_path,
        "sha256": sha256,
        "fingerprint": {"warehouse": warehouse_fp, "pack": pack_fp},
        "pack": pack,
        "released_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    emit_verdict(verdict)
    return 0

if __name__ == "__main__":
    sys.exit(main())
