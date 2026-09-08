"""Seed FiveThirtyEight RAPTOR modern tables into the warehouse.

Usage: python scripts/seed_raptor.py (run from backend/)
Source: https://github.com/fivethirtyeight/data/tree/master/nba-raptor
Season ints are end years: 2022 -> '2021-22'. Saved per season so each
row carries its own _season label. Per-season scoped saves make reruns
converge instead of duplicating.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from app import store
from app.sources.base import FetchMeta, FetchResult

BASE = "https://raw.githubusercontent.com/fivethirtyeight/data/master/nba-raptor"
TABLES = {
    "silver_raptor_player": f"{BASE}/modern_RAPTOR_by_player.csv",
    "silver_raptor_team": f"{BASE}/modern_RAPTOR_by_team.csv",
}


def label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"


def load(table: str, url: str) -> int:
    frame = pl.read_csv(url)
    frame = frame.rename({c: c.upper() for c in frame.columns})
    frame = frame.with_columns(pl.col("SEASON").cast(pl.Int64))
    total = 0
    for s in sorted(frame["SEASON"].unique().to_list()):
        chunk = frame.filter(pl.col("SEASON") == s)
        res = FetchResult(
            frame=chunk,
            meta=FetchMeta(source="fivethirtyeight:raptor", season=label(int(s))),
        )
        total += store.save_frame(table, res, entity="league", replace_season=True)
    print(f"{table}: {total} rows")
    return total


def main() -> None:
    print(f"player seasons: {label(2014)}..{label(2022)}")
    total = sum(load(t, u) for t, u in TABLES.items())
    print(f"raptor rows loaded: {total}")


if __name__ == "__main__":
    main()
