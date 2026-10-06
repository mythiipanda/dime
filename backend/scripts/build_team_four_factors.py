import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from v2.adapters import coverage

SQL = """
WITH games AS (
    SELECT Team_ID, Game_ID, _season,
           FGM, FG3M, FGA, FTA, TOV, OREB, DREB,
           MIN, PTS, WL,
           -- team abbreviation is the first token of MATCHUP
           split_part(MATCHUP, ' ', 1) AS TEAM
    FROM silver_team_games
    WHERE _season = ?
),
paired AS (
    SELECT g.*, o.DREB AS OPP_DREB, o.FGM AS OPP_FGM,
           o.FG3M AS OPP_FG3M, o.FGA AS OPP_FGA, o.FTA AS OPP_FTA,
           o.TOV AS OPP_TOV, o.OREB AS OPP_OREB
    FROM games g
    JOIN games o ON o.Game_ID = g.Game_ID AND o.Team_ID <> g.Team_ID
)
SELECT TEAM, Team_ID, _season, COUNT(*) AS GP,
       SUM(CASE WHEN WL = 'W' THEN 1 ELSE 0 END) AS W,
       ROUND((SUM(FGM) + 0.5 * SUM(FG3M)) / NULLIF(SUM(FGA), 0), 4) AS EFG_PCT,
       ROUND(SUM(TOV) / NULLIF(SUM(FGA) + 0.44 * SUM(FTA) + SUM(TOV), 0), 4) AS TOV_PCT,
       ROUND(SUM(OREB) / NULLIF(SUM(OREB) + SUM(OPP_DREB), 0), 4) AS ORB_PCT,
       ROUND(SUM(FTA) / NULLIF(SUM(FGA), 0), 4) AS FT_RATE,
       ROUND((SUM(OPP_FGM) + 0.5 * SUM(OPP_FG3M)) / NULLIF(SUM(OPP_FGA), 0), 4) AS OPP_EFG_PCT,
       ROUND(SUM(OPP_TOV) / NULLIF(SUM(OPP_FGA) + 0.44 * SUM(OPP_FTA) + SUM(OPP_TOV), 0), 4) AS OPP_TOV_PCT,
       ROUND(SUM(DREB) / NULLIF(SUM(DREB) + SUM(OPP_OREB), 0), 4) AS DRB_PCT,
       ROUND(SUM(OPP_FTA) / NULLIF(SUM(OPP_FGA), 0), 4) AS OPP_FT_RATE
FROM paired
GROUP BY TEAM, Team_ID, _season
ORDER BY EFG_PCT DESC
"""

LEAGUE_SIZE = 30

TOOL_TABLE = "silver_team_games"
TEAM_COLUMN = "Team_ID"

def league_seasons() -> tuple[str, ...]:
    return coverage.league_seasons(TOOL_TABLE, TEAM_COLUMN, LEAGUE_SIZE)

def build(season: str) -> tuple[dict, int]:
    con = store.connect(read_only=False)
    try:
        cur = con.execute(SQL, [season])
        cols = [d[0] for d in con.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()
    print(f"computed four factors for {len(rows)} teams ({season})")
    if len(rows) != LEAGUE_SIZE:
        raise SystemExit(
            f"{season}: expected {LEAGUE_SIZE} teams, got {len(rows)}; "
            f"this season is not a complete league season")
    return rows, len(rows)

def main() -> None:

    seasons = sys.argv[1:] or league_seasons()
    if not seasons:
        raise SystemExit("no league-complete seasons found")
    for season in seasons:
        rows, _ = build(season)
        con = store.connect(read_only=False)
        try:
            con.execute(
                "CREATE TABLE IF NOT EXISTS silver_four_factors_team AS "
                "SELECT * FROM frame LIMIT 0")
            con.execute(
                "DELETE FROM silver_four_factors_team WHERE _season = ?",
                [season])
            con.execute("INSERT INTO silver_four_factors_team "
                        "SELECT * FROM frame")
            (n,) = con.execute(
                "SELECT COUNT(*) FROM silver_four_factors_team "
                "WHERE _season = ?", [season]).fetchone()
        finally:
            con.close()
        print(f"silver_four_factors_team {season}: {n} rows")
        if n != LEAGUE_SIZE:
            raise SystemExit(1)

if __name__ == "__main__":
    main()
