import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources.base import FetchMeta, FetchResult

TABLE = "silver_injury_history"
SOURCE = "derived:hist_player_seasons+hist_gamelogs"
SEASON = "1996-2025"
MIN_SEASONS = 25

BUILD_SQL = """
WITH team_games AS (
    SELECT team_abbreviation AS TEAM_ABBREVIATION,
           season AS SEASON_YEAR,
           COUNT(*) AS TEAM_GP
    FROM silver_hist_gamelogs
    WHERE season_type = 'regular-season'
    GROUP BY team_abbreviation, season
)
SELECT p.player_id AS PLAYER_ID,
       p.player_name AS PLAYER_NAME,
       p.season AS SEASON_YEAR,
       CONCAT(p.season - 1, '-', RIGHT(CAST(p.season AS VARCHAR), 2)) AS SEASON,
       p.team_abbreviation AS TEAM_ABBREVIATION,
       p.gp AS GP,
       g.TEAM_GP AS TEAM_GP,
       GREATEST(g.TEAM_GP - p.gp, 0) AS GAMES_MISSED,
       ROUND(p.gp * 100.0 / g.TEAM_GP, 1) AS AVAILABILITY_PCT
FROM silver_hist_player_seasons p
JOIN team_games g
  ON g.TEAM_ABBREVIATION = p.team_abbreviation
 AND g.SEASON_YEAR = p.season
"""


def _save(res):
    return store.save_frame(TABLE, res, entity="league")


def main() -> None:
    con = store.connect()
    try:
        rows = con.execute(BUILD_SQL).fetchall()
        cols = [d[0] for d in con.description]
    finally:
        con.close()
    frame = pl.DataFrame({c: [r[i] for r in rows]
                          for i, c in enumerate(cols)})
    res = FetchResult(frame=frame,
                      meta=FetchMeta(source=SOURCE, season=SEASON))
    print(f"injury history rows: {frame.height}")
    try:
        n = _save(res)
    except Exception as exc:
        msg = str(exc).lower()
        if "lock" not in msg and "conflict" not in msg:
            raise
        time.sleep(5)
        n = _save(res)
    print(f"{TABLE}: {n} rows saved")
    con = store.connect()
    try:
        (count,) = con.execute(
            f"SELECT COUNT(DISTINCT SEASON) FROM {TABLE}").fetchone()
    finally:
        con.close()
    print(f"{TABLE}: {count} seasons")
    if count < MIN_SEASONS:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
