"""Seed ESPN team schedules into silver_schedule.

Usage: python3 scripts/seed_espn_schedule.py [--season 2026] (run from backend/)
ESPN season ints are end years: 2026 means 2025-26. Idempotent per season.
Keyless via sportsdataverse. Nested competitions/links columns dropped.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from app import store
from app.sources.base import FetchMeta, FetchResult

DROP = {"competitions", "links"}


def label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--season", type=int, default=2026)
    ns = args.parse_args()
    from sportsdataverse.nba import espn_nba_teams, espn_nba_team_schedule

    teams = espn_nba_teams()
    teams = pl.from_pandas(teams) if not isinstance(teams, pl.DataFrame) else teams
    ids = [(r["team_abbreviation"], int(r["team_id"]))
           for r in teams.to_dicts() if r.get("team_abbreviation")]
    print(f"seeding {len(ids)} team schedules for {label(ns.season)}")
    total = 0
    for abbr, eid in ids:
        try:
            df = espn_nba_team_schedule(team_id=eid, season=ns.season)
            df = pl.from_pandas(df) if not isinstance(df, pl.DataFrame) else df
        except Exception as exc:
            print(f"skip {abbr}: {exc}")
            continue
        if df.height == 0:
            continue
        df = df.drop([c for c in DROP if c in df.columns])
        df = df.with_columns(pl.lit(abbr).alias("team_abbreviation"))
        res = FetchResult(
            frame=df,
            meta=FetchMeta(source="espn:team_schedule", season=label(ns.season)),
        )
        total += store.save_frame("silver_schedule", res, entity=f"team:{abbr}",
                                  replace_season=False)
    print(f"silver_schedule loaded: {total} rows")


if __name__ == "__main__":
    main()
