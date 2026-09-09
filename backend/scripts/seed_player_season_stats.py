"""Seed LeagueDash player season stats (base + advanced, per-game, regular season).

Usage: python scripts/seed_player_season_stats.py [--start 2015 --end 2024] (run from backend/)
Source: https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nba_stats_player_season_stats
Merges base and advanced measure types on player_id into silver_hist_player_seasons.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from app import store
from app.sources.base import FetchMeta, FetchResult

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_stats_player_season_stats"

BASE_COLS = [
    "player_id", "player_name", "team_abbreviation", "season", "age", "gp", "min",
    "pts", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "fg_pct",
    "fg3m", "fg3a", "fg3_pct", "ftm", "fta", "ft_pct",
]
ADV_COLS = ["player_id", "ts_pct", "efg_pct", "usg_pct", "off_rating",
            "def_rating", "net_rating", "pie", "pace"]


def label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--start", type=int, default=2015)
    args.add_argument("--end", type=int, default=2024)
    ns = args.parse_args()
    total = 0
    for y in range(ns.start, ns.end + 1):
        try:
            df = pl.read_parquet(f"{BASE}/player_season_stats_{y}.parquet")
        except Exception as exc:
            print(f"skip {y}: {exc}")
            continue
        rs = df.filter(
            (pl.col("season_type") == "regular-season")
            & (pl.col("per_mode") == "pergame")
        )
        base = rs.filter(pl.col("measure_type") == "base").select(BASE_COLS)
        adv = rs.filter(pl.col("measure_type") == "advanced").select(ADV_COLS)
        merged = base.join(adv, on="player_id", how="left")
        res = FetchResult(
            frame=merged,
            meta=FetchMeta(source="sportsdataverse:nba_stats_player_season_stats",
                           season=label(y)),
        )
        n = store.save_frame("silver_hist_player_seasons", res,
                             entity="league", replace_season=True)
        total += n
        print(f"{label(y)}: {n} player-seasons")
    print(f"silver_hist_player_seasons loaded: {total} rows")


if __name__ == "__main__":
    main()
