"""Seed team hustle stats (LeagueHustleStatsTeam) into the warehouse.

Source: stats.nba.com LeagueHustleStatsTeam, 2025-26 season.
Normals: silver_hustle_team (one row per NBA team).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store
from app.sources import nba_stats


def _save(res):
    return store.save_frame("silver_hustle_team", res, entity="season:2025-26")


def main() -> None:
    res = nba_stats.hustle("team", "2025-26")
    frame = res.frame
    print(f"scraped {len(frame)} hustle team rows")
    try:
        n = _save(res)
    except Exception as exc:
        msg = str(exc).lower()
        if "lock" not in msg and "conflict" not in msg:
            raise
        time.sleep(5)
        n = _save(res)
    print(f"silver_hustle_team: {n} rows saved")
    con = store.connect()
    try:
        (count,) = con.execute(
            "SELECT COUNT(*) FROM silver_hustle_team WHERE _season = ?",
            ["2025-26"],
        ).fetchone()
    finally:
        con.close()
    print(f"silver_hustle_team 2025-26: {count} rows")
    if count != 30:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
