
from typing import Any
import asyncio as _asyncio
from dataclasses import dataclass
from langchain_core.tools import tool

from ..sources import nba_stats
from ._core import TTL_BOX, TTL_GAMELOG, TTL_PBPSTATS, TTL_ROSTER, TTL_SCOREBOARD_PAST, _warehouse_or_live, coerce_team_id, is_past_game_date, sample_tier, season_static, last_completed_season, resolve_season


def _team_game_seasons() -> set[str] | None:
    try:
        from v2.adapters.coverage import table_seasons as _seasons
    except Exception:
        return None
    try:
        return (set(_seasons("silver_team_games"))
                | set(_seasons("silver_hist_gamelogs")))
    except Exception:
        return None


def _hist_game_log_rows(team_id: int, season: str,
                        limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for _h in reversed(_hist_team_games(team_id, season)):
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
        from .. import store as _store
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
    a: str, b: str, season: str | None = None, home_abbrev: str = "",
) -> dict[str, Any]:
    """Side-by-side preview of two teams. Names, abbrevs, or ids. One call."""
    season = resolve_season(season)
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
            {"team_a": _abbrev(a), "team_b": _abbrev(b), "season": season,
             "home_abbrev": home_abbrev}),
        get_standings.ainvoke({"season": season}),
    )
    import random as _random

    _sims = 2000
    try:
        from nba_api.stats.static import teams as _static_teams

        _full_by_id = {t["id"]: t["full_name"] for t in _static_teams.get_teams()}
    except Exception:
        _full_by_id = {}
    _ida = coerce_team_id(a)
    _idb = coerce_team_id(b)

    def _rating_row(_tid: int) -> dict[str, float]:
        _row = None
        try:
            from .. import store as _store

            _con = _store.connect()
            try:
                _row = _con.execute(
                    "SELECT OFF_RATING, DEF_RATING, PACE FROM silver_team_ratings"
                    " WHERE _season = ? AND TEAM_ID = ?",
                    [season, _tid],
                ).fetchone()
                if not _row and _full_by_id.get(_tid):
                    _row = _con.execute(
                        "SELECT OFF_RATING, DEF_RATING, PACE FROM silver_team_ratings"
                        " WHERE _season = ? AND TEAM_NAME = ?",
                        [season, _full_by_id[_tid]],
                    ).fetchone()
            finally:
                _con.close()
        except Exception:
            _row = None
        if _row and _row[0] and _row[1] and _row[2]:
            return {"OFF_RATING": float(_row[0]), "DEF_RATING": float(_row[1]),
                    "PACE": float(_row[2])}
        return {"OFF_RATING": 114.0, "DEF_RATING": 114.0, "PACE": 99.0}

    _ra = _rating_row(_ida)
    _rb = _rating_row(_idb)
    _poss = ((_ra["PACE"] or 99.0) + (_rb["PACE"] or 99.0)) / 2


    _home_edge = 0.0
    _exp_a = _poss / 100 * (_ra["OFF_RATING"] + _rb["DEF_RATING"]) / 2 + _home_edge
    _exp_b = _poss / 100 * (_rb["OFF_RATING"] + _ra["DEF_RATING"]) / 2
    _wins_a = 0
    _tot = 0.0
    _marg = 0.0
    for _i in range(_sims):
        _sa = _random.gauss(_exp_a, 12)
        _sb = _random.gauss(_exp_b, 12)
        _wins_a += _sa > _sb
        _tot += _sa + _sb
        _marg += _sa - _sb
    _win_pct_a = round(_wins_a / _sims, 3)
    _proj_total = round(_tot / _sims, 1)
    _spread_a = round(_marg / _sims, 1)
    _gap = abs(_win_pct_a - 0.5)
    _confidence = ("low — near coin flip" if _gap < 0.05 else
                   "moderate" if _gap < 0.15 else "high")
    prob_rows = prob.get("rows", {}) or {}
    return {"tool": "get_preview", "ok": True,
            "rows": {"a": left, "b": right,
                     "win_prob": prob_rows.get("win_prob", prob_rows),
                     "elo_a": prob_rows.get("elo_a"),
                     "elo_b": prob_rows.get("elo_b"),
                     "standings_rows": len(st.get("rows", [])),
                     "win_pct_a": _win_pct_a,
                     "projected_total": _proj_total,
                     "spread_a": _spread_a,
                     "sims": _sims},
            "meta": {"source": "nba_api+warehouse", "season": season,
                     "sim_note": "Monte Carlo over blended ratings scores "
                     "(poss=mean pace; exp=poss/100*mean(own OFF, opp DEF)); "
                     "sim runs neutral court; ELO win_prob respects "
                     "home_abbrev when passed; normal std 12",
                     "confidence": _confidence,
                     "injuries_ignored": True}}


def _series_date_key(s: object) -> str:
    import datetime as _dt

    raw = str(s or "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return _dt.datetime.strptime(raw.title(), fmt).date().isoformat()
        except (TypeError, ValueError):
            continue
    return raw


def _playoff_series(games: list[dict[str, Any]], a: str,
                    b: str) -> list[dict[str, Any]]:
    """One record per playoff series the two teams played.

    A series is the run of playoff games inside one round; two teams can
    meet at most once per round. Series wins and game wins count different
    things, so the two never share a field.
    """
    by_round: dict[str, list[dict[str, Any]]] = {}
    for game in games:
        if game.get("phase") != "playoffs":
            continue
        code = str(game.get("round_code") or "")
        by_round.setdefault(code, []).append(game)
    records: list[dict[str, Any]] = []
    for code in sorted(by_round):
        round_games = by_round[code]
        tally = {a: sum(1 for g in round_games if g.get("winner") == a),
                 b: sum(1 for g in round_games if g.get("winner") == b)}
        undecided = len(round_games) - tally[a] - tally[b]
        winner = (a if tally[a] > tally[b]
                  else (b if tally[b] > tally[a] else None))
        records.append({
            "round_code": code,
            "round": str(round_games[0].get("round") or ""),
            "games": len(round_games),
            "games_undecided": undecided,
            "games_won": tally,
            "winner": winner,
        })
    return records


@tool
def get_team_game_log(team: str, limit: int = 10,
                      playoffs: bool = False,
                      season: str | None = None) -> dict[str, Any]:
    """A team's recent games, most recent first: date, matchup, W/L,
    team and opponent points, plus team REB/AST/STL/BLK/TOV. Use for
    "show me the <team> last N games" asks - this is the TEAM game log,
    never search_game_logs (that tool is per-player and its team_wide
    mode returns match counts, not games). team: name, nickname,
    abbreviation, or id. limit: 1-30. playoffs: read silver_playoffs
    (team-level playoff rows) instead of the regular-season table.
    Warehouse only; 2025-26 only.
    """
    season = resolve_season(season)
    from .. import store as _store

    try:
        tid = coerce_team_id(team)
    except ValueError as exc:
        return {"tool": "get_team_game_log", "ok": False, "error": str(exc)}
    try:
        limit = max(1, min(int(limit or 10), 30))
    except (TypeError, ValueError):
        limit = 10
    abbr = _abbrev(team)
    _covered = _team_game_seasons()
    if _covered and not playoffs and season not in _covered:
        return {"tool": "get_team_game_log", "ok": False,
                "error": (f"no regular-season games found for {abbr} "
                          f"in {season}. Team game coverage: "
                          f"{', '.join(sorted(_covered))}.")}

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        games: list[dict[str, Any]] = []
        if not playoffs and "silver_team_games" in tables:
            rows = con.execute(
                """SELECT g.Game_ID, g.GAME_DATE, g.MATCHUP, g.WL,
                          g.PTS, o.PTS, g.REB, g.AST, g.STL, g.BLK, g.TOV
                   FROM silver_team_games g
                   LEFT JOIN silver_team_games o
                     ON o._season = g._season AND o.Game_ID = g.Game_ID
                    AND o._entity != g._entity
                   WHERE g._season = ? AND g._entity = ?
                   ORDER BY strptime(g.GAME_DATE, '%b %d, %Y') DESC
                   LIMIT ?""",
                [season, f"team:{tid}", limit * 4],
            ).fetchall()
            seen: set[str] = set()
            for (gid, gdate, matchup, wl, pts, opp_pts, reb, ast, stl,
                 blk, tov) in rows:
                if str(gid) in seen:
                    continue
                seen.add(str(gid))
                games.append({
                    "game_id": str(gid), "date": str(gdate),
                    "matchup": str(matchup),
                    "wl": str(wl).upper() if wl else None,
                    "pts": pts, "opp_pts": opp_pts, "reb": reb,
                    "ast": ast, "stl": stl, "blk": blk, "tov": tov,
                })
                if len(games) >= limit:
                    break
        elif playoffs and "silver_playoffs" in tables:
            rows = con.execute(
                """SELECT g.GAME_ID, g.GAME_DATE, g.MATCHUP, g.WL,
                          g.PTS, o.PTS, g.REB, g.AST, g.STL, g.BLK, g.TOV
                   FROM silver_playoffs g
                   LEFT JOIN silver_playoffs o
                     ON o._season = g._season AND o.GAME_ID = g.GAME_ID
                    AND o.TEAM_ABBREVIATION != g.TEAM_ABBREVIATION
                   WHERE g._season = ? AND g.TEAM_ABBREVIATION = ?
                   ORDER BY coalesce(try_strptime(g.GAME_DATE, '%b %d, %Y'),
                                     try_strptime(g.GAME_DATE, '%Y-%m-%d')) DESC
                   LIMIT ?""",
                [season, abbr, limit * 4],
            ).fetchall()
            seen2: set[str] = set()
            for (gid, gdate, matchup, wl, pts, opp_pts, reb, ast, stl,
                 blk, tov) in rows:
                if str(gid) in seen2:
                    continue
                seen2.add(str(gid))
                games.append({
                    "game_id": str(gid), "date": str(gdate),
                    "matchup": str(matchup),
                    "wl": str(wl).upper() if wl else None,
                    "pts": pts, "opp_pts": opp_pts, "reb": reb,
                    "ast": ast, "stl": stl, "blk": blk, "tov": tov,
                })
                if len(games) >= limit:
                    break
        else:
            if playoffs:
                return {"tool": "get_team_game_log", "ok": False,
                        "error": "team game table not present in warehouse"}
    finally:
        con.close()
    _source = "warehouse:silver_team_games"
    _hist_served = False
    if not games and not playoffs and season_static(season):
        _hist = _hist_game_log_rows(tid, season, limit)
        if _hist:
            games = _hist
            _source = "warehouse:silver_hist_gamelogs"
            _hist_served = True
    if not games:
        _suffix = ""
        if _covered:
            _suffix = (" Team game coverage: "
                       + ", ".join(sorted(_covered)) + ".")
        return {"tool": "get_team_game_log", "ok": False,
                "error": f"no {'playoff' if playoffs else 'regular-season'} "
                         f"games found for {abbr} in {season}." + _suffix}
    _window = _team_game_window(tid, abbr, season, playoffs, _hist_served)
    _meta: dict[str, Any] = {
        "season": season, "source": _source,
        "scope": "playoffs" if playoffs else "regular season",
        "returned_games": len(games),
    }
    if _window:
        _total = _window.get("season_games") or 0
        _meta.update(_window)
        _meta["partial_window"] = bool(_total and len(games) < _total)
        _first = _window.get("first_date") or "unknown start"
        _last = _window.get("last_date") or "unknown end"
        _meta["coverage_note"] = (
            f"{abbr} {season} {('playoffs' if playoffs else 'regular season')}: "
            f"{_total} games from {_first} to {_last}; "
            f"showing {len(games)} most recent.")
    return {"tool": "get_team_game_log", "ok": True,
            "team": abbr, "games": games, "rows": games, "meta": _meta}


@tool
def get_season_series(team_a: str, team_b: str,
                      season: str | None = None) -> dict[str, Any]:
    """Head-to-head between two TEAMS: every meeting this season, regular
    season and playoffs, with winner and scores when tracked. Use for
    "how did X do against Y", "X vs Y record", "season series"."""
    season = resolve_season(season)
    from .competitive import _resolve_team_abbr
    from nba_api.stats.static import teams as _static_teams

    a = _resolve_team_abbr(team_a)
    b = _resolve_team_abbr(team_b)
    if not a or not b:
        return {"tool": "get_season_series", "ok": False,
                "error": f"could not resolve team(s): {team_a} / {team_b}"}
    if a == b:
        return {"tool": "get_season_series", "ok": False,
                "error": "two different teams needed"}
    ids = {str(t.get("abbreviation") or "").upper(): t.get("id")
           for t in _static_teams.get_teams()}
    id_a, id_b = ids.get(a), ids.get(b)

    from .. import store as _store

    games: list[dict[str, Any]] = []
    reg_source = "silver_team_games"
    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}


        if "silver_team_games" in tables and id_a is not None:
            rows = con.execute(
                """SELECT g.Game_ID, g.GAME_DATE, g.MATCHUP, g.WL, g.PTS,
                          o.PTS
                   FROM silver_team_games g
                   LEFT JOIN silver_team_games o
                     ON o._season = g._season AND o.Game_ID = g.Game_ID
                    AND o._entity = ?
                   WHERE g._season = ? AND g._entity = ?
                     AND g.MATCHUP ILIKE ?""",
                [f"team:{id_b}", season, f"team:{id_a}", f"%{b}%"],
            ).fetchall()
            for gid, gdate, matchup, wl, pts_a, pts_b in rows:
                games.append({
                    "game_id": str(gid), "date": str(gdate),
                    "matchup": str(matchup), "phase": "regular season",
                    "winner": a if str(wl).upper() == "W"
                    else (b if str(wl).upper() == "L" else None),
                    f"{a.lower()}_pts": pts_a,
                    f"{b.lower()}_pts": pts_b,
                })

        if not games and id_a is not None:
            reg_source = "silver_hist_gamelogs"
            for row in _hist_team_games(id_a, season):
                if b not in str(row.get("MATCHUP") or "").upper():
                    continue
                wl = str(row.get("WL") or "").upper()
                games.append({
                    "game_id": str(row.get("Game_ID") or ""),
                    "date": str(row.get("GAME_DATE") or ""),
                    "matchup": str(row.get("MATCHUP") or ""),
                    "phase": "regular season",
                    "winner": a if wl == "W" else (b if wl == "L" else None),
                    f"{a.lower()}_pts": row.get("PTS"),
                    f"{b.lower()}_pts": row.get("OPP_PTS"),
                })


        _ROUND = {"1": "first round", "2": "conference semifinals",
                  "3": "conference finals", "4": "NBA Finals"}
        playoff_source = None
        if "silver_playoffs" in tables and id_a is not None:
            prows = con.execute(
                """SELECT g.GAME_ID, g.GAME_DATE, g.MATCHUP, g.WL, g.PTS,
                          o.PTS
                   FROM silver_playoffs g
                   LEFT JOIN silver_playoffs o
                     ON o._season = g._season AND o.GAME_ID = g.GAME_ID
                    AND o.TEAM_ABBREVIATION = ?
                   WHERE g._season = ? AND g.TEAM_ABBREVIATION = ?
                     AND g.MATCHUP ILIKE ?""",
                [b, season, a, f"%{b}%"],
            ).fetchall()
            for gid, gdate, matchup, wl, pts_a, pts_b in prows:
                rnd = str(gid)[7:8]
                games.append({
                    "game_id": str(gid), "date": str(gdate),
                    "matchup": str(matchup),
                    "phase": "playoffs",
                    "round_code": rnd,
                    "round": _ROUND.get(rnd, "playoffs"),
                    "winner": a if str(wl).upper() == "W"
                    else (b if str(wl).upper() == "L" else None),
                    f"{a.lower()}_pts": pts_a,
                    f"{b.lower()}_pts": pts_b,
                })
            if prows:
                playoff_source = "silver_playoffs"
        if (not playoff_source
                and "silver_playoff_gamelogs" in tables):
            prows = con.execute(
                """SELECT DISTINCT Game_ID, GAME_DATE, MATCHUP, WL
                   FROM silver_playoff_gamelogs
                   WHERE _season = ? AND MATCHUP ILIKE ?""",
                [season, f"{a} % {b}"],
            ).fetchall()
            for gid, gdate, matchup, wl in prows:
                rnd = str(gid)[7:8]
                games.append({
                    "game_id": str(gid), "date": str(gdate),
                    "matchup": str(matchup), "phase": "playoffs",
                    "round_code": rnd,
                    "round": _ROUND.get(rnd, "playoffs"),
                    "winner": a if str(wl).upper() == "W"
                    else (b if str(wl).upper() == "L" else None),
                })
            if prows:
                playoff_source = "silver_playoff_gamelogs"
        playoff_coverage = {
            "silver_playoffs": "silver_playoffs" in tables,
            "silver_playoff_gamelogs": "silver_playoff_gamelogs" in tables,
        }
    finally:
        con.close()


    if not games:
        return {"tool": "get_season_series", "ok": False,
                "error": (f"No games between {a} and {b} found in the "
                          f"dataset (coverage: {season} regular season "
                          f"and playoffs). Do not report a 0-0 record - "
                          f"say the meetings are not in the dataset.")}
    games.sort(key=lambda g: _series_date_key(g["date"]))
    phases = sorted({g["phase"] for g in games})
    games_won = {a: sum(1 for g in games if g.get("winner") == a),
                 b: sum(1 for g in games if g.get("winner") == b)}
    games_by_phase = {phase: sum(1 for g in games if g["phase"] == phase)
                      for phase in phases}
    games_won_by_phase = {
        phase: {a: sum(1 for g in games if g["phase"] == phase
                       and g.get("winner") == a),
                b: sum(1 for g in games if g["phase"] == phase
                       and g.get("winner") == b)}
        for phase in phases}
    undecided = len(games) - games_won[a] - games_won[b]
    series = _playoff_series(games, a, b)
    series_won = {a: sum(1 for s in series if s["winner"] == a),
                  b: sum(1 for s in series if s["winner"] == b)}
    summary = {
        "games": len(games),
        "games_undecided": undecided,
        "games_won": games_won,
        "games_by_phase": games_by_phase,
        "games_won_by_phase": games_won_by_phase,
        "series_played": len(series),
        "series_won": series_won,
        "series": series,
    }
    return {"tool": "get_season_series", "ok": True,
            "rows": {"teams": [a, b], "summary": summary, "games": games},
            "meta": {"source": "warehouse team + playoff gamelogs",
                     "season": season,
                     "regular_season_source": reg_source,
                     "playoff_source": playoff_source,
                     "playoff_tables_present": playoff_coverage,
                     "unscored_games": sorted(
                         g["game_id"] for g in games
                         if f"{a.lower()}_pts" not in g
                         or g.get(f"{a.lower()}_pts") is None),
                     "note": ("games_won counts games; series_won counts "
                              "playoff series, one per round")}}








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
    season = resolve_season(season)
    from .. import store as _store
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
                               _abbrev(str(team_id))])
            names = [d[0] for d in cur.description]
            return [dict(zip(names, row)) for row in cur.fetchall()]
        finally:
            con.close()
    except Exception:
        return []


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


@tool
def get_team_hub(team_id: str | int, season: str | None = None) -> dict[str, Any]:
    """Game log plus roster for one team id. Warehouse first."""
    season = resolve_season(season)
    team_id = coerce_team_id(team_id)
    games, meta = _warehouse_or_live(
        "silver_team_games", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.team_gamelog(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=TTL_GAMELOG,
    )
    full_season_rows = False
    if not games and season_static(season) and meta.get("error"):







        hist = _hist_team_games(team_id, season)
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
    summary = _team_game_summary(games, full_season_rows)
    roster, _ = _warehouse_or_live(
        "silver_rosters", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.team_roster(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=TTL_ROSTER,
    )
    if not roster or "PLAYER" not in (roster[0] if roster else {}):






        try:
            from .. import store as _store
            from .gamelog import _team_abbr as _tabbr_fn
            abbr, _full = _tabbr_fn(team_id)
            frame = _store.read_frame(
                "silver_player_season", '"TEAM" = ? AND _season = ?',
                [abbr, season])
            if frame is not None and frame.height:
                roster = sorted(
                    ({"PLAYER": r.get("PLAYER"), "TEAM": r.get("TEAM"),
                      "AGE": r.get("AGE"), "GP": r.get("GP"),
                      "PPG": r.get("PPG"), "RPG": r.get("RPG"),
                      "APG": r.get("APG")}
                     for r in frame.to_dicts()),
                    key=lambda r: -(r.get("GP") or 0))
        except Exception:
            pass
    return {
        "tool": "get_team_hub", "ok": True,






        "rows": {"roster": roster, "summary": summary, "games": games},
        "meta": meta,
    }


def game_links(game_id: str) -> dict[str, str]:
    return {"watch": f"https://www.nba.com/game/{game_id}"}


@tool
def get_games_on_date(game_date: str, season: str | None = None) -> dict[str, Any]:
    """Scoreboard for one date. Date format is MM/DD/YYYY."""
    season = resolve_season(season)
    past = is_past_game_date(game_date)
    rows, meta = _warehouse_or_live(
        "silver_scoreboard", "_season = ? AND _entity = ?",
        [season, f"date:{game_date}"],
        lambda: nba_stats.scoreboard(game_date, season), season,
        entity=f"date:{game_date}", live_first=(not past),
        ttl_s=(TTL_SCOREBOARD_PAST if past else None),
    )
    for r in rows:
        gid = r.get("GAME_ID")
        if gid:
            r["LINKS"] = game_links(str(gid))
    return {"tool": "get_games_on_date", "ok": True, "rows": rows, "meta": meta}


@tool
def get_boxscore(game_id: str, season: str | None = None) -> dict[str, Any]:
    """Traditional boxscore player stats for one game id."""
    season = resolve_season(season)
    rows, meta = _warehouse_or_live(
        "silver_boxscores", "_season = ? AND _entity = ?",
        [season, f"game:{game_id}"],
        lambda: nba_stats.boxscore_traditional(game_id, season), season,
        entity=f"game:{game_id}", ttl_s=TTL_BOX,
    )
    return {"tool": "get_boxscore", "ok": True, "rows": rows,
            "meta": {**meta, "links": game_links(game_id)}}


def _sample_tier(minutes: object) -> tuple[str, int]:
    return sample_tier(minutes)


def _competitive_lineup_nets(
    team_id: int, season: str,
) -> dict[tuple[int, ...], tuple[float, int]] | None:
    season = resolve_season(season)
    from .. import store as _store

    con = _store.connect()
    try:
        pros = con.execute(
            "SELECT offense_team_id, defense_team_id, points,"
            " off_player_1, off_player_2, off_player_3,"
            " off_player_4, off_player_5,"
            " def_player_1, def_player_2, def_player_3,"
            " def_player_4, def_player_5"
            " FROM silver_hist_possessions"
            " WHERE _season = ?"
            " AND (offense_team_id = ? OR defense_team_id = ?)"
            " AND garbage = 0",
            [season, team_id, team_id],
        ).fetchall()
    finally:
        try:
            con.close()
        except Exception:
            pass
    if not pros:
        return None
    agg: dict[tuple[int, ...], list[float]] = {}
    for row in pros:
        try:
            off_tid, def_tid = row[0], row[1]
            pts = row[2] or 0
        except (IndexError, TypeError):
            continue
        if off_tid == team_id:
            unit = tuple(sorted(row[3:8]))
            pf, pa = pts, 0
        elif def_tid == team_id:
            unit = tuple(sorted(row[8:13]))
            pf, pa = 0, pts
        else:
            continue
        if any(v is None for v in unit):
            continue
        try:
            unit = tuple(int(v) for v in unit)
        except (TypeError, ValueError):
            continue
        a = agg.setdefault(unit, [0.0, 0.0, 0])
        a[0] += pf
        a[1] += pa
        a[2] += 1
    out: dict[tuple[int, ...], tuple[float, int]] = {}
    for unit, (pf, pa, poss) in agg.items():
        net = round((pf - pa) / poss * 100, 1) if poss else 0.0
        out[unit] = (net, int(poss))
    return out


def _lineup_key(row: dict[str, Any]) -> tuple[int, ...] | None:
    gid = row.get("GROUP_ID")
    if gid:
        try:
            parts = [int(p) for p in str(gid).split("-") if p.strip().isdigit()]
            if len(parts) == 5:
                return tuple(sorted(parts))
        except (TypeError, ValueError):
            pass
    return None


_HIST_LINEUP_PAIRS = (
    ("group_id", "GROUP_ID"), ("group_name", "GROUP_NAME"),
    ("team_id", "TEAM_ID"), ("team_abbreviation", "TEAM_ABBREVIATION"),
    ("gp", "GP"), ("min", "MIN"), ("pts", "PTS"),
    ("plus_minus", "PLUS_MINUS"), ("fga", "FGA"), ("oreb", "OREB"),
    ("tov", "TOV"), ("fta", "FTA"),
)


def _hist_lineup_rows(team_id: int, season: str) -> list[dict[str, Any]]:
    try:
        from .. import store as _store
        found = _store._read_df(
            "SELECT group_id, group_name, team_id, team_abbreviation,"
            " gp, min, pts, plus_minus, fga, oreb, tov, fta"
            " FROM silver_hist_lineups"
            " WHERE _season = ? AND team_id = ?"
            " AND season_type = 'regular-season'"
            " AND measure_type = 'base' AND per_mode = 'totals'",
            [season, team_id],
        )
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for r in found or []:
        try:
            out.append({upper: r.get(lower)
                        for lower, upper in _HIST_LINEUP_PAIRS})
        except Exception:
            continue
    return out


@tool
def get_lineups(team_id: str | int, season: str | None = None) -> dict[str, Any]:
    """Five-man lineup stats for one team id, sorted by minutes."""
    season = resolve_season(season)
    team_id = coerce_team_id(team_id)
    rows, meta = _warehouse_or_live(
        "silver_lineups", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.lineups(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=TTL_PBPSTATS,
    )
    if not rows:
        rows = _hist_lineup_rows(team_id, season)
        if rows:
            meta = {**meta, "source": "warehouse",
                    "coverage": "historical_lineups"}
    for r in rows:
        tier, est = _sample_tier(r.get("MIN"))
        r["SAMPLE_TIER"] = tier
        r["EST_POSS"] = est
        if tier == "small":
            r["SAMPLE"] = "small: under ~100 possessions"
    rows = sorted(rows, key=lambda r: float(r.get("MIN") or 0), reverse=True)
    try:
        comp = _competitive_lineup_nets(team_id, season)
    except Exception:
        comp = None
    if comp is None:
        for r in rows:
            r["competitive_net"] = None
            r["competitive_poss"] = None
            r["competitive_note"] = "possessions missing for team/season"
    else:
        try:
            from nba_api.stats.static import players as _static_players

            _all = _static_players.get_players()
            _by_last = {}
            for p in _all:
                last = str(p.get("last_name", "")).lower()
                if last:
                    _by_last.setdefault(last, p["id"])
        except Exception:
            _by_last = {}
        for r in rows:
            key = _lineup_key(r)
            if key is None and _by_last:
                try:
                    parts = [t.strip().lower().split()[-1]
                             for t in str(r.get("GROUP_NAME", "")).split("-")]
                    ids = [_by_last[t] for t in parts if t in _by_last]
                    if len(ids) == 5:
                        key = tuple(sorted(ids))
                except (TypeError, ValueError, IndexError):
                    key = None
            if key is not None and key in comp:
                net, poss = comp[key]
                r["competitive_net"] = net
                r["competitive_poss"] = poss
                if poss < 50:
                    r["SAMPLE"] = "small: under 50 competitive possessions"
            else:
                r["competitive_net"] = None
                r["competitive_poss"] = 0
                r["SAMPLE"] = "small: under 50 competitive possessions"
    meta = {**meta,
            "scope": f"Lineup nets are full-game totals for season {season} "
            "with no margin or clock filter, so garbage time is included."}
    return {"tool": "get_lineups", "ok": True, "rows": rows, "meta": meta}


@tool
def get_scouting_report(team_id: str | int, season: str | None = None) -> dict[str, Any]:
    """One-call dossier: record, roster, lineups, leaders context."""
    season = resolve_season(season)
    team_id = coerce_team_id(team_id)
    games, _ = _warehouse_or_live(
        "silver_team_games", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.team_gamelog(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=TTL_GAMELOG,
    )
    lineups, _ = _warehouse_or_live(
        "silver_lineups", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.lineups(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=TTL_PBPSTATS,
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
def get_recap(game_id: str, season: str | None = None) -> dict[str, Any]:
    """Post-game recap data: boxscore top five plus team totals."""
    season = resolve_season(season)
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
                      "rows": len(top), "cached": False,
                      "links": game_links(game_id)}}


@tool
async def get_scout_pack(team: str = "", opponent: str = "", season: str | None = None) -> dict[str, Any]:
    """One-call next-opponent brief: record, net rating, top lineups, injuries."""
    season = resolve_season(season)
    from .league import get_injuries, get_ratings

    async def one(who: str) -> dict[str, Any]:
        try:
            tid = coerce_team_id(who)
            abbr = _abbrev(who)
        except Exception as exc:
            return {"error": str(exc)[:160]}
        try:
            hub = await get_team_hub.ainvoke({"team_id": tid, "season": season})
            games = (hub.get("rows") or {}).get("games", []) or []
            wins = sum(1 for g in games if g.get("WL") == "W")
            rec = f"{wins}-{len(games) - wins}" if games else "0-0"
            rat = await get_ratings.ainvoke({"season": season})
            rr = next((r for r in rat.get("rows", []) if str(r.get("TEAM", "")).upper() == abbr.upper()), {})
            lin = await get_lineups.ainvoke({"team_id": tid, "season": season})
            top = [{"GROUP_NAME": r.get("GROUP_NAME"), "MIN": r.get("MIN"),
                    "PLUS_MINUS": r.get("PLUS_MINUS"), "SAMPLE_TIER": r.get("SAMPLE_TIER")}
                   for r in lin.get("rows", []) if "SAMPLE" not in r][:3]
            inj = await get_injuries.ainvoke({"team": abbr, "season": season})
            irows = inj.get("rows", []) or []
            return {"abbrev": abbr, "team_id": tid, "record": rec, "games": len(games),
                    "net_rating": rr.get("NET_RATING"), "net_rank": rr.get("NET_RATING_RANK"),
                    "off_rating": rr.get("OFF_RATING"), "def_rating": rr.get("DEF_RATING"),
                    "top_lineups": top, "injuries": irows, "injury_count": len(irows)}
        except Exception as exc:
            return {"abbrev": who, "error": str(exc)[:160]}

    t, o = await _asyncio.gather(one(team or ""), one(opponent or ""))
    try:
        tn, on_ = float(t.get("net_rating") or 0), float(o.get("net_rating") or 0)
        tp = (t.get("top_lineups") or [{}])[0].get("PLUS_MINUS", 0)
        op = (o.get("top_lineups") or [{}])[0].get("PLUS_MINUS", 0)
        edge = (f"{t.get('abbrev', team)} ({t.get('record')}, net {tn:+.1f}) vs "
                f"{o.get('abbrev', opponent)} ({o.get('record')}, net {on_:+.1f}): "
                f"net gap {tn - on_:+.1f}, top-unit {tp} vs {op}.")
        thin = [s.get("abbrev", "") for s in (t, o)
                if (s.get("top_lineups") or [{}])[0].get("SAMPLE_TIER") == "medium"]
        if thin:
            edge += f" Note: {', '.join(thin)} top unit has only 50-100 minutes together."
    except Exception:
        edge = f"{team} vs {opponent}: data incomplete, check records and health."
    return {"tool": "get_scout_pack", "ok": True, "rows": {"team": t, "opponent": o, "edge": edge},
            "meta": {"source": "nba_api+warehouse", "season": season}}


def _slim_unit_row(u: dict[str, Any]) -> dict[str, Any]:
    return {
        "GROUP_NAME": u.get("GROUP_NAME"),
        "EST_MIN": u.get("EST_MIN"),
        "GP": u.get("GP"),
        "poss": u.get("poss"),
        "OFF_RATING": u.get("OFF_RATING"),
        "DEF_RATING": u.get("DEF_RATING"),
        "NET_RATING": u.get("NET_RATING"),
        "PLUS_MINUS": u.get("PLUS_MINUS"),
        "is_best_net_unit": bool(u.get("is_best_net_unit")),
        "flags": list(u.get("flags") or []),
    }


CORE_GP_FLOOR = 20


def _tier_players(players: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    def _gp(p: dict[str, Any]) -> int:
        try:
            return int(p.get("GP") or 0)
        except (TypeError, ValueError):
            return 0

    def _mpg(p: dict[str, Any]) -> float:
        try:
            return float(p.get("MPG") or 0)
        except (TypeError, ValueError):
            return 0.0

    by_mpg = sorted(players, key=_mpg, reverse=True)
    core = [p for p in by_mpg if _gp(p) >= CORE_GP_FLOOR][:5]
    core_ids = {id(p) for p in core}
    rest = [p for p in by_mpg if id(p) not in core_ids]
    return {
        "core": core,
        "bench": rest[:5],
        "fringe": rest[5:10],
    }


def _thin_rotation_flags(
    *,
    players: list[dict[str, Any]],
    most_used_share: float,
    bench_diffs: list[float | None],
    cached_onoff: int,
) -> list[str]:
    if not players:
        return []
    flags: list[str] = []
    try:
        deep15 = sum(1 for p in players if float(p.get("MPG") or 0) >= 15)
    except (TypeError, ValueError):
        deep15 = 0
    try:
        deep10 = sum(1 for p in players if float(p.get("MPG") or 0) >= 10)
    except (TypeError, ValueError):
        deep10 = 0
    if deep15 < 8:
        flags.append(
            f"thin rotation: only {deep15} players at 15+ MPG"
            " (a healthy rotation runs 8-10 deep)"
        )
    if deep10 < 10:
        flags.append(f"short bench: only {deep10} players at 10+ MPG")
    try:
        share = float(most_used_share or 0)
    except (TypeError, ValueError):
        share = 0.0
    if share >= 0.35:
        flags.append(
            "heavy reliance: the most-used unit takes"
            f" {round(share * 100)}% of sampled lineup minutes"
        )
    diffs = [d for d in (bench_diffs or []) if isinstance(d, (int, float))]
    if len(diffs) >= 3:
        avg = sum(diffs) / len(diffs)
        if avg <= -3:
            flags.append(
                "bench drag: rotation players 6-10 average"
                f" {avg:+.1f} on/off"
            )
    try:
        cached = int(cached_onoff or 0)
    except (TypeError, ValueError):
        cached = 0
    if cached < 8:
        flags.append(
            f"on/off coverage thin: only {cached} of the top 10"
            " have cached on/off"
        )
    return flags


def _closing_candidates(
    units: list[dict[str, Any]], top_units: int, min_possessions: int,
) -> list[dict[str, Any]]:



    seen: set[str] = set()
    distinct: list[dict[str, Any]] = []
    for u in units or []:
        key = str(u.get("GROUP_NAME") or "")
        if key in seen:
            continue
        seen.add(key)
        distinct.append(u)
    eligible = [u for u in distinct if (u.get("poss") or 0) >= min_possessions]
    ordered = sorted(eligible, key=lambda u: float(u.get("NET_RATING") or 0), reverse=True)
    return [_slim_unit_row(u) for u in ordered[:top_units]]


def _avg_diff(rows: list[dict[str, Any]]) -> float | None:
    diffs = [r.get("DIFF") for r in rows
             if r.get("CACHED") and isinstance(r.get("DIFF"), (int, float))]
    if not diffs:
        return None
    return round(sum(diffs) / len(diffs), 1)


def _assemble_rotation_report(
    *,
    team_id: int,
    abbrev: str,
    season: str,
    min_possessions: int,
    top_units: int,
    players: list[dict[str, Any]],
    units: list[dict[str, Any]],
    clutch_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    season = resolve_season(season)
    players = players or []
    units = units or []
    clutch_rows = clutch_rows or []
    tiers = _tier_players(players)
    top15 = (tiers["core"] + tiers["bench"] + tiers["fringe"])[:15]
    try:
        total_min = sum(float(p.get("MIN") or 0) for p in top15)
        core_min = sum(float(p.get("MIN") or 0) for p in tiers["core"])
        share = round(core_min / total_min, 3) if total_min > 0 else 0.0
    except (TypeError, ValueError):
        share = 0.0
    bench_rows = tiers["bench"]
    bench_cached = sum(1 for p in bench_rows if p.get("CACHED"))
    bench_diffs = [p.get("DIFF") for p in bench_rows]
    top10 = (tiers["core"] + tiers["bench"])[:10]
    cached10 = sum(1 for p in top10 if p.get("CACHED"))
    slimmed = [_slim_unit_row(u) for u in units]
    most_used = slimmed[0] if slimmed else None
    try:
        total_est = sum(float(u.get("EST_MIN") or 0) for u in units)
        top_est = float(units[0].get("EST_MIN") or 0) if units else 0.0
        most_share = (top_est / total_est) if total_est > 0 else 0.0
    except (TypeError, ValueError, IndexError):
        most_share = 0.0
    thin = _thin_rotation_flags(
        players=players,
        most_used_share=most_share,
        bench_diffs=bench_diffs,
        cached_onoff=cached10,
    )
    if not players and not units:
        thin = []
    closing = _closing_candidates(units, top_units, min_possessions)
    try:
        total_poss = sum(int(u.get("poss") or 0) for u in units)
    except (TypeError, ValueError):
        total_poss = 0
    ids = {p.get("PLAYER_ID") for p in players if p.get("PLAYER_ID") is not None}
    closers: list[dict[str, Any]] = []
    for r in clutch_rows:
        if ids and r.get("PLAYER_ID") not in ids:
            continue
        closers.append({
            "PLAYER": r.get("PLAYER_NAME") or r.get("PLAYER"),
            "PLAYER_ID": r.get("PLAYER_ID"),
            "GP": r.get("GP"),
            "W": r.get("W"),
            "L": r.get("L"),
            "MIN": r.get("MIN"),
        })
        if len(closers) >= 8:
            break
    clutch_note = (
        "warehouse silver_clutch is player-scope only"
        " (last 5 min, margin <=5); team-level clutch splits live"
        " in get_clutch, not duplicated here"
    )
    if not closers:
        clutch_note += "; no cached clutch minutes for this team's players"
    return {
        "tool": "get_rotation_check",
        "ok": True,
        "rows": {
            "team": {"id": team_id, "abbrev": abbrev},
            "coverage": {
                "season": season,
                "units": len(units),
                "total_unit_poss": total_poss,
                "minutes_basis": (
                    "lineup EST_MIN = poss/2; lineup MIN is full-season"
                    " 2025-26 (silver_lineups, sportsdataverse seeds);"
                    " player MIN is season-to-date"
                    " from silver_hist_player_seasons"
                ),
            },
            "tiers": tiers,
            "starter_bench_split": {
                "starter_min_share": share,
                "starter_avg_diff": _avg_diff(tiers["core"]),
                "bench_avg_diff": _avg_diff(bench_rows),
                "bench_cached": bench_cached,
            },
            "most_used_unit": most_used,
            "closing_candidates": closing,
            "thin_flags": thin,
            "clutch_context": {"note": clutch_note, "closers": closers},
        },
        "meta": {
            "source": "warehouse",
            "season": season,
            "team_id": team_id,
            "sample_floor": f"{min_possessions} possessions",
            "data_note": (
                "warehouse-only; lineup EST_MIN = poss/2; silver_lineups"
                " MIN is full-season 2025-26 (sportsdataverse seeds); units under the"
                f" {min_possessions}-possession floor are hidden by"
                " get_lineup_stats, never presented as signal; player MIN is"
                " season-to-date from silver_hist_player_seasons and on/off"
                " from silver_on_off; every number is labeled with its source"
                " table and coverage in coverage/meta"
            ),
        },
    }


def _fetch_rotation_players(season: str, abbrev: str) -> list[dict[str, Any]]:
    season = resolve_season(season)
    from .. import store as _store

    return _store._read_df(
        "SELECT player_id, player_name, gp, min, pts"
        " FROM silver_hist_player_seasons"
        " WHERE _season = ? AND team_abbreviation = ?",
        [season, abbrev],
    )


def _fetch_rotation_onoff(
    season: str, pid: object,
) -> tuple[float | None, float | None, float | None, bool]:
    season = resolve_season(season)
    from .. import store as _store

    try:
        cached = _store._read_df(
            'SELECT Stat, "On", "Off", "On-Off" FROM silver_on_off'
            " WHERE _season = ? AND _entity = ?",
            [season, f"player:{pid}"],
        )
    except Exception:
        return None, None, None, False
    if not cached:
        return None, None, None, False
    for r in cached:
        if r.get("Stat") == "Pts per 100 Possessions":
            try:
                return float(r.get("On")), float(r.get("Off")), float(r.get("On-Off")), True
            except (TypeError, ValueError):
                return None, None, None, True
    return None, None, None, True


def _fetch_rotation_clutch(season: str, team_id: int) -> list[dict[str, Any]]:
    season = resolve_season(season)
    from .. import store as _store

    try:
        return _store._read_df(
            "SELECT PLAYER_NAME, PLAYER_ID, GP, W, L, MIN FROM silver_clutch"
            " WHERE _season = ? AND TEAM_ID = ? ORDER BY MIN DESC",
            [season, team_id],
        )
    except Exception:
        return []


async def _fetch_rotation_units(
    team: str | int, season: str, min_possessions: int,
) -> list[dict[str, Any]]:
    season = resolve_season(season)
    from .lineup import get_lineup_stats

    res = await get_lineup_stats.ainvoke({
        "team": team,
        "season": season,
        "min_possessions": min_possessions,
        "include_small": False,
        "limit": 25,
    })
    if not isinstance(res, dict) or not res.get("ok"):
        return []
    return res.get("rows") or []


@tool
async def get_rotation_check(
    team: str | int = "", season: str | None = None, min_possessions: int = 100,
    top_units: int = 5,
) -> dict[str, Any]:
    """Rotation and closing-unit check from warehouse five-man units, minutes, and cached on/off."""
    season = resolve_season(season)
    try:
        tid = coerce_team_id(team)
    except ValueError as exc:
        return {"tool": "get_rotation_check", "ok": False,
                "error": str(exc)[:160]}
    abbr = _abbrev(team)
    try:
        raw_players = _fetch_rotation_players(season, abbr)
    except Exception:
        raw_players = []
    enriched: list[dict[str, Any]] = []
    for r in raw_players:
        try:
            pid = r.get("player_id", r.get("PLAYER_ID"))
            name = r.get("player_name", r.get("PLAYER") or r.get("player"))
            gp = r.get("gp", r.get("GP") or 0)
            minutes = r.get("min", r.get("MIN") or 0)
            pts = r.get("pts", r.get("PTS") or 0)
            try:
                gp_f = int(gp or 0)
            except (TypeError, ValueError):
                gp_f = 0
            try:
                mpg = float(minutes or 0)
            except (TypeError, ValueError):
                mpg = 0.0
            try:
                ppg = float(pts or 0)
            except (TypeError, ValueError):
                ppg = 0.0


            min_f = round(mpg * gp_f, 1) if gp_f > 0 else 0.0
            pts_f = round(ppg * gp_f, 1) if gp_f > 0 else 0.0
            on, off, diff, cached = _fetch_rotation_onoff(season, pid)
            enriched.append({
                "PLAYER": name, "PLAYER_ID": pid, "GP": gp_f, "MIN": min_f,
                "MPG": round(mpg, 1), "PTS": pts_f, "ON": on, "OFF": off,
                "DIFF": diff, "CACHED": cached,
            })
        except Exception:
            continue




    enriched = sorted(enriched, key=lambda p: float(p.get("MPG") or 0),
                      reverse=True)[:15]
    try:
        units = await _fetch_rotation_units(team, season, min_possessions)
    except Exception:
        units = []
    clutch_rows = _fetch_rotation_clutch(season, tid)
    return _assemble_rotation_report(
        team_id=tid, abbrev=abbr, season=season,
        min_possessions=min_possessions, top_units=top_units,
        players=enriched, units=units, clutch_rows=clutch_rows,
    )


_TRAILING_SPLIT = "last10"
_TRAILING_SPLIT_SIZE = 10

_SPLIT_WINDOW_KINDS = {
    "home": ("venue", "regular-season games at home"),
    "away": ("venue", "regular-season games on the road"),
    "wins": ("outcome", "regular-season games won"),
    "losses": ("outcome", "regular-season games lost"),
    _TRAILING_SPLIT: (
        "trailing_games",
        f"the {_TRAILING_SPLIT_SIZE} most recent regular-season games"),
}


@dataclass(frozen=True)
class ScoredWindow:
    """The games a per-game rate was measured over.

    A rate without its window is a different number wearing the same label,
    so the window travels with the value or the value does not publish.
    """

    kind: str
    label: str
    season: str
    phase: str
    games: int

    def payload(self) -> dict[str, Any]:
        return {"kind": self.kind, "label": self.label, "season": self.season,
                "phase": self.phase, "games": self.games}


def _split_window(split: str, season: str, games: int) -> ScoredWindow:
    kind, label = _SPLIT_WINDOW_KINDS.get(
        split, ("calendar_month", f"regular-season games in {split}"))
    return ScoredWindow(kind=kind, label=label, season=season,
                        phase="regular season", games=games)


@tool
def get_team_splits(team: str | int, season: str | None = None) -> dict[str, Any]:
    """Home/away, wins/losses, last-10, monthly record plus PPG from cached gamelog."""
    season = resolve_season(season)
    try:
        tid = coerce_team_id(team)
    except ValueError as exc:
        return {"tool": "get_team_splits", "ok": False, "error": str(exc)[:160]}
    from datetime import datetime as _dt
    from .. import store as _store
    con = _store.connect()
    try:
        rows = con.execute(
            "SELECT MATCHUP, WL, GAME_DATE, PTS FROM silver_team_games"
            " WHERE _season = ? AND _entity = ?",
            [season, f"team:{tid}"],
        ).fetchall()
    finally:
        con.close()
    source = "silver_team_games"
    if not rows:
        rows = [(str(row.get("MATCHUP") or ""), str(row.get("WL") or ""),
                 str(row.get("GAME_DATE") or ""), row.get("PTS"))
                for row in _hist_team_games(tid, season)]
        source = "silver_hist_gamelogs"
    if not rows:
        return {"tool": "get_team_splits", "ok": False,
                "error": f"no cached games for team {tid}"}
    def _dkey(d: object) -> object:
        try:
            return _dt.strptime(str(d).title(), "%b %d, %Y")
        except (TypeError, ValueError):
            return _dt.min
    def _row(split: str, rs: list) -> dict[str, Any]:
        gp = len(rs)
        w = sum(1 for r in rs if r[1] == "W")
        l = sum(1 for r in rs if r[1] == "L")
        scored = [r for r in rs if r[3] is not None]
        ppg = (round(sum(float(r[3]) for r in scored) / len(scored), 1)
               if scored else None)
        return {"split": split,
                "window": _split_window(split, season, gp).payload(),
                "GP": gp, "W": w, "L": l, "UNDECIDED": gp - w - l,
                "PPG": ppg, "PPG_GAMES": len(scored)}
    out = [_row("home", [r for r in rows if "@" not in str(r[0])]),
           _row("away", [r for r in rows if "@" in str(r[0])]),
           _row("wins", [r for r in rows if r[1] == "W"]),
           _row("losses", [r for r in rows if r[1] == "L"])]
    ordered = sorted(rows, key=lambda r: _dkey(r[2]), reverse=True)
    out.append(_row(_TRAILING_SPLIT, ordered[:_TRAILING_SPLIT_SIZE]))
    months: dict[str, list] = {}
    for r in sorted(rows, key=lambda r: _dkey(r[2])):
        months.setdefault(str(r[2])[:3].upper(), []).append(r)
    out.extend(_row(m, rs) for m, rs in months.items())
    return {"tool": "get_team_splits", "ok": True, "rows": out,
            "meta": {"source": source, "season": season, "team_id": tid}}


@tool
async def get_injury_impact(team: str = "", season: str | None = None) -> dict[str, Any]:
    """Injury impact in one call: outs, net rating, last-10, heuristic impact."""
    season = resolve_season(season)
    import ast as _ast
    import json as _json

    from .league import get_injuries, get_ratings

    abbr = _abbrev(team or "")
    out: list[str] = []
    questionable: list[str] = []
    net = None
    rank = None
    last10 = None
    try:
        inj = await get_injuries.ainvoke({"team": abbr, "season": season})
        for r in inj.get("rows", []) or []:
            raw = r.get("injuries", "")
            try:
                try:
                    items = _json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    items = _ast.literal_eval(raw) if isinstance(raw, str) else raw
            except Exception:
                items = []
            for it in items or []:
                if not isinstance(it, dict):
                    continue
                name = (it.get("athlete") or {}).get("displayName", "?")
                if "out" in str(it.get("status", "")).lower():
                    out.append(str(name))
                else:
                    questionable.append(str(name))
    except Exception:
        pass
    try:
        rat = await get_ratings.ainvoke({"season": season})
        row = next((x for x in rat.get("rows", []) or []
                    if str(x.get("TEAM", "")).upper() == abbr.upper()), {})
        try:
            net = float(row.get("NET_RATING")) if row.get("NET_RATING") is not None else None
        except (TypeError, ValueError):
            net = None
        rank = row.get("NET_RATING_RANK")
    except Exception:
        pass
    try:
        sp = get_team_splits.invoke({"team": abbr, "season": season})
        l10 = next((x for x in sp.get("rows", []) or []
                    if x.get("split") == _TRAILING_SPLIT), {})
        if l10:
            last10 = f"{l10.get('W')}-{l10.get('L')}"
    except Exception:
        pass
    try:
        below = net is not None and float(net) < 0
    except (TypeError, ValueError):
        below = False
    availability_known = bool(out or questionable)
    impact = ("high" if len(out) >= 2 and below else
              "moderate" if out else "low" if availability_known else "unknown")
    meta = {"source": "espn+nba_api+warehouse", "season": season,
            "heuristic": "OUT>=2 and net<0 -> high; OUT>=1 -> moderate; "
            "listed players with no OUT -> low; empty report -> unknown; "
            "OUT = 'out' in status text, questionable = other listings"}
    if not availability_known:
        meta["warning"] = (
            "empty injury rows do not establish that all players are available"
        )
    return {"tool": "get_injury_impact", "ok": True,
            "rows": {"team": abbr, "out": out, "questionable": questionable,
                     "availability_known": availability_known,
                     "net_rating": net, "net_rank": rank, "last10": last10,
                     "impact": impact},
            "meta": meta}


@tool(description="Two-team matchup brief with ratings, form, injuries, season series, and win probability.")
async def get_matchup_brief(a: str = "", b: str = "", season: str | None = None) -> dict[str, Any]:
    from .league import get_ratings
    from .prediction import get_game_prediction
    season = resolve_season(season)
    a = str(a or "").strip()
    b = str(b or "").strip()
    if not a or not b:
        return {"tool": "get_matchup_brief", "ok": False, "error": "pass two teams (a, b)"}
    if not season:
        return {"tool": "get_matchup_brief", "ok": False, "error": "season is unresolved"}
    try:
        ida = coerce_team_id(a)
    except ValueError:
        return {"tool": "get_matchup_brief", "ok": False, "error": "unknown team: " + a}
    try:
        idb = coerce_team_id(b)
    except ValueError:
        return {"tool": "get_matchup_brief", "ok": False, "error": "unknown team: " + b}
    if ida == idb:
        return {"tool": "get_matchup_brief", "ok": False, "error": "a and b must be different teams"}
    abbr_a = str(_abbrev(a) or "").strip().upper()
    abbr_b = str(_abbrev(b) or "").strip().upper()
    rat = await get_ratings.ainvoke({"season": season})
    if not isinstance(rat, dict) or not rat.get("ok"):
        err = ""
        if isinstance(rat, dict):
            err = str(rat.get("error") or "ratings unavailable")
        return {"tool": "get_matchup_brief", "ok": False, "error": err}
    ratings_meta = rat.get("meta") if isinstance(rat.get("meta"), dict) else {}
    card_provenance = {
        "kind": str(ratings_meta.get("ratings_provenance") or ""),
        "source": str(ratings_meta.get("ratings_source") or ""),
    }
    allrows = rat.get("rows") or []
    row_a = next((r for r in allrows if str(r.get("TEAM") or "").strip().upper() == abbr_a), None)
    row_b = next((r for r in allrows if str(r.get("TEAM") or "").strip().upper() == abbr_b), None)
    if row_a is None or row_b is None:
        missing = []
        if row_a is None:
            missing.append(abbr_a)
        if row_b is None:
            missing.append(abbr_b)
        return {"tool": "get_matchup_brief", "ok": False, "error": "ratings missing for " + ", ".join(missing)}
    def _rating_card(r):
        w = r.get("W")
        l = r.get("L")
        record = str(w) + "-" + str(l) if w is not None and l is not None else None
        return {"TEAM": r.get("TEAM"), "TEAM_NAME": r.get("TEAM_NAME"), "TEAM_ID": r.get("TEAM_ID"), "OFF_RATING": r.get("OFF_RATING"), "DEF_RATING": r.get("DEF_RATING"), "NET_RATING": r.get("NET_RATING"), "PACE": r.get("PACE"), "W": w, "L": l, "record": record, "OFF_RATING_RANK": r.get("OFF_RATING_RANK"), "DEF_RATING_RANK": r.get("DEF_RATING_RANK"), "NET_RATING_RANK": r.get("NET_RATING_RANK")}
    def _last10(rows_in):
        item = next(
            (x for x in rows_in if x.get("split") == _TRAILING_SPLIT), None)
        if not item:
            return None
        return str(item.get("W")) + "-" + str(item.get("L"))
    form = {}
    for abbr in (abbr_a, abbr_b):
        sp = await get_team_splits.ainvoke({"team": abbr, "season": season})
        if not isinstance(sp, dict) or not sp.get("ok"):
            err2 = ""
            if isinstance(sp, dict):
                err2 = str(sp.get("error") or "splits unavailable")
            return {"tool": "get_matchup_brief", "ok": False, "error": err2}
        sprows = sp.get("rows") or []
        form[abbr] = {"last10": _last10(sprows), "splits": sprows}
    injuries = {}
    for abbr in (abbr_a, abbr_b):
        imp = await get_injury_impact.ainvoke({"team": abbr, "season": season})
        if not isinstance(imp, dict) or not imp.get("ok"):
            err3 = ""
            if isinstance(imp, dict):
                err3 = str(imp.get("error") or "injury data unavailable")
            return {"tool": "get_matchup_brief", "ok": False, "error": err3}
        injuries[abbr] = imp.get("rows") or {}
    ser = await get_season_series.ainvoke({"team_a": abbr_a, "team_b": abbr_b, "season": season})
    warnings = []
    if isinstance(ser, dict) and ser.get("ok"):
        series_rows = ser.get("rows") or {}
    else:
        series_rows = {"teams": [abbr_a, abbr_b], "summary": {"games": 0}, "games": []}
        if isinstance(ser, dict) and ser.get("error"):
            warnings.append(str(ser.get("error")))
    pred = await get_game_prediction.ainvoke({"a": abbr_a, "b": abbr_b, "season": season})
    if not isinstance(pred, dict) or not pred.get("ok"):
        err4 = ""
        if isinstance(pred, dict):
            err4 = str(pred.get("error") or "prediction unavailable")
        return {"tool": "get_matchup_brief", "ok": False, "error": err4}
    est = pred.get("estimate") or {}
    inputs = pred.get("inputs") or {}
    prediction_provenance = {
        "kind": str(inputs.get("ratings_provenance") or ""),
        "source": str(inputs.get("ratings_source") or ""),
    }
    if (not all(card_provenance.values())
            or card_provenance != prediction_provenance):
        return {"tool": "get_matchup_brief", "ok": False, "error": (
            f"ratings provenance disagrees inside the brief for season "
            f"{season}: the ratings card reports "
            f"{_provenance_label(card_provenance)} and the simulation reports "
            f"{_provenance_label(prediction_provenance)}, so one quantity "
            f"would carry two provenances; refusing to answer")}
    pred_meta = pred.get("meta") if isinstance(pred.get("meta"), dict) else {}
    prediction_rows = {"matchup": pred.get("matchup") or {}, "win_prob": est.get("win_prob") or {}, "projected_score": est.get("projected_score") or {}, "projected_total": est.get("projected_total"), "win_prob_ci90": est.get("win_prob_ci90") or {}, "total_ci90": est.get("total_ci90") or [], "margin_ci90": est.get("margin_ci90") or [], "ratings_source": prediction_provenance["source"], "ratings_provenance": prediction_provenance["kind"]}
    from .. import store as _store

    meta = {"source": str(pred_meta.get("source") or "warehouse"), "season": season, "ratings_provenance": card_provenance, **_store.warehouse_identity()}
    if warnings:
        meta["warnings"] = warnings
    return {"tool": "get_matchup_brief", "ok": True, "rows": {"teams": [abbr_a, abbr_b], "ratings_provenance": card_provenance, "ratings": {abbr_a: _rating_card(row_a), abbr_b: _rating_card(row_b)}, "form": form, "injuries": injuries, "season_series": series_rows, "prediction": prediction_rows}, "meta": meta}


def _provenance_label(provenance: dict[str, str]) -> str:
    kind = str(provenance.get("kind") or "").strip()
    source = str(provenance.get("source") or "").strip()
    if not kind and not source:
        return "no provenance"
    return f"{kind or 'unknown'} ({source or 'no table'})"
