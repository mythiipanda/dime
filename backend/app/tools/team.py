"""Team desk. Hubs, games, boxscores, lineups, dossiers, recaps."""

from typing import Any
import asyncio as _asyncio
from langchain_core.tools import tool

from ..sources import nba_stats
from ._core import SEASON, TTL_BOX, TTL_GAMELOG, TTL_PBPSTATS, TTL_ROSTER, TTL_SCOREBOARD_PAST, _warehouse_or_live, coerce_team_id, is_past_game_date, trust_tier


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
        entity=f"team:{team_id}", ttl_s=TTL_GAMELOG,
    )
    roster, _ = _warehouse_or_live(
        "silver_rosters", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.team_roster(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=TTL_ROSTER,
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
def get_boxscore(game_id: str, season: str = SEASON) -> dict[str, Any]:
    """Traditional boxscore player stats for one game id."""
    # game_id carries no date so a 1h TTL keeps in-progress games reasonably fresh while repeat reads stay instant
    rows, meta = _warehouse_or_live(
        "silver_boxscores", "_season = ? AND _entity = ?",
        [season, f"game:{game_id}"],
        lambda: nba_stats.boxscore_traditional(game_id, season), season,
        entity=f"game:{game_id}", ttl_s=TTL_BOX,
    )
    return {"tool": "get_boxscore", "ok": True, "rows": rows,
            "meta": {**meta, "links": game_links(game_id)}}


def _trust_tier(minutes: object) -> tuple[str, int]:
    return trust_tier(minutes)


def _competitive_lineup_nets(
    team_id: int, season: str,
) -> dict[tuple[int, ...], tuple[float, int]] | None:
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


@tool
def get_lineups(team_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Five-man lineup stats for one team id, sorted by minutes."""
    team_id = coerce_team_id(team_id)
    rows, meta = _warehouse_or_live(
        "silver_lineups", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: nba_stats.lineups(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=TTL_PBPSTATS,
    )
    for r in rows:
        tier, est = _trust_tier(r.get("MIN"))
        r["TRUST"] = tier
        r["EST_POSS"] = est
        if tier == "SMALL":
            r["SAMPLE"] = "small: under ~100 possessions, do not trust"
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
def get_scouting_report(team_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """One-call dossier: record, roster, lineups, leaders context."""
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


def _tier_players(players: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(players, key=lambda p: float(p.get("MIN") or 0), reverse=True)
    return {
        "core": ordered[:5],
        "bench": ordered[5:10],
        "fringe": ordered[10:15],
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
    eligible = [u for u in (units or []) if (u.get("poss") or 0) >= min_possessions]
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
    team: str | int = "", season: str = SEASON, min_possessions: int = 100,
    top_units: int = 5,
) -> dict[str, Any]:
    """Rotation and closing-unit check from warehouse five-man units, minutes, and cached on/off."""
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
            # Warehouse min/pts are per-game averages, so season totals
            # are derived as per-game * gp; MPG keeps the warehouse value.
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
    enriched = sorted(enriched, key=lambda p: float(p.get("MIN") or 0),
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
