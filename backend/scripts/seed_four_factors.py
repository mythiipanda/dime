import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb

TABLE = "silver_four_factors"
WEEK_SECONDS = 7 * 24 * 3600


def parse_four_factor_frame(frame, season: str, fetched_at: str, entity: str):
    if frame is None or frame.height == 0:
        return None
    rows = frame.iter_rows(named=True)
    offense, defense = [], []
    minutes_on = 0
    minutes_off = 0
    side_key = None
    cols = set(frame.columns)
    for key in ("side", "Side", "type", "Type"):
        if key in cols:
            side_key = key
            break
    stat_key = next((k for k in ("stat", "Stat", "name") if k in cols), None)
    if stat_key is None:
        return None
    on_key = next((k for k in cols if k.lower() == "on"), None)
    off_key = next((k for k in cols if k.lower() == "off"), None)
    for row in rows:
        stat = str(row.get(stat_key) or "")
        if not stat:
            continue
        low = stat.lower()
        if "min" in low or "poss" in low:
            try:
                minutes_on = int(float(row.get(on_key) or 0)) if on_key else minutes_on
                minutes_off = int(float(row.get(off_key) or 0)) if off_key else minutes_off
            except (TypeError, ValueError):
                pass
            continue
        def _f(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0
        entry = {"On": _f(row.get(on_key)), "Off": _f(row.get(off_key)), "stat": stat}
        side = str(row.get(side_key) or "").lower() if side_key else ""
        if "def" in side:
            defense.append(entry)
        elif "off" in side or "offense" in side:
            offense.append(entry)
        elif stat in ("DReb%", "DRB%"):
            defense.append(entry)
        else:
            offense.append(entry)
    if not offense and not defense:
        return None
    return (offense, defense, minutes_on, minutes_off, "pbpstats", season,
            fetched_at, entity)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2026-27")
    ap.add_argument("--warehouse", default=str(Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args(argv)

    from shared.sources.pbpstats import four_factors

    con = duckdb.connect(args.warehouse)
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if TABLE not in tables:
        print(f"{TABLE} missing from warehouse"); return 1
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
            "SELECT DISTINCT _entity, CAST(_fetched_at AS TIMESTAMP) FROM silver_four_factors WHERE _season = ?",
            [args.season]).fetchall()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for entity, ts in rows:
            if args.force or ts is None or (now - ts).total_seconds() > WEEK_SECONDS:
                continue
            have.add(entity)
    except Exception:
        pass
    todo = [(int(p), int(t)) for p, t in pairs if f"player:{int(p)}" not in have]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(pairs)} player-team pairs ({pair_source}), {len(have)} fresh this week, fetching {len(todo)}")
    if args.dry_run and not args.apply:
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
            res = four_factors(pid, tid, args.season)
        except Exception:
            return pid, None
        frame = getattr(res, "frame", None)
        return pid, parse_four_factor_frame(frame, args.season, fetched_at, f"player:{pid}")

    if args.apply:
        done = 0
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            for pid, parsed in pool.map(fetch, todo):
                done += 1
                if parsed is None:
                    fail += 1
                else:
                    con.execute("DELETE FROM silver_four_factors WHERE _season = ? AND _entity = ?",
                                [args.season, f"player:{pid}"])
                    con.execute("INSERT INTO silver_four_factors VALUES (?,?,?,?,?,?,?,?)",
                                list(parsed))
                    ins += 1
                if done % 50 == 0:
                    print(f"  {done}/{len(todo)} fetched, {ins} written, {fail} empty/failed")
        con.execute("CHECKPOINT")
        print(f"done: {ins} players written, {fail} empty/failed — applied + checkpointed")
    else:
        print("dry-run rolled back (pass --apply to write)")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
