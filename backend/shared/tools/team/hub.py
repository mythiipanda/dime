import asyncio as _asyncio
import sys
from typing import Any

from langchain_core.tools import tool


def _pkg():
    return sys.modules[__package__]


def _preview_rating_row(season: str, tid: int, full_by_id: dict[int, str]) -> dict[str, float]:
    _row = None
    try:
        from ... import store as _store

        _con = _store.connect()
        try:
            _row = _con.execute(
                "SELECT OFF_RATING, DEF_RATING, PACE FROM silver_team_ratings"
                " WHERE _season = ? AND TEAM_ID = ?",
                [season, tid],
            ).fetchone()
            if not _row and full_by_id.get(tid):
                _row = _con.execute(
                    "SELECT OFF_RATING, DEF_RATING, PACE FROM silver_team_ratings"
                    " WHERE _season = ? AND TEAM_NAME = ?",
                    [season, full_by_id[tid]],
                ).fetchone()
        finally:
            _con.close()
    except Exception:
        _row = None
    if _row and _row[0] and _row[1] and _row[2]:
        return {"OFF_RATING": float(_row[0]), "DEF_RATING": float(_row[1]),
                "PACE": float(_row[2])}
    return {"OFF_RATING": 114.0, "DEF_RATING": 114.0, "PACE": 99.0}


def _preview_monte_carlo(ra: dict[str, float], rb: dict[str, float], sims: int) -> tuple[float, float, float, str]:
    import random as _random

    poss = ((ra["PACE"] or 99.0) + (rb["PACE"] or 99.0)) / 2
    exp_a = poss / 100 * (ra["OFF_RATING"] + rb["DEF_RATING"]) / 2
    exp_b = poss / 100 * (rb["OFF_RATING"] + ra["DEF_RATING"]) / 2
    wins_a = 0
    tot = 0.0
    marg = 0.0
    for _ in range(sims):
        sa = _random.gauss(exp_a, 12)
        sb = _random.gauss(exp_b, 12)
        wins_a += sa > sb
        tot += sa + sb
        marg += sa - sb
    win_pct_a = round(wins_a / sims, 3)
    proj_total = round(tot / sims, 1)
    spread_a = round(marg / sims, 1)
    gap = abs(win_pct_a - 0.5)
    confidence = ("low \u2014 near coin flip" if gap < 0.05 else
                  "moderate" if gap < 0.15 else "high")
    return win_pct_a, proj_total, spread_a, confidence


@tool(description='Side-by-side preview of two teams. Names, abbrevs, or ids. One call.')
async def get_preview(
    a: str, b: str, season: str | None = None, home_abbrev: str = "",
) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    from ..league import get_standings, get_win_prob

    async def one(who: str) -> dict[str, Any]:
        tid = pkg.coerce_team_id(who)
        hub = await pkg.get_team_hub.ainvoke({"team_id": tid, "season": season})
        lineups = await pkg.get_lineups.ainvoke({"team_id": tid, "season": season})
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
            {"team_a": pkg._abbrev(a), "team_b": pkg._abbrev(b), "season": season,
             "home_abbrev": home_abbrev}),
        get_standings.ainvoke({"season": season}),
    )
    sims = 2000
    try:
        from nba_api.stats.static import teams as _static_teams

        full_by_id = {t["id"]: t["full_name"] for t in _static_teams.get_teams()}
    except Exception:
        full_by_id = {}
    ra = _preview_rating_row(season, pkg.coerce_team_id(a), full_by_id)
    rb = _preview_rating_row(season, pkg.coerce_team_id(b), full_by_id)
    win_pct_a, proj_total, spread_a, confidence = _preview_monte_carlo(ra, rb, sims)
    prob_rows = prob.get("rows", {}) or {}
    return {"tool": "get_preview", "ok": True,
            "rows": {"a": left, "b": right,
                     "win_prob": prob_rows.get("win_prob", prob_rows),
                     "elo_a": prob_rows.get("elo_a"),
                     "elo_b": prob_rows.get("elo_b"),
                     "standings_rows": len(st.get("rows", [])),
                     "win_pct_a": win_pct_a,
                     "projected_total": proj_total,
                     "spread_a": spread_a,
                     "sims": sims},
            "meta": {"source": "nba_api+warehouse", "season": season,
                     "sim_note": "Monte Carlo over blended ratings scores "
                     "(poss=mean pace; exp=poss/100*mean(own OFF, opp DEF)); "
                     "sim runs neutral court; ELO win_prob respects "
                     "home_abbrev when passed; normal std 12",
                     "confidence": confidence,
                     "injuries_ignored": True}}


def _validate_team_season_rows(
    games: list[dict[str, Any]],
    resolved_team_id: int,
    resolved_season: str,
) -> tuple[int, int, int] | None:
    game_ids: set[str] = set()
    wins = losses = total_points = 0
    for game in games:
        game_id = str(game.get("Game_ID") or "").strip()
        row_team_id = game.get("Team_ID")
        row_season = game.get("_season")
        result = str(game.get("WL") or "").strip().upper()
        raw_points = game.get("PTS")
        if (not game_id or game_id in game_ids
                or str(row_team_id) != str(resolved_team_id)
                or str(row_season) != resolved_season
                or result not in {"W", "L"}
                or isinstance(raw_points, bool)):
            return None
        try:
            points = int(raw_points)
        except (TypeError, ValueError, OverflowError):
            return None
        if points != raw_points:
            return None
        game_ids.add(game_id)
        wins += result == "W"
        losses += result == "L"
        total_points += points
    return wins, losses, total_points


@tool(description=(
    "Available warehouse regular-season summary for one resolved team and "
    "season: games, wins, losses, total points, and points per game. "
    "Uses all matching silver_hist_gamelogs rows; warehouse completeness "
    "is not guaranteed. Requires an explicit regular-season task scope."))
def get_team_season_summary(
    team_id: str | int | None = None,
    season: str | None = None,
    period_scope: str = "unspecified",
) -> dict[str, Any]:
    pkg = _pkg()
    if period_scope != "regular_season":
        return {"tool": "get_team_season_summary", "ok": False,
                "error": "only explicit regular-season scope is supported"}
    if team_id is None:
        return {"tool": "get_team_season_summary", "ok": False,
                "error": "a resolved team is required"}
    try:
        resolved_team_id = pkg.coerce_team_id(team_id)
        resolved_season = pkg.resolve_season(season)
    except (TypeError, ValueError):
        return {"tool": "get_team_season_summary", "ok": False,
                "error": "team and season scope could not be resolved"}

    games = pkg._hist_team_games(resolved_team_id, resolved_season)
    if not games:
        return {"tool": "get_team_season_summary", "ok": False,
                "error": "regular-season rows are unavailable for this team and season"}

    validated = _validate_team_season_rows(games, resolved_team_id, resolved_season)
    if validated is None:
        return {"tool": "get_team_season_summary", "ok": False,
                "error": "warehouse rows do not establish team-game summary fields"}
    wins, losses, total_points = validated
    count = len(games)
    from ... import store as _store

    return {
        "tool": "get_team_season_summary",
        "ok": True,
        "rows": [{
            "TEAM_ID": resolved_team_id,
            "SEASON": resolved_season,
            "PERIOD_SCOPE": period_scope,
            "GAMES": count,
            "WINS": wins,
            "LOSSES": losses,
            "PTS": total_points,
            "PPG": total_points / count,
        }],
        "meta": {
            "source": "warehouse:silver_hist_gamelogs",
            **_store.warehouse_identity(),
            "season": resolved_season,
            "coverage": (
                "Summary of rows available for this team, season, and "
                "regular-season source; season completeness is unverified."),
            "data_note": "Values describe available warehouse rows only.",
        },
    }


@tool(description='Game log plus roster for one team id. Warehouse first.')
def get_team_hub(team_id: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    team_id = pkg.coerce_team_id(team_id)
    games, meta = pkg._warehouse_or_live(
        "silver_team_games", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: pkg.nba_stats.team_gamelog(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=pkg.TTL_GAMELOG,
    )
    full_season_rows = False
    if not games and pkg.season_static(season) and meta.get("error"):
        hist = pkg._hist_team_games(team_id, season)
        if hist:
            games = hist
            full_season_rows = True
            meta = {"rows": len(games), "cached": True,
                    "source": "warehouse:silver_hist_gamelogs",
                    "season": season, "season_type": "regular-season",
                    "static_season": True,
                    "note": "historical season served from the "
                            "silver_hist_gamelogs regular-season slice "
                            "(same rows silver_team_games is promoted from)"}
    if not full_season_rows:
        try:
            full_season_rows = bool(games) and len(games) >= int(
                meta.get("rows", 0) or 0)
        except (TypeError, ValueError):
            full_season_rows = False
    summary = pkg._team_game_summary(games, full_season_rows)
    roster, _ = pkg._warehouse_or_live(
        "silver_rosters", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: pkg.nba_stats.team_roster(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=pkg.TTL_ROSTER,
    )
    if not roster or "PLAYER" not in (roster[0] if roster else {}):
        from ... import store as _store
        from ..gamelog import _team_abbr as _tabbr_fn

        abbr, _full = _tabbr_fn(team_id)
        frame = _store.read_frame(
            "silver_player_season", '"TEAM" = ? AND _season = ?',
            [abbr, season])
        if frame.height:
            roster = sorted(
                ({"PLAYER": r.get("PLAYER"), "TEAM": r.get("TEAM"),
                  "AGE": r.get("AGE"), "GP": r.get("GP"),
                  "PPG": r.get("PPG"), "RPG": r.get("RPG"),
                  "APG": r.get("APG")}
                 for r in frame.to_dicts()),
                key=lambda r: -(r.get("GP") or 0))
    return {
        "tool": "get_team_hub", "ok": True,
        "rows": {"roster": roster, "summary": summary, "games": games},
        "meta": meta,
    }


@tool(description='Scoreboard for one date. Date format is MM/DD/YYYY.')
def get_games_on_date(game_date: str, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    past = pkg.is_past_game_date(game_date)
    rows, meta = pkg._warehouse_or_live(
        "silver_scoreboard", "_season = ? AND _entity = ?",
        [season, f"date:{game_date}"],
        lambda: pkg.nba_stats.scoreboard(game_date, season), season,
        entity=f"date:{game_date}", live_first=(not past),
        ttl_s=(pkg.TTL_SCOREBOARD_PAST if past else None),
    )
    for r in rows:
        gid = r.get("GAME_ID")
        if gid:
            r["LINKS"] = pkg.game_links(str(gid))
    return {"tool": "get_games_on_date", "ok": True, "rows": rows, "meta": meta}


@tool(description='Traditional boxscore player stats for one game id.')
def get_boxscore(game_id: str, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    rows, meta = pkg._warehouse_or_live(
        "silver_boxscores", "_season = ? AND _entity = ?",
        [season, f"game:{game_id}"],
        lambda: pkg.nba_stats.boxscore_traditional(game_id, season), season,
        entity=f"game:{game_id}", ttl_s=pkg.TTL_BOX,
    )
    return {"tool": "get_boxscore", "ok": True, "rows": rows,
            "meta": {**meta, "links": pkg.game_links(game_id)}}


@tool(description='Post-game recap data: boxscore top five plus team totals.')
def get_recap(game_id: str, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    res = pkg.nba_stats.boxscore_traditional(game_id, season)
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
                     "rows": len(top), "cached": False,
                     "links": pkg.game_links(game_id)}}
