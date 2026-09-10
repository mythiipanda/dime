"""Seed silver_on_off for every rotation player (full league, 2025-26).

Uses pbpstats get-on-off (gentle: one call at a time + sleeps).
Rotation cutoff: MIN >= 900 total minutes in silver_leaders_pts (~11 mpg over 82).
Idempotent: skips already-seeded entities; save_frame replaces per entity/season.

Usage: python3 scripts/seed_on_off_league.py (run from backend/)
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store
from app.sources import pbpstats

SEASON = "2025-26"
MIN_MINUTES = 900
SLEEP = 1.5
BACKOFF_AFTER_CONSEC_FAILS = 5
BACKOFF_SLEEP = 120
ABORT_AFTER_TOTAL_FAILS = 60


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--limit", type=int, default=0,
                      help="max players to seed this run (0 = all)")
    ns = args.parse_args()

    con = store.connect()
    try:
        seeded = {r[0] for r in con.execute(
            "SELECT DISTINCT _entity FROM silver_on_off").fetchall()}
        players = con.execute(
            "SELECT PLAYER_ID, PLAYER, TEAM_ID FROM silver_leaders_pts "
            "WHERE _season = ? AND MIN >= ? ORDER BY MIN DESC",
            [SEASON, MIN_MINUTES]).fetchall()
    finally:
        con.close()

    todo = [(pid, name, tid) for pid, name, tid in players
            if f"player:{pid}" not in seeded and tid]
    print(f"seeded: {len(seeded)}, rotation pool: {len(players)}, todo: {len(todo)}",
          flush=True)

    done = fails = consec = 0
    for pid, name, tid in todo:
        if ns.limit and done + fails >= ns.limit:
            print(f"  batch limit {ns.limit} reached", flush=True)
            break
        ent = f"player:{pid}"
        try:
            res = pbpstats.on_off(int(pid), int(tid), SEASON)
            ok = res is not None and res.ok and res.frame.height > 0
        except Exception as e:
            ok = False
            print(f"  {name}: error {str(e)[:60]}", flush=True)
        if ok:
            try:
                n = store.save_frame("silver_on_off", res, entity=ent)
                done += 1
                consec = 0
                print(f"  {name} ({tid}): {n} rows", flush=True)
            except Exception as e:
                ok = False
                print(f"  {name}: save failed {str(e)[:60]}", flush=True)
        if not ok:
            fails += 1
            consec += 1
        time.sleep(SLEEP)
        if consec >= BACKOFF_AFTER_CONSEC_FAILS:
            print(f"  backing off ({BACKOFF_SLEEP}s) after {consec} consecutive failures",
                  flush=True)
            time.sleep(BACKOFF_SLEEP)
            consec = 0
        if fails >= ABORT_AFTER_TOTAL_FAILS:
            print(f"  aborting: {fails} total failures", flush=True)
            break
    print(f"on_off league seed: {done} new players, {fails} failures", flush=True)


if __name__ == "__main__":
    main()
