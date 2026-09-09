"""Team desk. Hubs, games, boxscores, lineups, dossiers, recaps."""

from typing import Any
import asyncio as _asyncio
from langchain_core.tools import tool

from ..sources import nba_stats
from ._core import SEASON, _warehouse_or_live, coerce_team_id, trust_tier


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
    a: str, b: str, season: str = SEASON, home_abbrev: str = "",
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
    # Neutral court: preview(a, b) carries no home/matchup context, so the
    # +1.5 home edge is not applied to either side.
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


def game_links(game_id: str) -> dict[str, str]:
    return {"watch": f"https://www.nba.com/game/{game_id}"}


@tool
def get_games_on_date(game_date: str, season: str = SEASON) -> dict[str, Any]:
    """Scoreboard for one date. Date format is MM/DD/YYYY."""
    rows, meta = _warehouse_or_live(
        "silver_scoreboard", "_season = ? AND _entity = ?",
        [season, f"date:{game_date}"],
        lambda: nba_stats.scoreboard(game_date, season), season,
        entity=f"date:{game_date}", live_first=True,
    )
    for r in rows:
        gid = r.get("GAME_ID")
        if gid:
            r["LINKS"] = game_links(str(gid))
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
    return {"tool": "get_boxscore", "ok": True, "rows": rows,
            "meta": {**meta, "links": game_links(game_id)}}


def _trust_tier(minutes: object) -> tuple[str, int]:
    return trust_tier(minutes)


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
    for r in rows:
        tier, est = _trust_tier(r.get("MIN"))
        r["TRUST"] = tier
        r["EST_POSS"] = est
        if tier == "SMALL":
            r["SAMPLE"] = "small: under ~100 possessions, do not trust"
    rows = sorted(rows, key=lambda r: float(r.get("MIN") or 0), reverse=True)
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
                      "rows": len(top), "cached": False,
                      "links": game_links(game_id)}}


@tool
async def get_scout_pack(team: str = "", opponent: str = "", season: str = SEASON) -> dict[str, Any]:
    """One-call next-opponent brief: record, net rating, top lineups, injuries."""
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
                    "PLUS_MINUS": r.get("PLUS_MINUS"), "TRUST": r.get("TRUST")}
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
        fragile = [s.get("abbrev", "") for s in (t, o)
                   if (s.get("top_lineups") or [{}])[0].get("TRUST") == "FRAGILE"]
        if fragile:
            edge += f" Caution: {', '.join(fragile)} top unit is FRAGILE (50-100 minutes)."
    except Exception:
        edge = f"{team} vs {opponent}: data incomplete, check records and health."
    return {"tool": "get_scout_pack", "ok": True, "rows": {"team": t, "opponent": o, "edge": edge},
            "meta": {"source": "nba_api+warehouse", "season": season}}


@tool
def get_rotation_check(team: str = "", season: str = SEASON) -> dict[str, Any]:
    """Rotation health in one call: roster plus cached on/off net per player."""
    from .. import store as _store

    tid = coerce_team_id(team)
    abbr = _abbrev(team)
    ros: list[dict[str, Any]] = []
    try:
        from nba_api.stats.endpoints import CommonTeamRoster as _CTR
        import polars as _pl

        for _df in _CTR(team_id=tid, season=season, timeout=30).get_data_frames():
            _p = _pl.from_pandas(_df)
            if "PLAYER_ID" in _p.columns and _p.height:
                ros = _p.to_dicts()
                break
    except Exception:
        ros = []
    if not ros:
        try:
            res = nba_stats.team_roster(tid, season)
            ros = [r for r in (res.frame.to_dicts() if res.ok else [])
                   if r.get("PLAYER_ID")]
        except Exception:
            ros = []
    if not ros:
        try:
            from ..store import _read_df

            w_ros = _read_df(
                "SELECT PLAYER, PLAYER_ID, PTS, GP, MIN FROM silver_leaders_pts "
                "WHERE _season = ? AND (TEAM = ? OR TEAM_ID = ?) ORDER BY PTS DESC LIMIT 15",
                [season, abbr, tid],
            )
            if not w_ros:
                w_ros = _read_df(
                    "SELECT PLAYER, PLAYER_ID, PTS, GP, MIN FROM silver_leaders_pts "
                    "WHERE TEAM = ? OR TEAM_ID = ? ORDER BY PTS DESC LIMIT 15",
                    [abbr, tid],
                )
            if w_ros:
                ros = w_ros
        except Exception:
            pass
    mcol = next((c for c in ("MIN", "MPG", "PTS", "EXP") if ros and c in ros[0]), "")
    if mcol:
        def _num(r: dict[str, Any]) -> float:
            try:
                return float(r.get(mcol) or 0)
            except (TypeError, ValueError):
                return 0.0
        ros = sorted(ros, key=_num, reverse=True)
    ros = ros[:10]
    players: list[dict[str, Any]] = []
    for r in ros:
        try:
            pid = r.get("PLAYER_ID")
            name = r.get("PLAYER") or f"{r.get('FIRST_NAME', '')} {r.get('LAST_NAME', '')}".strip() or str(pid)
            cached: list = []
            try:
                con = _store.connect()
                try:
                    cached = con.execute(
                        'SELECT Stat, "On", "Off", "On-Off" FROM silver_on_off'
                        " WHERE _season = ? AND _entity = ?",
                        [season, f"player:{pid}"],
                    ).fetchall()
                finally:
                    con.close()
            except Exception:
                cached = []
            by_stat = {s: (o, f, d) for s, o, f, d in cached}
            row: dict[str, Any] = {"PLAYER": name, "ON": None, "OFF": None,
                                   "DIFF": None, "MIN": 0, "CACHED": bool(cached)}
            try:
                o, f, d = by_stat["Pts per 100 Possessions"]
                row["ON"], row["OFF"], row["DIFF"] = float(o), float(f), float(d)
            except (KeyError, TypeError, ValueError):
                pass
            try:
                m = next(v[0] for k, v in by_stat.items()
                         if k.strip().lower() in ("minutes", "min", "possessions"))
                row["MIN"] = float(m)
            except (StopIteration, TypeError, ValueError):
                pass
            players.append(row)
        except Exception:
            players.append({"PLAYER": "?", "ON": None, "OFF": None,
                            "DIFF": None, "MIN": 0, "CACHED": False})
    flag = ", ".join(p["PLAYER"] for p in players
                     if isinstance(p.get("DIFF"), (int, float)) and p["DIFF"] < -5
                     and isinstance(p.get("MIN"), (int, float)) and p["MIN"] > 100)
    return {"tool": "get_rotation_check", "ok": True,
            "rows": {"team": abbr, "players": players, "flag": flag},
            "meta": {"source": "nba_api+warehouse", "season": season}}


@tool
def get_team_splits(team: str | int, season: str = SEASON) -> dict[str, Any]:
    """Home/away, wins/losses, last-10, monthly record plus PPG from cached gamelog."""
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
        ppg = round(sum((r[3] or 0) for r in rs) / gp, 1) if gp else 0.0
        return {"split": split, "GP": gp, "W": w, "L": gp - w, "PPG": ppg}
    out = [_row("home", [r for r in rows if "@" not in str(r[0])]),
           _row("away", [r for r in rows if "@" in str(r[0])]),
           _row("wins", [r for r in rows if r[1] == "W"]),
           _row("losses", [r for r in rows if r[1] == "L"])]
    ordered = sorted(rows, key=lambda r: _dkey(r[2]), reverse=True)
    out.append(_row("last10", ordered[:10]))
    months: dict[str, list] = {}
    for r in sorted(rows, key=lambda r: _dkey(r[2])):
        months.setdefault(str(r[2])[:3].upper(), []).append(r)
    out.extend(_row(m, rs) for m, rs in months.items())
    return {"tool": "get_team_splits", "ok": True, "rows": out,
            "meta": {"source": "warehouse", "season": season, "team_id": tid}}


@tool
async def get_injury_impact(team: str = "", season: str = SEASON) -> dict[str, Any]:
    """Injury impact in one call: outs, net rating, last-10, heuristic impact."""
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
                    if x.get("split") == "last10"), {})
        if l10:
            last10 = f"{l10.get('W')}-{l10.get('L')}"
    except Exception:
        pass
    try:
        below = net is not None and float(net) < 0
    except (TypeError, ValueError):
        below = False
    impact = "high" if len(out) >= 2 and below else "moderate" if out else "low"
    return {"tool": "get_injury_impact", "ok": True,
            "rows": {"team": abbr, "out": out, "questionable": questionable,
                     "net_rating": net, "net_rank": rank, "last10": last10,
                     "impact": impact},
            "meta": {"source": "espn+nba_api+warehouse", "season": season,
                     "heuristic": "OUT>=2 and net<0 -> high; OUT>=1 -> moderate; else low; "
                     "OUT = 'out' in status text, questionable = other listings"}}
