"""Seed sportsdataverse-data release CSVs into the warehouse.

Usage: python scripts/seed_sportsdataverse.py [--seasons 2025] (run from backend/)
Sources:
  https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nba_stats_shots
  https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nba_stats_player_season_stats

Targets (existing hist tables; schema checked against the warehouse first):
  silver_hist_shots            <- shots_<end_year>.csv, season label like 2024-25
  silver_hist_player_seasons   <- player_season_stats_<end_year>.csv, base+advanced merged

Idempotent: each season is checked against the warehouse before any download.
A season already seeded at the expected row count is skipped. Re-runs converge
because store.save_frame(..., replace_season=True) deletes the season slice
before inserting, so a crashed run simply re-seeds on the next run.
"""

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from app import store
from app.sources.base import FetchMeta, FetchResult

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
DATA = Path(__file__).resolve().parent.parent / "data" / "history"

# Expected row counts from the release investigation; shots fail loudly if off.
EXPECTED = {"shots": {2025: 233_904}}
SHOT_TOL = 0.01  # 1% tolerance around expected shots count
MIN_PLAYER_SEASONS = 400  # a full season carries ~500+ player-season rows


def label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    req = urllib.request.Request(url, headers={"User-Agent": "dime-seed/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.replace(dest)
    return dest


def have_shots(year: int) -> int:
    df = store.read_frame("silver_hist_shots", f"season = {year}", [])
    return len(df)


def have_player_seasons(year: int) -> int:
    df = store.read_frame(
        "silver_hist_player_seasons", "_season = ? AND _entity = 'league'", [label(year)]
    )
    return len(df)


def seed_shots(year: int) -> int:
    have = have_shots(year)
    expected = EXPECTED["shots"].get(year)
    if have:
        if expected is None or abs(have - expected) <= expected * SHOT_TOL:
            print(f"shots {label(year)}: already seeded ({have} rows), skipping")
            return have
        print(f"shots {label(year)}: warehouse has {have} rows vs expected "
              f"{expected}; re-seeding")
    dest = download(f"{BASE}/nba_stats_shots/shots_{year}.csv", DATA / f"shots_{year}.csv")
    frame = pl.read_csv(dest)
    n = len(frame)
    if expected is not None:
        assert abs(n - expected) <= expected * SHOT_TOL, (
            f"shots {label(year)}: upstream has {n} rows, expected ~{expected}"
        )
    res = FetchResult(
        frame=frame,
        meta=FetchMeta(source="sportsdataverse:nba_stats_shots", season=label(year)),
    )
    n = store.save_frame("silver_hist_shots", res, entity=f"season:{label(year)}",
                         replace_season=True)
    print(f"shots {label(year)}: {n} rows")
    return n


BASE_COLS = [
    "player_id", "player_name", "team_abbreviation", "season", "age", "gp", "min",
    "pts", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "fg_pct",
    "fg3m", "fg3a", "fg3_pct", "ftm", "fta", "ft_pct",
]
ADV_COLS = ["player_id", "ts_pct", "efg_pct", "usg_pct", "off_rating",
            "def_rating", "net_rating", "pie", "pace"]
JOIN_KEY = ["player_id", "team_abbreviation"]


def seed_player_seasons(year: int) -> int:
    have = have_player_seasons(year)
    if have >= MIN_PLAYER_SEASONS:
        print(f"player_seasons {label(year)}: already seeded ({have} rows), skipping")
        return have
    dest = download(
        f"{BASE}/nba_stats_player_season_stats/player_season_stats_{year}.csv",
        DATA / f"player_season_stats_{year}.csv",
    )
    df = pl.read_csv(dest)
    rs = df.filter(
        (pl.col("season_type") == "regular-season")
        & (pl.col("per_mode") == "pergame")
    )
    base = rs.filter(pl.col("measure_type") == "base").select(BASE_COLS)
    adv = rs.filter(pl.col("measure_type") == "advanced").select(ADV_COLS + ["team_abbreviation"])
    merged = base.join(adv, on=JOIN_KEY, how="left")
    n = len(merged)
    assert n >= MIN_PLAYER_SEASONS, (
        f"player_seasons {label(year)}: only {n} rows after merge, expected >={MIN_PLAYER_SEASONS}"
    )
    res = FetchResult(
        frame=merged,
        meta=FetchMeta(source="sportsdataverse:nba_stats_player_season_stats",
                       season=label(year)),
    )
    n = store.save_frame("silver_hist_player_seasons", res, entity="league",
                         replace_season=True)
    print(f"player_seasons {label(year)}: {n} rows")
    return n


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--seasons", default="2025")
    ns = args.parse_args()
    years = [int(y) for y in ns.seasons.split(",")]
    print("row counts verified against the warehouse (freshly seeded or skipped):")
    for y in years:
        print(f"  {label(y)} shots: {seed_shots(y)}")
        print(f"  {label(y)} player_seasons: {seed_player_seasons(y)}")


if __name__ == "__main__":
    main()
