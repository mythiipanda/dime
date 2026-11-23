import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources.base import safe

TABLE = "silver_gleague_season"
FIRST_SEASON = "2007-08"
LAST_SEASON = "2025-26"
MIN_SEASONS = 15
SOURCE = "nba_api:LeagueDashPlayerStats:gleague"

def seasons():
    out = []
    for end in range(2008, 2027):
        out.append(f"{end - 1}-{str(end)[2:]}")
    return [s for s in out if FIRST_SEASON <= s <= LAST_SEASON]

def fetch(season: str):
    from nba_api.stats.endpoints import LeagueDashPlayerStats

    def run():
        frames = LeagueDashPlayerStats(league_id_nullable="20",
                                       season=season, timeout=30
                                       ).get_data_frames()
        import polars as pl
        return pl.from_pandas(frames[0])

    return safe(SOURCE, season, run)

def main() -> int:
    import os
    if not os.environ.get("DIME_WAREHOUSE", ""):
        print("refusing: DIME_WAREHOUSE is not set")
        return 2
    total = 0
    n_seasons = 0
    for season in seasons():
        res = fetch(season)
        if not res.ok or res.frame.height == 0:
            print(f"gleague {season}: FAILED {res.error}", flush=True)
            continue
        n = store.save_frame(TABLE, res, entity=f"season:{season}",
                             replace_season=True)
        total += n
        n_seasons += 1
        print(f"gleague {season}: {n} rows", flush=True)
        time.sleep(1)
    print(f"{TABLE}: {n_seasons} seasons, {total} rows")
    if n_seasons < MIN_SEASONS:
        print(f"FAIL: only {n_seasons} seasons seeded")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
