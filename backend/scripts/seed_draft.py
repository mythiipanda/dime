"""Seed historical NBA draft data (1997-2024) from sportsdataverse-data.

Usage: python scripts/seed_draft.py (run from backend/)
Source: https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nba_stats_draft
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from app import store
from app.sources.base import FetchMeta, FetchResult

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_stats_draft"


def label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"


def main() -> None:
    print("Fetching draft data 1997..2024...")
    dfs: list[pl.DataFrame] = []
    for y in range(1997, 2025):
        url = f"{BASE}/draft_{y}.parquet"
        try:
            df = pl.read_parquet(url)
            df = df.rename({c: c.upper() for c in df.columns})
            dfs.append(df)
        except Exception as exc:
            print(f"skip {y}: {exc}")
    if not dfs:
        print("No draft data found")
        return
    combined = pl.concat(dfs, how="diagonal")
    combined = combined.with_columns((pl.col("SEASON").cast(pl.Int64) - 1).alias("DRAFT_YEAR"))
    total = 0
    for s in sorted(combined["SEASON"].unique().to_list()):
        chunk = combined.filter(pl.col("SEASON") == s)
        s_int = int(s)
        res = FetchResult(
            frame=chunk,
            meta=FetchMeta(source="sportsdataverse:nba_stats_draft", season=label(s_int)),
        )
        total += store.save_frame("silver_hist_draft", res, entity="draft", replace_season=True)
    print(f"silver_hist_draft loaded: {total} rows across {len(dfs)} draft classes")


if __name__ == "__main__":
    main()
