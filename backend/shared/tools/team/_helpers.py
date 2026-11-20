import sys
from typing import Any


def _pkg():
    return sys.modules[__package__]


def _team_game_seasons() -> set[str] | None:
    try:
        from shared.coverage import table_seasons as _seasons
    except Exception:
        return None
    try:
        return (set(_seasons("silver_team_games"))
                | set(_seasons("silver_hist_gamelogs")))
    except Exception:
        return None


_HIST_TEAM_GAMES_SQL = """
SELECT
  g.team_id AS "Team_ID",
  g.game_id AS "Game_ID",
  UPPER(STRFTIME(CAST(g.game_date AS DATE), '%b %d, %Y')) AS "GAME_DATE",
  CAST(g.game_date AS DATE) AS "_sort_date",
  g.matchup AS "MATCHUP",
  g.wl AS "WL",
  SUM(CASE WHEN g.wl = 'W' THEN 1 ELSE 0 END) OVER w AS "W",
  SUM(CASE WHEN g.wl = 'L' THEN 1 ELSE 0 END) OVER w AS "L",
  CAST(SUM(CASE WHEN g.wl = 'W' THEN 1 ELSE 0 END) OVER w AS DOUBLE) /
    CAST(ROW_NUMBER() OVER w AS DOUBLE) AS "W_PCT",
  g.min AS "MIN",
  g.fgm AS "FGM",
  g.fga AS "FGA",
  g.fg_pct AS "FG_PCT",
  g.fg3m AS "FG3M",
  g.fg3a AS "FG3A",
  g.fg3_pct AS "FG3_PCT",
  g.ftm AS "FTM",
  g.fta AS "FTA",
  g.ft_pct AS "FT_PCT",
  g.oreb AS "OREB",
  g.dreb AS "DREB",
  g.reb AS "REB",
  g.ast AS "AST",
  g.stl AS "STL",
  g.blk AS "BLK",
  g.tov AS "TOV",
  g.pf AS "PF",
  g.pts AS "PTS",
  o.pts AS "OPP_PTS",
  'sportsdataverse' AS "_source",
  ? AS "_season",
  ? AS "_fetched_at",
  'team:' || CAST(g.team_id AS VARCHAR) AS "_entity"
FROM silver_hist_gamelogs g
LEFT JOIN silver_hist_gamelogs o
  ON o._season = g._season AND o.game_id = g.game_id
 AND o.team_id != g.team_id AND o.season_type = 'regular-season'
WHERE g._season = ? AND (g.team_id = ? OR g.team_abbreviation = ?)
  AND g.season_type = 'regular-season'
WINDOW w AS (PARTITION BY g.team_id ORDER BY CAST(g.game_date AS DATE), g.game_id
             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
ORDER BY "_sort_date", g.game_id
"""


def _hist_team_games(team_id: int, season: str) -> list[dict[str, Any]]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    from ... import store as _store
    try:
        con = _store.connect(read_only=True)
        try:
            tables = {r[0]
                      for r in con.execute("SHOW TABLES").fetchall()}
            if "silver_hist_gamelogs" not in tables:
                return []
            cols = {r[1] for r in con.execute(
                "PRAGMA table_info(silver_hist_gamelogs)").fetchall()}
            need = {"team_id", "team_abbreviation", "game_id", "game_date",
                    "matchup", "wl", "pts", "fga", "fta", "season_type"}
            if not need <= cols:
                return []
            import datetime as _dt
            fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
            cur = con.execute(_HIST_TEAM_GAMES_SQL,
                              [season, fetched_at, season, team_id,
                               pkg._abbrev(str(team_id))])
            names = [d[0] for d in cur.description]
            return [dict(zip(names, row)) for row in cur.fetchall()]
        finally:
            con.close()
    except Exception:
        return []


def _hist_game_log_rows(team_id: int, season: str,
                        limit: int) -> list[dict[str, Any]]:
    pkg = _pkg()
    out: list[dict[str, Any]] = []
    for _h in reversed(pkg._hist_team_games(team_id, season)):
        if not isinstance(_h, dict):
            continue
        _wl = str(_h.get("WL") or "").strip().upper()
        out.append({
            "game_id": str(_h.get("Game_ID") or ""),
            "date": str(_h.get("GAME_DATE") or ""),
            "matchup": str(_h.get("MATCHUP") or ""),
            "wl": _wl or None,
            "pts": _h.get("PTS"), "opp_pts": _h.get("OPP_PTS"),
            "reb": _h.get("REB"), "ast": _h.get("AST"),
            "stl": _h.get("STL"), "blk": _h.get("BLK"),
            "tov": _h.get("TOV"),
        })
        if len(out) >= limit:
            break
    return out


def _team_game_window(tid: int, abbr: str, season: str,
                      playoffs: bool, hist: bool) -> dict[str, Any]:
    try:
        from ... import store as _store
        con = _store.connect(read_only=True)
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            if playoffs:
                if "silver_playoffs" not in tables:
                    return {}
                row = con.execute(
                    "SELECT COUNT(*), MIN(coalesce(try_strptime(GAME_DATE, '%b %d, %Y'),"
                    " try_strptime(GAME_DATE, '%Y-%m-%d'))),"
                    " MAX(coalesce(try_strptime(GAME_DATE, '%b %d, %Y'),"
                    " try_strptime(GAME_DATE, '%Y-%m-%d')))"
                    " FROM silver_playoffs WHERE _season = ?"
                    " AND TEAM_ABBREVIATION = ?",
                    [season, abbr]).fetchone()
            elif hist and "silver_hist_gamelogs" in tables:
                row = con.execute(
                    "SELECT COUNT(*), MIN(CAST(game_date AS DATE)),"
                    " MAX(CAST(game_date AS DATE))"
                    " FROM silver_hist_gamelogs WHERE _season = ?"
                    " AND (team_id = ? OR team_abbreviation = ?)"
                    " AND season_type = 'regular-season'",
                    [season, tid, abbr]).fetchone()
            elif "silver_team_games" in tables:
                row = con.execute(
                    "SELECT COUNT(DISTINCT Game_ID),"
                    " MIN(try_strptime(GAME_DATE, '%b %d, %Y')),"
                    " MAX(try_strptime(GAME_DATE, '%b %d, %Y'))"
                    " FROM silver_team_games WHERE _season = ?"
                    " AND _entity = ?",
                    [season, f"team:{tid}"]).fetchone()
            else:
                return {}
        finally:
            con.close()
    except Exception:
        return {}
    if not row or not row[0]:
        return {}
    return {"season_games": int(row[0]),
            "first_date": None if row[1] is None else str(row[1]),
            "last_date": None if row[2] is None else str(row[2])}


def _abbrev(who: str) -> str:
    pkg = _pkg()
    try:
        tid = pkg.coerce_team_id(who)
    except ValueError:
        return str(who).upper()
    from nba_api.stats.static import teams

    for t in teams.get_teams():
        if t.get("id") == tid:
            return t.get("abbreviation", str(who).upper())
    return str(who).upper()


def _num(x: Any) -> float | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _cell(row: dict[str, Any], *keys: str) -> float | None:
    for k in keys:
        v = _num(row.get(k))
        if v is not None:
            return v
    return None


def _team_game_summary(games: list[dict[str, Any]],
                       full_season: bool) -> dict[str, Any]:
    wins = losses = 0
    pts = 0.0
    pts_games = 0
    ts_pts = ts_fga = ts_fta = 0.0
    ts_games = 0
    for g in games:
        wl = str(g.get("WL", g.get("wl", ""))).strip().upper()
        if wl.startswith("W"):
            wins += 1
        elif wl.startswith("L"):
            losses += 1
        p = _cell(g, "PTS", "pts")
        if p is not None:
            pts += p
            pts_games += 1
        a2 = _cell(g, "FGA", "fga")
        a3 = _cell(g, "FTA", "fta")
        if p is not None and a2 is not None and a3 is not None:
            ts_pts += p
            ts_fga += a2
            ts_fta += a3
            ts_games += 1
    out: dict[str, Any] = {
        "games": len(games),
        "wins": wins,
        "losses": losses,
        "covers_full_season": bool(full_season and games),
    }
    if pts_games:
        out["ppg"] = round(pts / pts_games, 1)
        out["ppg_games"] = pts_games
    if ts_games:
        denom = 2 * (ts_fga + 0.44 * ts_fta)
        out["ts_pct"] = round(100 * ts_pts / denom, 1) if denom > 0 else None
        out["ts_pct_games"] = ts_games
    return out


def game_links(game_id: str) -> dict[str, str]:
    return {"watch": f"https://www.nba.com/game/{game_id}"}


def _sample_tier(minutes: object) -> tuple[str, int]:
    return _pkg().sample_tier(minutes)


def _std_context(team_id: object, season: str,
                 games: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    pkg = _pkg()
    static = pkg.season_static(season)
    hist = pkg._hist_team_games(team_id, season)
    if hist:
        gp = len(hist)
    elif games:
        gp = len(games)
    else:
        gp = None
    prior = None
    prior_season = pkg.last_completed_season()
    if prior_season and prior_season != season:
        prior_games = pkg._hist_team_games(team_id, prior_season)
        if prior_games:
            wins = sum(1 for g in prior_games
                       if str(g.get("WL", g.get("wl", ""))).strip().upper().startswith("W"))
            prior = {"season": prior_season,
                     "games_played": len(prior_games),
                     "wins": wins,
                     "losses": len(prior_games) - wins,
                     "w_pct": round(wins / len(prior_games), 3)}
    meta = pkg.season_to_date_meta(season, gp, prior)
    if static and not meta.get("small_sample"):
        return None
    return meta
