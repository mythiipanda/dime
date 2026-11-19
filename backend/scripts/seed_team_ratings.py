import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources import nba_stats

TABLE = "silver_team_ratings"
ENTITY = "teamratings:overall"

FAIL_ROWS = -1
MAX_ATTEMPTS = 3
BACKOFF_S = 2.0
SEASONS = [f"{start}-{str(start + 1)[-2:]}" for start in range(2015, 2025)]

def fetch(season: str):
    return nba_stats.team_ratings(season)

def unit_complete(season: str) -> bool:
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
            [TABLE, season, ENTITY],
        ).fetchone()
    except Exception:
        return False
    finally:
        try:
            con.close()
        except Exception:
            pass
    return row is not None and row[0] is not None and int(row[0]) >= 0

def record_failure(season: str) -> None:
    from datetime import datetime, timezone

    fetched_at = datetime.now(timezone.utc).isoformat()
    con = store.connect(read_only=False)
    try:
        with store.write_guard():
            con.execute("BEGIN TRANSACTION")
            try:
                con.execute(
                    "INSERT INTO fetch_log VALUES (?,?,?,?,?,?)",
                    [TABLE, season, ENTITY, "nba_api", fetched_at, FAIL_ROWS],
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

def run_unit(season: str) -> bool:
    last = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            res = fetch(season)
            if res.ok and res.frame.height > 0:
                store.write_unit(TABLE, res.frame, season,
                                 res.meta.source, ENTITY,
                                 "_season = ? AND _entity = ?",
                                 [season, ENTITY])
                print(f"saved {TABLE} {season} rows={res.frame.height}",
                      flush=True)
                return True
            last = res.error or "empty upstream response"
        except Exception as exc:
            last = str(exc)
        if attempt < MAX_ATTEMPTS:
            time.sleep(BACKOFF_S * attempt)
    record_failure(season)
    print(f"failed {TABLE} {season}: {last}", flush=True)
    return False

DEV_ENVS = frozenset({"dev", "local", "test"})

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
    env = (os.environ.get("DIME_ENV") or "").strip().lower()
    if env not in DEV_ENVS and not scratch_db:
        print("refusing: set DIME_ENV=dev or pass --scratch-db")
        return None
    return target

def table_count(season: str) -> int:
    try:
        con = store.connect(read_only=True)
    except Exception:
        return 0
    try:
        if TABLE not in store.tables():
            return 0
        row = con.execute(
            f"SELECT COUNT(*) FROM {TABLE} WHERE _season = ?",
            [season],
        ).fetchone()
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
    ap.add_argument("--seasons", default=",".join(SEASONS))
    ap.add_argument("--scratch-db", default="")
    ap.add_argument("--limit-units", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("positional", nargs="*")
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

def _run(args, target: Path) -> int:
    if args.positional:
        seasons = [s.strip() for s in args.positional if s.strip()]
    else:
        seasons = [s.strip() for s in str(args.seasons).split(",")
                   if s.strip()]
    if args.limit_units and args.limit_units > 0:
        seasons = seasons[:args.limit_units]
    if args.dry_run:
        for season in seasons:
            print(f"{TABLE} {season} {ENTITY}")
        print(f"units: {len(seasons)}")
        return 0
    failed = 0
    done = 0
    for season in seasons:
        if unit_complete(season):
            print(f"skip {TABLE} {season} {ENTITY}", flush=True)
            done += 1
            continue
        if run_unit(season):
            done += 1
        else:
            failed += 1
    for season in seasons:
        print(f"{TABLE} {season}: {table_count(season)} rows")
    print(f"done units={done} failed={failed}")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
