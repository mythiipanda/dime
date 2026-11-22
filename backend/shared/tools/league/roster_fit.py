from typing import Any

from langchain_core.tools import tool

from .._core import coerce_team_id, team_error_message
from ._helpers import _owned_connection, _pkg, _warehouse_tables


def _team_lookup() -> dict[int, dict[str, str]]:
    from nba_api.stats.static import teams as _teams

    return {t["id"]: {"abbrev": t["abbreviation"], "name": t["full_name"]}
            for t in _teams.get_teams()}


def _season_end_year(season: str) -> int:
    return int(str(season).split("-")[0]) + 1


_FLAG_SQL = """
SELECT TEAM,
       count(*) AS rotation,
       sum(MIN * ((FG3A * 1.0 / nullif(FGA, 0) >= 0.4
                  AND FG3_PCT >= 0.34)::int)) / sum(MIN)
           AS spacing_min_share,
       sum(MIN * ((AST / MIN * 36 >= 4.5
                  OR PTS / MIN * 36 >= 20)::int)) / sum(MIN)
           AS creation_min_share,
       sum(MIN * ((BLK / MIN * 36 >= 1.2)::int)) / sum(MIN)
           AS rim_min_share,
       sum(MIN * (((STL + BLK) / MIN * 36 >= 1.6)::int)) / sum(MIN)
           AS defense_min_share,
       1 - (SELECT sum(m2) FROM (
              SELECT sum(t2.MIN) AS m2 FROM silver_leaders_pts t2
              WHERE t2._season = ? AND t2.TEAM = t.TEAM
                AND t2.GP >= 5
              GROUP BY t2.PLAYER ORDER BY m2 DESC LIMIT 5)) / sum(MIN)
           AS bench_min_share
FROM silver_leaders_pts t
WHERE _season = ? AND GP >= 5 AND MIN / GP >= 12
GROUP BY TEAM
"""

_PLAYER_FLAGS_SQL = """
SELECT PLAYER, TEAM, round(MIN / GP, 1) AS mpg,
       FG3A * 1.0 / nullif(FGA, 0) >= 0.4 AND FG3_PCT >= 0.34 AS spacer,
       AST / MIN * 36 >= 4.5 OR PTS / MIN * 36 >= 20 AS creator,
       BLK / MIN * 36 >= 1.2 AS rim_protector,
       (STL + BLK) / MIN * 36 >= 1.6 AS defender
FROM silver_leaders_pts
WHERE _season = ? AND TEAM = ? AND GP >= 5 AND MIN / GP >= 12
ORDER BY MIN DESC
"""

_DIMS = (
    ("spacing", "spacing_min_share",
     "share of rotation minutes from spacers "
     "(3PA rate >= 40% and 3P% >= 34%)"),
    ("creation", "creation_min_share",
     "share of rotation minutes from creators "
     "(ast/36 >= 4.5 or pts/36 >= 20)"),
    ("rim_protection", "rim_min_share",
     "share of rotation minutes from rim protectors "
     "(blk/36 >= 1.2)"),
    ("defense", "defense_min_share",
     "share of rotation minutes from defenders "
     "((stl+blk)/36 >= 1.6)"),
    ("depth", "bench_min_share",
     "share of rotation minutes outside the top 5"),
)


def _contender_abbrs(con, season_str: str) -> set[str]:
    end_year = _season_end_year(season_str)
    tables = _warehouse_tables(con)
    rows = []
    if "silver_hist_standings" in tables:
        rows = con.execute(
            """SELECT team_id FROM silver_hist_standings
               WHERE season = ? ORDER BY win_pct DESC LIMIT 8""",
            [end_year]).fetchall()
    if not rows and "silver_standings" in tables:
        rows = con.execute(
            """SELECT "TeamID" FROM silver_standings
               ORDER BY "WinPCT" DESC LIMIT 8""").fetchall()
    lookup = _team_lookup()
    return {lookup[r[0]]["abbrev"] for r in rows if r[0] in lookup}


@tool(description=(
    "Roster gap and fit profile for one team and season (default "
    "current): rotation shares by skill archetype (spacing, creation, "
    "rim protection, defense, bench depth) versus league and top-8 "
    "contender baselines, returning the biggest gaps. Reads "
    "silver_leaders_pts and standings; warehouse only."))
def get_roster_fit(team_id: object = None, team: str = "",
                   season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        tid = coerce_team_id(team_id if team_id is not None else team)
    except ValueError as exc:
        return {"tool": "get_roster_fit", "ok": False, "error": str(exc)}
    info = _team_lookup().get(tid)
    if not info:
        return {"tool": "get_roster_fit", "ok": False,
                "error": team_error_message(tid)}
    with _owned_connection(None, read_only=True) as con:
        tables = _warehouse_tables(con)
        if "silver_leaders_pts" not in tables:
            return {"tool": "get_roster_fit", "ok": False,
                    "error": "silver_leaders_pts not in warehouse; "
                             "run the leaders seeder first."}
        metrics = con.execute(_FLAG_SQL, [season, season]).fetchall()
        if not metrics:
            return {"tool": "get_roster_fit", "ok": False,
                    "error": f"no rotation rows for season {season}"}
        cols = [c[0] for c in con.description]
        by_team = {r[0]: dict(zip(cols, r)) for r in metrics}
        mine = by_team.get(info["abbrev"])
        if not mine:
            return {"tool": "get_roster_fit", "ok": False,
                    "error": f"{info['abbrev']} has no rotation rows "
                             f"for {season}"}
        contenders = _contender_abbrs(con, season) - {info["abbrev"]}
        contenders = contenders or \
            (_contender_abbrs(con, season) | {info["abbrev"]})
        players = [dict(zip([c[0] for c in con.description], r))
                   for r in con.execute(
                       _PLAYER_FLAGS_SQL, [season, info["abbrev"]]).fetchall()]
    league_n = len(by_team)
    rows = []
    for name, col, desc in _DIMS:
        team_val = mine.get(col)
        league_avg = sum(t[col] for t in by_team.values()
                         if t[col] is not None) / league_n
        pool = [by_team[a] for a in contenders if a in by_team]
        cont_avg = sum(t[col] for t in pool
                       if t[col] is not None) / len(pool) if pool else None
        row = {"dimension": name, "definition": desc,
               "team": round(team_val, 3) if team_val is not None else None,
               "league_avg": round(league_avg, 3),
               "contender_avg": round(cont_avg, 3)
               if cont_avg is not None else None}
        if team_val is not None and cont_avg is not None:
            row["gap_vs_contenders"] = round(team_val - cont_avg, 3)
        rows.append(row)
    gaps = sorted((r for r in rows if r.get("gap_vs_contenders")
                   is not None), key=lambda r: r["gap_vs_contenders"])
    meta = {"source": "warehouse", "season": season,
            "tables": ["silver_leaders_pts", "silver_hist_standings",
                       "silver_standings"],
            "contender_baseline": sorted(contenders),
            "rotation": "players with GP>=5 and >=12 MPG",
            "player_flags": players}
    return {"tool": "get_roster_fit", "ok": True,
            "team": info["name"], "abbrev": info["abbrev"],
            "season": season, "rows": rows,
            "biggest_gaps": [g["dimension"] for g in gaps[:3]],
            "meta": meta}
