import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources import nba_stats

TABLE = "silver_playtypes"
FAIL_ROWS = -1
KIND_SCOPE = {"player": "P", "team": "T"}
SIDE_GROUPING = {"offense": "offensive", "defense": "defensive"}
REQUIRED_COLUMNS = set(nba_stats.PLAYTYPE_SCHEMA)


def planned_units(seasons):
    units = []
    for season in seasons:
        for kind in ("player", "team"):
            for side in ("offense", "defense"):
                units.append((season, kind, side))
    return units


def unit_entity(kind, side):
    return f"league:{kind}:{side}"


def unit_complete(season, kind, side):
    entity = unit_entity(kind, side)
    try:
        con = store.connect(read_only=True)
    except Exception:
        return False
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "fetch_log" not in tables:
            return False
        row = con.execute(
            "SELECT rows FROM fetch_log WHERE dataset = ? AND season = ? "
            "AND entity = ? ORDER BY fetched_at DESC LIMIT 1",
            [TABLE, season, entity],
        ).fetchone()
    except Exception:
        return False
    finally:
        try:
            con.close()
        except Exception:
            pass
    return row is not None and row[0] is not None and int(row[0]) >= 0


def record_failure(season, kind, side):
    from datetime import datetime, timezone

    fetched_at = datetime.now(timezone.utc).isoformat()
    con = store.connect(read_only=False)
    try:
        with store.write_guard():
            con.execute("BEGIN TRANSACTION")
            try:
                con.execute(
                    "INSERT INTO fetch_log VALUES (?,?,?,?,?,?)",
                    [TABLE, season, unit_entity(kind, side), "nba_api",
                     fetched_at, FAIL_ROWS],
                )
                con.execute("COMMIT")
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except Exception:
                    pass
                raise
    finally:
        con.close()


def run_unit(unit, fetch_fn=None):
    season, kind, side = unit
    entity = unit_entity(kind, side)
    last = ""
    try:
        fetch = fetch_fn or nba_stats.synergy_playtypes
        res = fetch(season, KIND_SCOPE[kind], SIDE_GROUPING[side])
        if res.ok and res.frame.height > 0:
            missing = REQUIRED_COLUMNS - set(res.frame.columns)
            if missing:
                raise ValueError("missing columns: " + ",".join(sorted(missing)))
            store.write_unit(
                TABLE, res.frame, season, res.meta.source, entity,
                "_season = ? AND _entity = ?", [season, entity])
            print(f"saved {TABLE} {season} {entity} rows={res.frame.height}",
                  flush=True)
            return True
        last = res.error or "empty upstream response"
    except Exception as exc:
        last = str(exc)
    record_failure(season, kind, side)
    print(f"failed {TABLE} {season} {entity}: {last}", flush=True)
    return False


def resolve_target(raw_db):
    raw = raw_db or os.environ.get("DIME_WAREHOUSE", "")
    if not raw:
        print("refusing: DIME_WAREHOUSE is not set")
        return None
    target = Path(raw).expanduser().resolve()
    print(f"target: {target}")
    if target == store.CANONICAL_DB_PATH:
        print("refusing: target is the canonical warehouse")
        return None
    return target


def table_count():
    try:
        con = store.connect(read_only=True)
    except Exception:
        return 0
    try:
        if TABLE not in store.tables():
            return 0
        row = con.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0
    finally:
        try:
            con.close()
        except Exception:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2024-25,2025-26")
    ap.add_argument("--scratch-db", default="")
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--limit-units", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    target = resolve_target(args.scratch_db)
    if target is None:
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    prior_db_path, prior_lock_path = store.DB_PATH, store.LOCK_PATH
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    try:
        seasons = [s.strip() for s in str(args.seasons).split(",") if s.strip()]
        units = planned_units(seasons)
        if args.limit_units and args.limit_units > 0:
            units = units[: args.limit_units]
        if args.dry_run:
            for unit in units:
                print(f"{TABLE} {unit[0]} {unit_entity(unit[1], unit[2])}")
            print(f"units: {len(units)}")
            return 0
        done = skipped = failed = 0
        for index, unit in enumerate(units):
            if unit_complete(*unit):
                print(f"skip {TABLE} {unit[0]} {unit_entity(unit[1], unit[2])}",
                      flush=True)
                skipped += 1
                continue
            if run_unit(unit):
                done += 1
            else:
                failed += 1
            if index + 1 < len(units):
                time.sleep(max(0.0, args.sleep))
        print(f"{TABLE}: {table_count()} rows")
        print(f"done units={done} skipped={skipped} failed={failed}")
        return 1 if failed else 0
    finally:
        store.DB_PATH, store.LOCK_PATH = prior_db_path, prior_lock_path
        store.warehouse_tables_cache_clear()
        store.warehouse_pool_clear()


if __name__ == "__main__":
    raise SystemExit(main())
