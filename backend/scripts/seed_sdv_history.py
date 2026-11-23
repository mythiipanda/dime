import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources.base import FetchMeta, FetchResult

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"

SOURCES = [
    {
        "table": "silver_hist_hustle",
        "release": "nba_stats_hustle",
        "pattern": "leaguehustlestatsplayer_regular-season_totals_{y}.parquet",
        "first": 2016, "last": 2027, "min_rows": 300,
    },
    {
        "table": "silver_coaches_history",
        "release": "nba_stats_coaches",
        "pattern": "coaches_{y}.parquet",
        "first": 1997, "last": 2027, "min_rows": 30,
    },
    {
        "table": "silver_officials",
        "release": "nba_stats_officials",
        "pattern": "officials_{y}.parquet",
        "first": 1997, "last": 2027, "min_rows": 500,
    },
]

def label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"

def main() -> int:
    import os
    if not os.environ.get("DIME_WAREHOUSE", ""):
        print("refusing: DIME_WAREHOUSE is not set")
        return 2
    failed = []
    for src in SOURCES:
        seasons = 0
        total = 0
        for y in range(src["first"], src["last"] + 1):
            url = f"{BASE}/{src['release']}/{src['pattern'].format(y=y)}"
            try:
                df = pl.read_parquet(url)
            except Exception as exc:
                print(f"{src['table']} {label(y)}: skip {exc}", flush=True)
                continue
            if df.height < src["min_rows"]:
                print(f"{src['table']} {label(y)}: only {df.height} rows",
                      flush=True)
                continue
            res = FetchResult(
                frame=df,
                meta=FetchMeta(source=f"sportsdataverse:{src['release']}",
                               season=label(y)),
            )
            n = store.save_frame(src["table"], res,
                                 entity=f"season:{label(y)}",
                                 replace_season=True)
            total += n
            seasons += 1
            print(f"{src['table']} {label(y)}: {n} rows", flush=True)
        print(f"{src['table']}: {seasons} seasons, {total} rows")
        if seasons < 3:
            failed.append(src["table"])
    if failed:
        print(f"FAIL: {failed}")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
