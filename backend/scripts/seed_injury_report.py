import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources.base import FetchMeta, FetchResult

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_stats_injury_report"
TABLE = "silver_injury_report"
FIRST_YEAR = 2019
LAST_YEAR = 2026
MIN_SEASONS = 6

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
        url = f"{BASE}/injury_report_{y}.parquet"
        try:
            df = pl.read_parquet(url)
        except Exception as exc:
            print(f"skip {y}: {exc}", flush=True)
            continue
        res = FetchResult(
            frame=df,
            meta=FetchMeta(source="sportsdataverse:nba_stats_injury_report",
                           season=label(y)),
        )
        n = store.save_frame(TABLE, res, entity=f"season:{label(y)}",
                             replace_season=True)
        total += n
        seasons += 1
        print(f"injury_report {label(y)}: {n} rows", flush=True)
    print(f"{TABLE}: {seasons} seasons, {total} rows")
    if seasons < MIN_SEASONS:
        print(f"FAIL: only {seasons} seasons seeded")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
