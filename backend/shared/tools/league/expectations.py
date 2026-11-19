from typing import Any

from langchain_core.tools import tool

from .._core import coerce_team_id
from ._helpers import _owned_connection, _pkg, _warehouse_tables


def _team_lookup() -> dict[int, dict[str, str]]:
    from nba_api.stats.static import teams as _teams

    return {t["id"]: {"abbrev": t["abbreviation"], "name": t["full_name"]}
            for t in _teams.get_teams()}


def _season_end_year(season: str) -> int:
    return int(str(season).split("-")[0]) + 1


def _projection_rows(con, team_abbr: str) -> list[dict[str, Any]]:
    rows = con.execute(
        """SELECT _season, PROJECTED_WINS, PROJECTED_LOSSES,
                  MAKE_PLAYOFFS_PCT, WIN_TITLE_PCT, RATING,
                  PROJECTION_MODEL, PROJECTION_SOURCE, _fetched_at
           FROM silver_preseason_projections
           WHERE TEAM = ? ORDER BY _season""",
        [team_abbr]).fetchall()
    cols = ["season", "projected_wins", "projected_losses",
            "make_playoffs_pct", "win_title_pct", "power_index_rating",
            "model", "projection_source", "fetched_at"]
    return [dict(zip(cols, r)) for r in rows]


def _hist_net_rating(con, season_year: int, team_id: int) -> float | None:
    tables = _warehouse_tables(con)
    if "silver_hist_gamelogs" not in tables:
        return None
    row = con.execute(
        """WITH ours AS (
             SELECT game_id, pts, fga, fta, tov, oreb
             FROM silver_hist_gamelogs
             WHERE season = ? AND team_id = ?
           ), opp AS (
             SELECT g.game_id, g.pts AS opp_pts,
                    g.fga AS opp_fga, g.fta AS opp_fta,
                    g.tov AS opp_tov, g.oreb AS opp_oreb
             FROM silver_hist_gamelogs g
             JOIN ours o ON g.game_id = o.game_id AND g.team_id != ?
             WHERE g.season = ?
           )
           SELECT sum(o.pts), sum(p.opp_pts),
                  sum((o.fga + 0.44 * o.fta + o.tov - o.oreb +
                       p.opp_fga + 0.44 * p.opp_fta + p.opp_tov -
                       p.opp_oreb) / 2.0)
           FROM ours o JOIN opp p ON o.game_id = p.game_id""",
        [season_year, team_id, team_id, season_year]).fetchone()
    if not row or row[0] is None or not row[2]:
        return None
    return round(100.0 * (row[0] - row[1]) / row[2], 2)


def _actuals(con, season_str: str, team_id: int) -> dict[str, Any]:
    end_year = _season_end_year(season_str)
    out: dict[str, Any] = {}
    if "silver_hist_standings" in _warehouse_tables(con):
        row = con.execute(
            """SELECT wins, losses, win_pct
               FROM silver_hist_standings
               WHERE season = ? AND team_id = ?""",
            [end_year, team_id]).fetchone()
        if row and row[0] is not None:
            out = {"actual_wins": row[0], "actual_losses": row[1],
                   "win_pct": row[2], "status": "completed",
                   "net_rating": _hist_net_rating(con, end_year, team_id)}
            return out
    if "silver_standings" in _warehouse_tables(con):
        row = con.execute(
            """SELECT "WINS", "LOSSES", "WinPCT"
               FROM silver_standings WHERE "TeamID" = ?""",
            [team_id]).fetchone()
        if row and row[0] is not None:
            gp = (row[0] or 0) + (row[1] or 0)
            out = {"actual_wins": row[0], "actual_losses": row[1],
                   "win_pct": row[2], "status": "in_progress",
                   "games_played": gp,
                   "pace_wins": round(82.0 * row[0] / gp, 1) if gp else None}
            if "silver_team_ratings" in _warehouse_tables(con):
                rt = con.execute(
                    """SELECT NET_RATING FROM silver_team_ratings
                       WHERE TEAM_ID = ?""", [team_id]).fetchone()
                if rt:
                    out["net_rating"] = rt[0]
    return out


@tool(description=(
    "Actual or season-to-date record and net rating versus preseason "
    "expectations (projected win total, playoff/title odds) for one team, "
    "per season. Warehouse-backed: silver_preseason_projections plus "
    "standings/ratings tables. Pass a team id, abbreviation or name; "
    "optional season like '2025-26', else the most recent seasons."))
def get_expectations(team_id: object = None, team: str = "",
                     season: str | None = None,
                     seasons: int = 3) -> dict[str, Any]:
    _pkg()
    try:
        tid = coerce_team_id(team_id if team_id is not None else team)
    except ValueError as exc:
        return {"tool": "get_expectations", "ok": False, "error": str(exc)}
    info = _team_lookup().get(tid)
    if not info:
        return {"tool": "get_expectations", "ok": False,
                "error": f"unknown team id {tid}"}
    try:
        seasons = max(1, min(int(seasons or 3), 10))
    except (TypeError, ValueError):
        seasons = 3
    with _owned_connection(None, read_only=True) as con:
        tables = _warehouse_tables(con)
        if "silver_preseason_projections" not in tables:
            return {"tool": "get_expectations", "ok": False,
                    "error": "silver_preseason_projections not in "
                             "warehouse; run seed_recent_market.py to "
                             "load preseason projections."}
        projs = _projection_rows(con, info["abbrev"])
        if season:
            want = _pkg().resolve_season(season)
            projs = [p for p in projs if p["season"] == want]
        else:
            projs = projs[-seasons:]
        rows = []
        for p in projs:
            row = {"team": info["name"], "abbrev": info["abbrev"], **p}
            act = _actuals(con, p["season"], tid)
            row.update(act)
            if row.get("actual_wins") is not None \
                    and p.get("projected_wins") is not None:
                ref = row.get("pace_wins") \
                    if row.get("status") == "in_progress" \
                    else row["actual_wins"]
                if ref is not None:
                    row["wins_vs_projection"] = round(
                        ref - p["projected_wins"], 1)
            rows.append(row)
    meta = {"source": "warehouse",
            "tables": ["silver_preseason_projections",
                       "silver_hist_standings", "silver_standings",
                       "silver_hist_gamelogs", "silver_team_ratings"],
            "note": "net_rating is per 100 possessions; historical "
                    "seasons use possessions estimated from gamelogs"}
    if not rows:
        meta["warning"] = "no preseason projections found for team/season"
    return {"tool": "get_expectations", "ok": True,
            "rows": rows, "meta": meta}
