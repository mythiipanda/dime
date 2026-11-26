import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb

TABLE = "silver_wowy"
WEEK_SECONDS = 7 * 24 * 3600


def parse_wowy_frame(frame, player_id: int, season: str, fetched_at: str, entity: str):
    if frame is None or frame.height == 0:
        return None
    cols = set(frame.columns)
    if {"single_row_table_data", "multi_row_table_data", "win_loss_record"} <= cols:
        row = frame.row(0, named=True)
        multi = row.get("multi_row_table_data")
        if not multi:
            return None
        return (row.get("single_row_table_data"), multi, None, "pbpstats", season, fetched_at, entity)
    rows = frame.iter_rows(named=True)
    multi = []
    single = None
    for row in rows:
        clean = {k: v for k, v in row.items()}
        multi.append(clean)
        eid = str(clean.get("EntityId") or clean.get("RowId") or "")
        if single is None and eid == str(player_id):
            single = clean
    if not multi:
        return None
    if single is None:
        for clean in multi:
            eid = str(clean.get("EntityId") or clean.get("RowId") or "")
            if "-" not in eid:
                single = clean
                break
    if single is None:
        single = multi[0]
    return (single, multi, None, "pbpstats", season, fetched_at, entity)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2026-27")
    ap.add_argument("--warehouse", default=str(Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args(argv)

    from shared.sources.pbpstats import wowy

    con = duckdb.connect(args.warehouse)
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if TABLE not in tables:
        print(f"{TABLE} missing from warehouse")
        return 1
    pairs = con.execute(
        "SELECT DISTINCT PLAYER_ID, TEAM_ID FROM silver_boxscores"
        " WHERE _season = ? AND PLAYER_ID IS NOT NULL ORDER BY 1",
        [args.season]).fetchall()
    pair_source = "silver_boxscores"
    if not pairs:
        pairs = con.execute(
            "SELECT DISTINCT ps.PLAYER_ID, m.TEAM_ID FROM silver_player_season ps"
            " JOIN (SELECT DISTINCT teamTricode, TEAM_ID FROM silver_boxscores"
            "       WHERE teamTricode IS NOT NULL) m ON ps.TEAM = m.teamTricode"
            " WHERE ps._season = ? AND ps.PLAYER_ID IS NOT NULL ORDER BY 1",
            [args.season]).fetchall()
        pair_source = "silver_player_season fallback"
    have = set()
    try:
        rows = con.execute(
            "SELECT DISTINCT _entity, CAST(_fetched_at AS TIMESTAMP) FROM silver_wowy WHERE _season = ?",
            [args.season]).fetchall()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for entity, ts in rows:
            if args.force or ts is None or (now - ts).total_seconds() > WEEK_SECONDS:
                continue
            have.add(entity)
    except Exception:
        pass
    todo = [(int(p), int(t)) for p, t in pairs if f"wowy:{int(p)}" not in have]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(pairs)} player-team pairs ({pair_source}), {len(have)} fresh this week, fetching {len(todo)}")
    if args.dry_run:
        for p, t in todo[:5]:
            print(f"  would fetch player:{p} team:{t}")
        if len(todo) > 5:
            print(f"  ... and {len(todo) - 5} more")

    fetched_at = datetime.now(timezone.utc).isoformat()
    ins, fail = 0, 0

    def fetch(pair):
        pid, tid = pair
        time.sleep(args.sleep)
        try:
            res = wowy([pid], tid, args.season)
        except Exception:
            return pid, None
        frame = getattr(res, "frame", None)
        return pid, parse_wowy_frame(frame, pid, args.season, fetched_at, f"wowy:{pid}")

    if not args.dry_run:
        done = 0
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            for pid, parsed in pool.map(fetch, todo):
                done += 1
                if parsed is None:
                    fail += 1
                else:
                    con.execute("DELETE FROM silver_wowy WHERE _season = ? AND _entity = ?",
                                [args.season, f"wowy:{pid}"])
                    con.execute("INSERT INTO silver_wowy VALUES (?,?,?,?,?,?,?)",
                                list(parsed))
                    ins += 1
                if done % 50 == 0:
                    print(f"  {done}/{len(todo)} fetched, {ins} written, {fail} empty/failed")
        con.execute("CHECKPOINT")
        print(f"done: {ins} players written, {fail} empty/failed — applied + checkpointed")
    else:
        print("dry-run rolled back (writes happen without --dry-run)")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
