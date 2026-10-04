#!/usr/bin/env python3
import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources import nba_stats

PT_STATS_TABLE = "silver_tracking_pt_stats"
PT_DEFEND_TABLE = "silver_tracking_pt_defend"
PT_SHOT_TABLE = "silver_tracking_pt_shot"

FAIL_ROWS = -1
MAX_ATTEMPTS = 3
BACKOFF_S = 2.0


@dataclass
class Unit:
    kind: str
    season: str
    scope: str
    label: str


def unit_table(unit: Unit) -> str:
    if unit.kind == "pt_stats":
        return PT_STATS_TABLE
    if unit.kind == "pt_defend":
        return PT_DEFEND_TABLE
    return PT_SHOT_TABLE


def unit_entity(unit: Unit) -> str:
    if unit.kind == "pt_stats":
        return f"ptstats:{unit.scope}:{unit.label}"
    if unit.kind == "pt_defend":
        return f"ptdefend:{unit.label}"
    return "ptshot:overall"


def planned_units(seasons: list[str]) -> list[Unit]:
    units: list[Unit] = []
    for season in seasons:
        for scope in nba_stats.PT_SCOPES:
            for measure in nba_stats.PT_MEASURE_TYPES:
                units.append(Unit("pt_stats", season, scope, measure))
        for category in nba_stats.PT_DEFEND_CATEGORIES:
            units.append(Unit("pt_defend", season, "", category))
        units.append(Unit("pt_shot", season, "", "overall"))
    return units


def fetch(unit: Unit):
    if unit.kind == "pt_stats":
        return nba_stats.pt_stats(unit.scope, unit.label, unit.season)
    if unit.kind == "pt_defend":
        return nba_stats.pt_defend(unit.label, unit.season)
    return nba_stats.pt_shot(unit.season)


def unit_complete(table: str, season: str, entity: str) -> bool:
    try:
        con = store.connect(read_only=True)
    except Exception:
        return False
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "fetch_log" not in tables:
            return False
        row = con.execute(
            """SELECT rows FROM fetch_log
            WHERE dataset = ? AND season = ? AND entity = ?
            ORDER BY fetched_at DESC LIMIT 1""",
            [table, season, entity],
        ).fetchone()
    except Exception:
        return False
    finally:
        try:
            con.close()
        except Exception:
            pass
    return row is not None and row[0] is not None and int(row[0]) >= 0


def record_failure(table: str, season: str, entity: str) -> None:
    from datetime import datetime, timezone

    fetched_at = datetime.now(timezone.utc).isoformat()
    con = store.connect(read_only=False)
    try:
        with store.write_guard():
            con.execute("BEGIN TRANSACTION")
            try:
                con.execute(
                    "INSERT INTO fetch_log VALUES (?,?,?,?,?,?)",
                    [table, season, entity, "nba_api", fetched_at, FAIL_ROWS],
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


def run_unit(unit: Unit) -> bool:
    table = unit_table(unit)
    entity = unit_entity(unit)
    last = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            res = fetch(unit)
            if res.ok and res.frame.height > 0:
                store.write_unit(table, res.frame, unit.season,
                                 res.meta.source, entity,
                                 "_season = ? AND _entity = ?",
                                 [unit.season, entity])
                print(f"saved {table} {unit.season} {entity} rows={res.frame.height}",
                      flush=True)
                return True
            last = res.error or "empty upstream response"
        except Exception as exc:
            last = str(exc)
        if attempt < MAX_ATTEMPTS:
            time.sleep(BACKOFF_S * attempt)
    record_failure(table, unit.season, entity)
    print(f"failed {table} {unit.season} {entity}: {last}", flush=True)
    return False


def resolve_target(scratch_db: str) -> Path | None:
    raw = scratch_db or os.environ.get("DIME_WAREHOUSE", "")
    if not raw:
        print("refusing: DIME_WAREHOUSE is not set")
        return None
    target = Path(raw).expanduser().resolve()
    print(f"target: {target}")
    if target == store.CANONICAL_DB_PATH:
        print("refusing: target is the canonical warehouse")
        return None
    return target


def table_count(table: str) -> int:
    try:
        con = store.connect(read_only=True)
    except Exception:
        return 0
    try:
        if table not in store.tables():
            return 0
        row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0
    finally:
        try:
            con.close()
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2024-25,2025-26")
    ap.add_argument("--scratch-db", default="")
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
    try:
        return _run(args, target)
    finally:
        store.DB_PATH, store.LOCK_PATH = prior_db_path, prior_lock_path


def _run(args, target) -> int:
    seasons = [s.strip() for s in str(args.seasons).split(",") if s.strip()]
    units = planned_units(seasons)
    if args.limit_units and args.limit_units > 0:
        units = units[:args.limit_units]
    if args.dry_run:
        for unit in units:
            print(f"{unit_table(unit)} {unit.season} {unit_entity(unit)}")
        print(f"units: {len(units)}")
        return 0
    failed = 0
    done = 0
    for unit in units:
        table = unit_table(unit)
        entity = unit_entity(unit)
        if unit_complete(table, unit.season, entity):
            print(f"skip {table} {unit.season} {entity}", flush=True)
            done += 1
            continue
        if run_unit(unit):
            done += 1
        else:
            failed += 1
    for table in (PT_STATS_TABLE, PT_DEFEND_TABLE, PT_SHOT_TABLE):
        print(f"{table}: {table_count(table)} rows")
    print(f"done units={done} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
