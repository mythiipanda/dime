"""Promote the 2025-26 in-warehouse slices (sportsdataverse seeds) into the
current-season silver_* tables.

- silver_team_games: 2025-26 regular-season slice from silver_hist_gamelogs
  (2,460 rows = 30 teams x 82 games; W/L/W_PCT derived as running records).
- silver_lineups: full 2025-26 slice from silver_hist_lineups (48,188 rows,
  all measure types / per modes; regular-season + playoffs).

Idempotent: the 2025-26 slice is deleted before insert, so re-runs are safe.

Usage:
    python -m scripts.seed_2025_26_warehouse          # seed + verify
    python -m scripts.seed_2025_26_warehouse --check  # report counts only
"""

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store

SEASON = "2025-26"
END_YEAR = 2026

TEAM_GAME_COLS = [
    "Team_ID", "Game_ID", "GAME_DATE", "MATCHUP", "WL", "W", "L", "W_PCT",
    "MIN", "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA",
    "FT_PCT", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PTS",
    "_source", "_season", "_fetched_at", "_entity",
]

LINEUP_COLS = [
    "GROUP_SET", "GROUP_ID", "GROUP_NAME", "TEAM_ID", "TEAM_ABBREVIATION",
    "GP", "W", "L", "W_PCT", "MIN",
    "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT",
    "FTM", "FTA", "FT_PCT", "OREB", "DREB", "REB",
    "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS",
] + [c + "_RANK" for c in [
    "GP", "W", "L", "W_PCT", "MIN",
    "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT",
    "FTM", "FTA", "FT_PCT", "OREB", "DREB", "REB",
    "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS",
]] + [
    "SUM_TIME_PLAYED", "_source", "_season", "_fetched_at", "_entity",
]

TEAM_GAME_SELECT = """
SELECT
  team_id AS "Team_ID",
  game_id AS "Game_ID",
  -- warehouse convention: nba_api-style "APR 01, 2026" (consumers parse %b %d, %Y)
  UPPER(STRFTIME(CAST(game_date AS DATE), '%b %d, %Y')) AS "GAME_DATE",
  matchup AS "MATCHUP",
  wl AS "WL",
  SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) OVER
    (PARTITION BY team_id ORDER BY game_date, game_id
     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS "W",
  SUM(CASE WHEN wl = 'L' THEN 1 ELSE 0 END) OVER
    (PARTITION BY team_id ORDER BY game_date, game_id
     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS "L",
  CAST(SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) OVER
    (PARTITION BY team_id ORDER BY game_date, game_id
     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS DOUBLE) /
    CAST(ROW_NUMBER() OVER
    (PARTITION BY team_id ORDER BY game_date, game_id) AS DOUBLE) AS "W_PCT",
  min AS "MIN",
  fgm AS "FGM",
  fga AS "FGA",
  fg_pct AS "FG_PCT",
  fg3m AS "FG3M",
  fg3a AS "FG3A",
  fg3_pct AS "FG3_PCT",
  ftm AS "FTM",
  fta AS "FTA",
  ft_pct AS "FT_PCT",
  oreb AS "OREB",
  dreb AS "DREB",
  reb AS "REB",
  ast AS "AST",
  stl AS "STL",
  blk AS "BLK",
  tov AS "TOV",
  pf AS "PF",
  pts AS "PTS",
  'sportsdataverse' AS "_source",
  ? AS "_season",
  ? AS "_fetched_at",
  'team:' || CAST(team_id AS VARCHAR) AS "_entity"
FROM silver_hist_gamelogs
WHERE season = ? AND season_type = 'regular-season'
"""

LINEUP_SELECT = """
SELECT {cols}, 'sportsdataverse' AS "_source", ? AS "_season",
       ? AS "_fetched_at",
       'team:' || CAST(team_id AS VARCHAR) AS "_entity"
FROM silver_hist_lineups
WHERE season = ?
""".format(
    cols=", ".join(f"{c.lower()} AS \"{c}\"" for c in LINEUP_COLS
                   if c not in ("_source", "_season", "_fetched_at", "_entity"))
)


def report(con) -> dict[str, int]:
    counts = {}
    for t in ("silver_team_games", "silver_lineups"):
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        counts[t] = n
        print(f"{t}: {n} rows")
    return counts


def check() -> int:
    con = store.connect(read_only=True)
    try:
        counts = report(con)
    finally:
        con.close()
    tg = con_check_target("silver_team_games", 2460, counts["silver_team_games"])
    lu = con_check_target("silver_lineups", 48188, counts["silver_lineups"])
    return 0 if (tg and lu) else 1


def con_check_target(name, expected, actual) -> bool:
    ok = actual == expected
    print(f"  {'OK' if ok else 'MISMATCH'}: {name} expected {expected}, got {actual}")
    return ok


def seed() -> None:
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()
    con = store.connect()
    try:
        with store.write_guard():
            print("deleting 2025-26 slice from silver_team_games ...")
            con.execute("DELETE FROM silver_team_games WHERE _season = ?",
                        [SEASON])
            print("inserting 2025-26 regular-season team games ...")
            con.execute(
                "INSERT INTO silver_team_games "
                f"({', '.join('\"' + c + '\"' for c in TEAM_GAME_COLS)}) "
                + TEAM_GAME_SELECT,
                [SEASON, fetched_at, END_YEAR],
            )
            tg = con.execute("SELECT COUNT(*) FROM silver_team_games"
                             ).fetchone()[0]

            print("deleting 2025-26 slice from silver_lineups ...")
            con.execute("DELETE FROM silver_lineups WHERE _season = ?",
                        [SEASON])
            print("inserting 2025-26 lineups ...")
            con.execute(
                "INSERT INTO silver_lineups "
                f"({', '.join('\"' + c + '\"' for c in LINEUP_COLS)}) "
                + LINEUP_SELECT,
                [SEASON, fetched_at, END_YEAR],
            )
            lu = con.execute("SELECT COUNT(*) FROM silver_lineups").fetchone()[0]

            teams = con.execute(
                "SELECT COUNT(DISTINCT TEAM_ID) FROM silver_lineups").fetchone()[0]
            print(f"silver_team_games: {tg} rows")
            print(f"silver_lineups: {lu} rows ({teams} teams)")

            assert tg == 2460, f"silver_team_games = {tg}, expected 2460"
            assert lu > 45000, f"silver_lineups = {lu}, expected > 45000"
            assert teams == 30, f"silver_lineups teams = {teams}, expected 30"
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
