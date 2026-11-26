import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store

TABLE = "silver_wowy_derived"

_ON_PARTS = []
for _i in range(1, 6):
    _ON_PARTS.append(
        f"SELECT _season, game_id, home_team_id AS team_id, "
        f"home_player_{_i} AS player_id, duration_sec, home_swing AS swing "
        f"FROM silver_stints")
for _i in range(1, 6):
    _ON_PARTS.append(
        f"SELECT _season, game_id, away_team_id AS team_id, "
        f"away_player_{_i} AS player_id, duration_sec, -home_swing AS swing "
        f"FROM silver_stints")
_ONCT = " UNION ALL ".join(_ON_PARTS)

SELECT_SQL = f"""
WITH onct AS (
{_ONCT}
),
agg AS (
    SELECT _season, player_id, team_id,
           count(DISTINCT game_id) AS games_on,
           sum(duration_sec) / 60.0 AS on_minutes,
           sum(swing) AS on_net
    FROM onct
    GROUP BY _season, player_id, team_id
),
team_stints AS (
    SELECT _season, home_team_id AS team_id, game_id, duration_sec,
           home_swing AS swing
    FROM silver_stints
    UNION ALL
    SELECT _season, away_team_id AS team_id, game_id, duration_sec,
           -home_swing AS swing
    FROM silver_stints
),
team_agg AS (
    SELECT _season, team_id,
           count(DISTINCT game_id) AS games_played,
           sum(duration_sec) / 60.0 AS team_minutes,
           sum(swing) AS team_net
    FROM team_stints
    GROUP BY _season, team_id
),
names_bc AS (
    SELECT DISTINCT PLAYER_ID AS player_id, _season,
           left(firstName, 1) || '. ' || familyName AS player_name
    FROM silver_boxscores_ext
),
names_hist AS (
    SELECT DISTINCT player_id, _season,
           left(player_name, 1) || '. ' ||
               substr(player_name, position(' ' IN player_name) + 1) AS player_name
    FROM silver_hist_player_seasons
    WHERE position(' ' IN player_name) > 0
)
SELECT a._season,
       a.player_id,
       coalesce(bc.player_name, hs.player_name, cast(a.player_id AS VARCHAR))
           AS player_name,
       a.team_id,
       a.games_on,
       t.games_played,
       a.on_minutes,
       a.on_net * 48.0 / a.on_minutes AS on_net_per48,
       (t.team_net - a.on_net) * 48.0 /
           nullif(t.team_minutes - a.on_minutes, 0) AS off_net_per48,
       a.on_net * 48.0 / a.on_minutes -
           (t.team_net - a.on_net) * 48.0 /
           nullif(t.team_minutes - a.on_minutes, 0) AS wowy_diff_per48
FROM agg a
JOIN team_agg t ON t._season = a._season AND t.team_id = a.team_id
LEFT JOIN names_bc bc ON bc.player_id = a.player_id AND bc._season = a._season
LEFT JOIN names_hist hs ON hs.player_id = a.player_id AND hs._season = a._season
"""


def build(con):
    cur = con.execute(SELECT_SQL)
    cols = [d[0] for d in cur.description]
    return cols, cur.fetchall()


def main() -> None:
    con = store.connect(read_only=False)
    try:
        con.execute(f"CREATE OR REPLACE TABLE {TABLE} AS {SELECT_SQL}")
        rows = con.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]
        seasons = con.execute(
            f"SELECT min(_season), max(_season) FROM {TABLE}").fetchone()
    finally:
        con.close()
    print(f"{TABLE}: {rows} rows, seasons {seasons[0]}..{seasons[1]}")


if __name__ == "__main__":
    main()
