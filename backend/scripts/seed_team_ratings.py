#!/usr/bin/env python3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.sources import nba_stats
from shared import store


def seed_team_ratings(seasons):
    con = store.connect(read_only=False)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS silver_team_ratings ("
            "TEAM_ID BIGINT, TEAM_NAME VARCHAR, TEAM_ABBREV VARCHAR, "
            "GP INTEGER, W INTEGER, L INTEGER, "
            "OFF_RATING DOUBLE, DEF_RATING DOUBLE, NET_RATING DOUBLE, "
            "PACE DOUBLE, _season VARCHAR, _source VARCHAR, "
            "_fetched_at TIMESTAMP)"
        )
        try:
            from nba_api.stats.static import teams as _static_teams
            abbrev_map = {
                t["id"]: t["abbreviation"] for t in _static_teams.get_teams()
            }
        except Exception:
            abbrev_map = {}
        now = datetime.now(timezone.utc)
        for season in seasons:
            existing = con.execute(
                "SELECT COUNT(*) FROM silver_team_ratings WHERE _season = ?",
                [season],
            ).fetchone()[0]
            if existing > 0:
                print(f"{season}: already seeded ({existing} rows), skipping")
                continue
            result = nba_stats.team_ratings(season)
            if not result.ok or result.frame is None or result.frame.height == 0:
                print(f"{season}: fetch failed: {result.error}")
                continue
            rows = []
            for rec in result.frame.to_dicts():
                team_id = int(rec["TEAM_ID"])
                rows.append((
                    team_id,
                    rec["TEAM_NAME"],
                    abbrev_map.get(team_id),
                    int(rec["GP"]),
                    int(rec["W"]),
                    int(rec["L"]),
                    float(rec["OFF_RATING"]),
                    float(rec["DEF_RATING"]),
                    float(rec["NET_RATING"]),
                    float(rec["PACE"]) if rec.get("PACE") is not None else None,
                    season,
                    "nba_api",
                    now,
                ))
            con.executemany(
                "INSERT INTO silver_team_ratings VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            print(f"{season}: seeded {len(rows)} teams")
    finally:
        con.close()


if __name__ == "__main__":
    seasons = sys.argv[1:] or ["2024-25"]
    seed_team_ratings(seasons)
