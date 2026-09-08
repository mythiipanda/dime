"""Team desk. Hubs, games, boxscores, lineups, dossiers, recaps."""

from typing import Any
import asyncio as _asyncio
from langchain_core.tools import tool

from ..sources import nba_stats
from ._core import SEASON, _warehouse_or_live, coerce_team_id


def _abbrev(who: str) -> str:
    try:
        tid = coerce_team_id(who)
    except ValueError:
        return str(who).upper()
    from nba_api.stats.static import teams

    for t in teams.get_teams():
        if t.get("id") == tid:
            return t.get("abbreviation", str(who).upper())
    return str(who).upper()


@tool
async def get_preview(
    a: str, b: str, season: str = SEASON,
) -> dict[str, Any]:
    """Side-by-side preview of two teams. Names, abbrevs, or ids. One call."""
    from .league import get_standings, get_win_prob

    async def one(who: str) -> dict[str, Any]:
        tid = coerce_team_id(who)
        hub = await get_team_hub.ainvoke({"team_id": tid, "season": season})
        lineups = await get_lineups.ainvoke({"team_id": tid, "season": season})
        top = (lineups.get("rows", []) or [{}])[0]
        return {
            "name": who,
            "team_id": tid,
            "games": len(hub.get("rows", {}).get("games", [])),
            "top_lineup": top.get("GROUP_NAME", ""),
            "top_lineup_pm": top.get("PLUS_MINUS", 0),
        }

    (left, right), prob, st = await _asyncio.gather(
        _asyncio.gather(one(a), one(b)),
        get_win_prob.ainvoke(
            {"team_a": _abbrev(a), "team_b": _abbrev(b), "season": season}),
        get_standings.ainvoke({"season": season}),
    )
    return {"tool": "get_preview", "ok": True,
            "rows": {"a": left, "b": right,
                     "win_prob": prob.get("rows", {}),
                     "standings_rows": len(st.get("rows", []))},
            "meta": {"source": "nba_api+warehouse", "season": season}}


@tool
def get_team_hub(team_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Game log plus roster for one team id. Warehouse first."""
    team_id = coerce_team_id(team_id)
    games, meta = _warehouse_or_live(
        "silver_team_games", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.team_gamelog(team_id, season), season,
        entity=f"team:{team_id}", live_first=True,
    )
    roster, _ = _warehouse_or_live(
        "silver_rosters", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.team_roster(team_id, season), season,
        entity=f"team:{team_id}", live_first=True,
    )
    return {
        "tool": "get_team_hub", "ok": True,
        "rows": {"games": games, "roster": roster}, "meta": meta,
    }


@tool
def get_games_on_date(game_date: str, season: str = SEASON) -> dict[str, Any]:
    """Scoreboard for one date. Date format is MM/DD/YYYY."""
    rows, meta = _warehouse_or_live(
        "silver_scoreboard", "_season = ? AND _entity = ?",
        [season, f"date:{game_date}"],
        lambda: nba_stats.scoreboard(game_date, season), season,
        entity=f"date:{game_date}", live_first=True,
    )
    return {"tool": "get_games_on_date", "ok": True, "rows": rows, "meta": meta}


@tool
def get_boxscore(game_id: str, season: str = SEASON) -> dict[str, Any]:
    """Traditional boxscore player stats for one game id."""
    rows, meta = _warehouse_or_live(
        "silver_boxscores", "_season = ? AND _entity = ?",
        [season, f"game:{game_id}"],
        lambda: nba_stats.boxscore_traditional(game_id, season), season,
        entity=f"game:{game_id}", live_first=True,
    )
    return {"tool": "get_boxscore", "ok": True, "rows": rows, "meta": meta}


@tool
def get_lineups(team_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Five-man lineup stats for one team id, sorted by minutes."""
    team_id = coerce_team_id(team_id)
    rows, meta = _warehouse_or_live(
        "silver_lineups", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.lineups(team_id, season), season,
        entity=f"team:{team_id}", live_first=True,
    )
    return {"tool": "get_lineups", "ok": True, "rows": rows, "meta": meta}


@tool
def get_scouting_report(team_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """One-call dossier: record, roster, lineups, leaders context."""
    team_id = coerce_team_id(team_id)
    games, _ = _warehouse_or_live(
        "silver_team_games", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.team_gamelog(team_id, season), season,
        entity=f"team:{team_id}", live_first=True,
    )
    lineups, _ = _warehouse_or_live(
        "silver_lineups", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.lineups(team_id, season), season,
        entity=f"team:{team_id}", live_first=True,
    )
    wins = sum(1 for g in games if g.get("WL") == "W")
    top_lineup = (lineups or [{}])[0]
    return {"tool": "get_scouting_report", "ok": True,
            "rows": {"record": f"{wins}-{len(games) - wins}",
                     "games_sample": len(games),
                     "top_lineup": {
                         "GROUP_NAME": top_lineup.get("GROUP_NAME"),
                         "MIN": top_lineup.get("MIN"),
                         "PLUS_MINUS": top_lineup.get("PLUS_MINUS")}},
            "meta": {"source": "nba_api", "season": season}}


@tool
def get_recap(game_id: str, season: str = SEASON) -> dict[str, Any]:
    """Post-game recap data: boxscore top five plus team totals."""
    res = nba_stats.boxscore_traditional(game_id, season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_recap", "ok": False,
                "error": res.error or "empty upstream response"}
    try:
        name_col = next((c for c in ("PLAYER_NAME", "nameI") if c in res.frame.columns),
                        res.frame.columns[9])
        team_col = next((c for c in ("TEAM_ABBREVIATION", "teamTricode") if c in res.frame.columns),
                        res.frame.columns[2])
        pts_col = next((c for c in ("PTS", "points") if c in res.frame.columns),
                       res.frame.columns[-2])
        reb_col = next((c for c in ("REB", "reboundsTotal") if c in res.frame.columns),
                       res.frame.columns[-4])
        ast_col = next((c for c in ("AST", "assists") if c in res.frame.columns),
                       res.frame.columns[-3])
        top = (res.frame.sort(pts_col, descending=True).head(5)
               .select(name_col, team_col, pts_col, reb_col, ast_col)
               .rename({name_col: "PLAYER", team_col: "TEAM",
                        pts_col: "PTS", reb_col: "REB", ast_col: "AST"})
               .to_dicts())
    except Exception as exc:
        return {"tool": "get_recap", "ok": False, "error": str(exc)[:160]}
    return {"tool": "get_recap", "ok": True, "rows": top,
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": len(top), "cached": False}}
