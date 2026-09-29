import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import concurrent.futures

from shared import store
from shared.sources import nba_stats
from shared.sources.base import FetchResult

SEASON = "2025-26"
TIMEOUT = 30


def _fetch(fn, *args):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn, *args)
        try:
            return fut.result(timeout=TIMEOUT)
        except Exception as e:
            return None


def _seeded_entities(table: str) -> set:
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if table not in tables:
            return set()
        return {r[0] for r in con.execute(
            f"SELECT DISTINCT _entity FROM {table}").fetchall()}
    finally:
        con.close()


def main() -> None:
    print("=== lineups ===", flush=True)
    seeded = _seeded_entities("silver_lineups")
    print(f"already seeded: {len(seeded)}", flush=True)
    try:
        from nba_api.stats.static import teams as _teams
        all_teams = [(t["id"], t["abbreviation"]) for t in _teams.get_teams()]
    except Exception:
        all_teams = []
    done = 0
    for tid, abbrev in all_teams:
        ent = f"team:{tid}"
        if ent in seeded:
            continue
        res = _fetch(nba_stats.lineups, tid, SEASON)
        if res and res.ok and res.frame.height:
            try:
                n = store.save_frame("silver_lineups", res, entity=ent)
                done += 1
                print(f"  {abbrev}: {n} rows", flush=True)
            except Exception as e:
                print(f"  {abbrev}: save failed {e}", flush=True)
        else:
            print(f"  {abbrev}: fetch failed", flush=True)
        time.sleep(1)
    print(f"lineups seeded: {done} new teams", flush=True)

    print("=== gamelogs ===", flush=True)
    seeded = _seeded_entities("silver_player_gamelogs")
    print(f"already seeded: {len(seeded)}", flush=True)
    con = store.connect()
    try:
        players = con.execute(
            "SELECT PLAYER_ID, PLAYER FROM silver_leaders_pts "
            "WHERE _season = ? ORDER BY PTS DESC LIMIT 50",
            [SEASON]).fetchall()
    finally:
        con.close()
    done = 0
    for pid, name in players:
        ent = f"player:{pid}"
        if ent in seeded:
            continue
        res = _fetch(nba_stats.player_gamelog, pid, SEASON)
        if res and res.ok and res.frame.height:
            try:
                n = store.save_frame("silver_player_gamelogs", res, entity=ent)
                done += 1
                print(f"  {name}: {n} rows", flush=True)
            except Exception as e:
                print(f"  {name}: save failed {e}", flush=True)
        else:
            print(f"  {name}: fetch failed", flush=True)
        time.sleep(1)
    print(f"gamelogs seeded: {done} new players", flush=True)

    print("=== on_off ===", flush=True)
    seeded = _seeded_entities("silver_on_off")
    print(f"already seeded: {len(seeded)}", flush=True)
    try:
        from shared.sources import pbpstats
    except ImportError:
        print("pbpstats not available, skipping", flush=True)
        return
    con = store.connect()
    try:
        players = con.execute(
            "SELECT PLAYER_ID, PLAYER, TEAM FROM silver_leaders_pts "
            "WHERE _season = ? ORDER BY MIN DESC LIMIT 30",
            [SEASON]).fetchall()
    finally:
        con.close()
    try:
        from nba_api.stats.static import teams as _teams
        tabbr = {t["abbreviation"]: t["id"] for t in _teams.get_teams()}
    except Exception:
        tabbr = {}
    done = 0
    for pid, name, team in players:
        ent = f"player:{pid}"
        if ent in seeded:
            continue
        tid = tabbr.get(str(team or "").upper())
        if not tid:
            continue
        res = _fetch(pbpstats.on_off, pid, tid, SEASON)
        if res and res.ok and res.frame.height:
            try:
                n = store.save_frame("silver_on_off", res, entity=ent)
                done += 1
                print(f"  {name}: {n} rows", flush=True)
            except Exception as e:
                print(f"  {name}: save failed {e}", flush=True)
        else:
            print(f"  {name}: fetch failed", flush=True)
        time.sleep(2)
    print(f"on_off seeded: {done} new players", flush=True)


if __name__ == "__main__":
    main()
