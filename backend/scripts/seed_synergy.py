import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources.base import FetchMeta, FetchResult

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_stats_synergy"
TABLE = "silver_synergy"
FIRST_YEAR = 2016
LAST_YEAR = 2027
MIN_SEASONS = 8
PLAY_TYPES = [
    "cut", "handoff", "isolation", "misc", "offrebound", "offscreen",
    "postup", "prballhandler", "prrollman", "spotup", "transition",
]
SIDES = ["offensive", "defensive"]
SEASON_TYPE = "regular-season"
MIN_ROWS_PER_SEASON = 500

def label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"

def main() -> int:
    import os
    if not os.environ.get("DIME_WAREHOUSE", ""):
        print("refusing: DIME_WAREHOUSE is not set")
        return 2
    total = 0
    seasons = 0
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        dfs = []
        for pt in PLAY_TYPES:
            for side in SIDES:
                url = (f"{BASE}/{SEASON_TYPE}_{pt}_{side}"
                       f"_totals_{y}.parquet")
                try:
                    df = pl.read_parquet(url)
                    if df.height:
                        dfs.append(df)
                except Exception:
                    pass
        if not dfs:
            print(f"skip {label(y)}: no files", flush=True)
            continue
        combined = pl.concat(dfs, how="diagonal")
        if combined.height < MIN_ROWS_PER_SEASON:
            print(f"skip {label(y)}: only {combined.height} rows", flush=True)
            continue
        res = FetchResult(
            frame=combined,
            meta=FetchMeta(source="sportsdataverse:nba_stats_synergy",
                           season=label(y)),
        )
        n = store.save_frame(TABLE, res, entity=f"season:{label(y)}",
                             replace_season=True)
        total += n
        seasons += 1
        print(f"synergy {label(y)}: {n} rows", flush=True)
    print(f"{TABLE}: {seasons} seasons, {total} rows")
    if seasons < MIN_SEASONS:
        print(f"FAIL: only {seasons} seasons seeded")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
