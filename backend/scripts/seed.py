"""Seed the warehouse for one season. Standings plus leaders plus injuries.

Usage: python -m scripts.seed --season 2025-26
Heavy tables seed on demand through the dataset API, not here.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store
from app.sources import espn, nba_stats


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--season", default="2025-26")
    ns = args.parse_args()
    season: str = ns.season

    total = 0
    res = nba_stats.standings(season)
    if res.ok:
        total += store.save_frame("silver_standings", res)
    print("standings:", res.ok, res.frame.height)

    res = nba_stats.leaders("PTS", season)
    if res.ok:
        total += store.save_frame("silver_leaders_pts", res)
    print("leaders:", res.ok, res.frame.height)

    res = espn.injuries(season)
    if res.ok:
        total += store.save_frame("silver_injuries", res)
    print("injuries:", res.ok, res.frame.height)

    print("seeded rows:", total)


if __name__ == "__main__":
    main()
