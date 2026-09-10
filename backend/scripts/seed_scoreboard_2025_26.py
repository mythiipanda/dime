"""Derive the full 2025-26 silver_scoreboard from in-warehouse team game logs.

- Source: silver_hist_gamelogs 2025-26 slice (1,230 regular-season + 85
  playoff distinct game_ids = 1,315 games; 2 rows per game).
- Home/away teams parsed from the matchup string ("GSW @ LAL" = GSW away at
  LAL home; "LAL vs. GSW" = LAL home vs GSW away), verified against
  silver_team_games' abbr/team_id mapping.
- Matches the existing silver_scoreboard schema exactly (nba_api columns +
  provenance). Real values for ids, dates, teams, and final scores are
  derived; unknown nba_api-only fields (broadcasters, arena, live period)
  are NULL/blank placeholders.

Idempotent: the 2025-26 slice is deleted before insert, so re-runs are safe.

Usage:
    python -m scripts.seed_scoreboard_2025_26          # seed + verify
    python -m scripts.seed_scoreboard_2025_26 --check   # report counts only
"""

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store

SEASON = "2025-26"
END_YEAR = 2026

EXPECTED_GAMES = 1315  # 1,230 regular-season + 85 playoffs

SCOREBOARD_COLS = [
    "GAME_DATE_EST", "GAME_SEQUENCE", "GAME_ID", "GAME_STATUS_ID",
    "GAME_STATUS_TEXT", "GAMECODE", "HOME_TEAM_ID", "VISITOR_TEAM_ID",
    "SEASON", "LIVE_PERIOD", "LIVE_PC_TIME",
    "NATL_TV_BROADCASTER_ABBREVIATION", "HOME_TV_BROADCASTER_ABBREVIATION",
    "AWAY_TV_BROADCASTER_ABBREVIATION", "LIVE_PERIOD_TIME_BCAST",
    "ARENA_NAME", "WH_STATUS", "WNBA_COMMISSIONER_FLAG",
    "HOME_TEAM_PTS", "VISITOR_TEAM_PTS",
    "HOME_TEAM_ABBREVIATION", "VISITOR_TEAM_ABBREVIATION",
    "_source", "_season", "_fetched_at", "_entity",
]

SCOREBOARD_SELECT = """
WITH per AS (
  SELECT
    game_id,
    CAST(game_date AS DATE) AS game_date,
    team_id, team_abbreviation, matchup, wl, pts,
    CASE WHEN matchup LIKE '% vs. %' THEN 1 ELSE 0 END AS is_home_row,
    CASE WHEN matchup LIKE '% @ %' THEN 1 ELSE 0 END AS is_away_row
  FROM silver_hist_gamelogs
  WHERE season = ? AND season_type IN ('regular-season', 'playoffs')
),
-- 5 source rows are corrupt (both teams' matchup rendered "X @ Y").
-- In every corrupt game the LOSER's row is the correct away row ("X @ Y"
-- with X = loser); the winner is home. Verified: this is the unique
-- assignment that keeps every team at 41 home / 41 away in the RS slice.
resolved AS (
  SELECT
    game_id,
    game_date,
    CASE WHEN SUM(is_home_row) = 0
         THEN MAX(CASE WHEN wl = 'W' THEN team_abbreviation END)
         ELSE MAX(CASE WHEN is_home_row = 1 THEN team_abbreviation END)
    END AS home_abbr,
    CASE WHEN SUM(is_home_row) = 0
         THEN MAX(CASE WHEN wl = 'L' THEN team_abbreviation END)
         ELSE MAX(CASE WHEN is_away_row = 1 THEN team_abbreviation END)
    END AS visitor_abbr
  FROM per
  GROUP BY game_id, game_date
),
games AS (
  SELECT
    r.game_id,
    r.game_date,
    r.home_abbr,
    r.visitor_abbr,
    MAX(CASE WHEN p.team_abbreviation = r.home_abbr THEN p.team_id END)
      AS home_team_id,
    MAX(CASE WHEN p.team_abbreviation = r.home_abbr THEN p.pts END)
      AS home_team_pts,
    MAX(CASE WHEN p.team_abbreviation = r.visitor_abbr THEN p.team_id END)
      AS visitor_team_id,
    MAX(CASE WHEN p.team_abbreviation = r.visitor_abbr THEN p.pts END)
      AS visitor_team_pts
  FROM resolved r
  JOIN per p ON p.game_id = r.game_id
  GROUP BY r.game_id, r.game_date, r.home_abbr, r.visitor_abbr
)
SELECT
  STRFTIME(game_date, '%Y-%m-%dT00:00:00') AS "GAME_DATE_EST",
  ROW_NUMBER() OVER (PARTITION BY game_date ORDER BY game_id)
    AS "GAME_SEQUENCE",
  game_id AS "GAME_ID",
  3 AS "GAME_STATUS_ID",
  'Final' AS "GAME_STATUS_TEXT",
  STRFTIME(game_date, '%Y%m%d') || '/' || visitor_abbr
    || home_abbr AS "GAMECODE",
  home_team_id AS "HOME_TEAM_ID",
  visitor_team_id AS "VISITOR_TEAM_ID",
  ? AS "SEASON",
  4 AS "LIVE_PERIOD",
  '     ' AS "LIVE_PC_TIME",
  NULL AS "NATL_TV_BROADCASTER_ABBREVIATION",
  NULL AS "HOME_TV_BROADCASTER_ABBREVIATION",
  NULL AS "AWAY_TV_BROADCASTER_ABBREVIATION",
  NULL AS "LIVE_PERIOD_TIME_BCAST",
  NULL AS "ARENA_NAME",
  NULL AS "WH_STATUS",
  NULL AS "WNBA_COMMISSIONER_FLAG",
  home_team_pts AS "HOME_TEAM_PTS",
  visitor_team_pts AS "VISITOR_TEAM_PTS",
  home_abbr AS "HOME_TEAM_ABBREVIATION",
  visitor_abbr AS "VISITOR_TEAM_ABBREVIATION",
  'sportsdataverse' AS "_source",
  ? AS "_season",
  ? AS "_fetched_at",
  'date:' || STRFTIME(game_date, '%m/%d/%Y') AS "_entity"
FROM games
"""

VERIFY = {
    "game_count": ("SELECT COUNT(*), COUNT(DISTINCT GAME_ID) "
                   "FROM silver_scoreboard WHERE _season = ?"),
    "split": ("SELECT SEASON, "
              "SUM(CASE WHEN GAME_ID LIKE '004%' THEN 1 ELSE 0 END) AS playoffs, "
              "SUM(CASE WHEN GAME_ID LIKE '002%' THEN 1 ELSE 0 END) AS reg, "
              "COUNT(*) FROM silver_scoreboard WHERE _season = ? GROUP BY 1"),
    "nulls": ("SELECT COUNT(*) FROM silver_scoreboard WHERE _season = ? AND "
              "(HOME_TEAM_ID IS NULL OR VISITOR_TEAM_ID IS NULL)"),
    "dupes": ("SELECT GAME_ID, COUNT(*) c FROM silver_scoreboard "
              "WHERE _season = ? GROUP BY 1 HAVING COUNT(*) > 1"),
    # every team plays 41 home + 41 away in the regular season
    "balance": ("SELECT HOME_TEAM_ABBREVIATION, COUNT(*) FROM "
                "silver_scoreboard WHERE _season = ? AND GAME_ID LIKE '002%' "
                "GROUP BY 1 HAVING COUNT(*) != 41"),
    "balance_away": ("SELECT VISITOR_TEAM_ABBREVIATION, COUNT(*) FROM "
                     "silver_scoreboard WHERE _season = ? AND GAME_ID LIKE '002%' "
                     "GROUP BY 1 HAVING COUNT(*) != 41"),
}


def report(con) -> int:
    n = con.execute("SELECT COUNT(*) FROM silver_scoreboard").fetchone()[0]
    print(f"silver_scoreboard: {n} rows")
    return n


def check() -> int:
    con = store.connect(read_only=True)
    try:
        n = report(con)
        ok = n == EXPECTED_GAMES
        print(f"  {'OK' if ok else 'MISMATCH'}: silver_scoreboard "
              f"expected {EXPECTED_GAMES}, got {n}")
        return 0 if ok else 1
    finally:
        con.close()


def seed() -> None:
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()
    con = store.connect()
    try:
        with store.write_guard():
            print("deleting 2025-26 slice from silver_scoreboard ...")
            con.execute("DELETE FROM silver_scoreboard WHERE _season = ?",
                        [SEASON])
            print("deriving 1,315 games from silver_hist_gamelogs ...")
            con.execute(
                "INSERT INTO silver_scoreboard "
                f"({', '.join('\"' + c + '\"' for c in SCOREBOARD_COLS)}) "
                + SCOREBOARD_SELECT,
                [END_YEAR, SEASON, SEASON, fetched_at],
            )

            n, distinct = con.execute(VERIFY["game_count"],
                                      [SEASON]).fetchone()
            print(f"silver_scoreboard[{SEASON}]: {n} rows, "
                  f"{distinct} distinct game ids")
            print("season / playoff split:",
                  con.execute(VERIFY["split"], [SEASON]).fetchall())
            print("rows with null home/visitor team:",
                  con.execute(VERIFY["nulls"], [SEASON]).fetchone()[0])
            print("duplicate game ids:",
                  con.execute(VERIFY["dupes"], [SEASON]).fetchall())

            assert n == EXPECTED_GAMES, f"got {n}, expected {EXPECTED_GAMES}"
            assert distinct == EXPECTED_GAMES, \
                f"distinct game ids = {distinct}, expected {EXPECTED_GAMES}"
            nulls = con.execute(VERIFY["nulls"], [SEASON]).fetchone()[0]
            assert nulls == 0, f"{nulls} rows missing home/visitor team"
            dupes = con.execute(VERIFY["dupes"], [SEASON]).fetchall()
            assert not dupes, f"duplicate game ids: {dupes[:5]}"
            bad_h = con.execute(VERIFY["balance"], [SEASON]).fetchall()
            assert not bad_h, f"teams not at 41 home games: {bad_h}"
            bad_a = con.execute(VERIFY["balance_away"], [SEASON]).fetchall()
            assert not bad_a, f"teams not at 41 away games: {bad_a}"
            print("assertions passed")
    finally:
        con.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report counts only, no writes")
    args = ap.parse_args(argv)
    if args.check:
        return check()
    seed()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
