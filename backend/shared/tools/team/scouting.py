import asyncio as _asyncio
import sys
from typing import Any

from langchain_core.tools import tool


def _pkg():
    return sys.modules[__package__]


@tool(description='One-call dossier: record, roster, top lineup only, leaders context. For the full qualifying-unit set use get_lineups or get_lineup_stats.')
def get_scouting_report(team_id: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    team_id = pkg.coerce_team_id(team_id)
    games, _ = pkg._warehouse_or_live(
        "silver_team_games", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: pkg.nba_stats.team_gamelog(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=pkg.TTL_GAMELOG,
    )
    lineups, _ = pkg._warehouse_or_live(
        "silver_lineups", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda: pkg.nba_stats.lineups(team_id, season), season,
        entity=f"team:{team_id}", ttl_s=pkg.TTL_PBPSTATS,
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


@tool(description='One-call next-opponent brief: record, net rating, top lineup only, injuries.')
async def get_scout_pack(team: str = "", opponent: str = "", season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    from ..league import get_injuries, get_ratings

    async def one(who: str) -> dict[str, Any]:
        try:
            tid = pkg.coerce_team_id(who)
            abbr = pkg._abbrev(who)
        except Exception as exc:
            return {"error": str(exc)[:160]}
        try:
            hub = await pkg.get_team_hub.ainvoke({"team_id": tid, "season": season})
            games = (hub.get("rows") or {}).get("games", []) or []
            wins = sum(1 for g in games if g.get("WL") == "W")
            rec = f"{wins}-{len(games) - wins}" if games else "0-0"
            rat = await get_ratings.ainvoke({"season": season})
            rr = next((r for r in rat.get("rows", []) if str(r.get("TEAM", "")).upper() == abbr.upper()), {})
            lin = await pkg.get_lineups.ainvoke({"team_id": tid, "season": season})
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


def _injury_status_lists(rows):
    import ast as _ast
    import json as _json

    out: list[str] = []
    questionable: list[str] = []
    for r in rows or []:
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
    return out, questionable


@tool(description='Injury impact in one call: outs, net rating, last-10, heuristic impact.')
async def get_injury_impact(team: str = "", season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    from ..league import get_injuries, get_ratings

    abbr = pkg._abbrev(team or "")
    out: list[str] = []
    questionable: list[str] = []
    net = None
    rank = None
    last10 = None
    try:
        inj = await get_injuries.ainvoke({"team": abbr, "season": season})
        out, questionable = pkg._injury_status_lists(inj.get("rows", []) or [])
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
        sp = pkg.get_team_splits.invoke({"team": abbr, "season": season})
        l10 = next((x for x in sp.get("rows", []) or []
                    if x.get("split") == pkg._TRAILING_SPLIT), {})
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


def _rating_card(r):
    w = r.get("W")
    l = r.get("L")
    record = str(w) + "-" + str(l) if w is not None and l is not None else None
    return {"TEAM": r.get("TEAM"), "TEAM_NAME": r.get("TEAM_NAME"), "TEAM_ID": r.get("TEAM_ID"),
            "OFF_RATING": r.get("OFF_RATING"), "DEF_RATING": r.get("DEF_RATING"),
            "NET_RATING": r.get("NET_RATING"), "PACE": r.get("PACE"),
            "W": w, "L": l, "record": record,
            "OFF_RATING_RANK": r.get("OFF_RATING_RANK"),
            "DEF_RATING_RANK": r.get("DEF_RATING_RANK"),
            "NET_RATING_RANK": r.get("NET_RATING_RANK")}


def _last10(rows_in):
    item = next(
        (x for x in rows_in if x.get("split") == _pkg()._TRAILING_SPLIT), None)
    if not item:
        return None
    return str(item.get("W")) + "-" + str(item.get("L"))


async def _brief_rating_rows(get_ratings, abbr_a, abbr_b, season):
    rat = await get_ratings.ainvoke({"season": season})
    if not isinstance(rat, dict) or not rat.get("ok"):
        err = ""
        if isinstance(rat, dict):
            err = str(rat.get("error") or "ratings unavailable")
        return None, None, None, err
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
        return None, None, None, "ratings missing for " + ", ".join(missing)
    return card_provenance, row_a, row_b, None


def _provenance_label(provenance: dict[str, str]) -> str:
    kind = str(provenance.get("kind") or "").strip()
    source = str(provenance.get("source") or "").strip()
    if not kind and not source:
        return "no provenance"
    return f"{kind or 'unknown'} ({source or 'no table'})"


def _provenance_error(card_provenance, prediction_provenance, season):
    if (not all(card_provenance.values())
            or card_provenance != prediction_provenance):
        return (
            f"ratings provenance disagrees inside the brief for season "
            f"{season}: the ratings card reports "
            f"{_provenance_label(card_provenance)} and the simulation reports "
            f"{_provenance_label(prediction_provenance)}, so one quantity "
            f"would carry two provenances; refusing to answer")
    return None


async def _brief_form(abbr_a, abbr_b, season):
    pkg = _pkg()
    form = {}
    for abbr in (abbr_a, abbr_b):
        sp = await pkg.get_team_splits.ainvoke({"team": abbr, "season": season})
        if not isinstance(sp, dict) or not sp.get("ok"):
            err2 = ""
            if isinstance(sp, dict):
                err2 = str(sp.get("error") or "splits unavailable")
            return None, err2
        sprows = sp.get("rows") or []
        form[abbr] = {"last10": pkg._last10(sprows), "splits": sprows}
    return form, None


async def _brief_injuries(abbr_a, abbr_b, season):
    pkg = _pkg()
    injuries = {}
    for abbr in (abbr_a, abbr_b):
        imp = await pkg.get_injury_impact.ainvoke({"team": abbr, "season": season})
        if not isinstance(imp, dict) or not imp.get("ok"):
            err3 = ""
            if isinstance(imp, dict):
                err3 = str(imp.get("error") or "injury data unavailable")
            return None, err3
        injuries[abbr] = imp.get("rows") or {}
    return injuries, None


async def _brief_series(abbr_a, abbr_b, season):
    pkg = _pkg()
    ser = await pkg.get_season_series.ainvoke({"team_a": abbr_a, "team_b": abbr_b, "season": season})
    warnings = []
    if isinstance(ser, dict) and ser.get("ok"):
        series_rows = {"teams": [abbr_a, abbr_b], "available": True,
                       **(ser.get("rows") or {})}
    else:
        reason = (str(ser.get("error") or "") if isinstance(ser, dict)
                  else "season series unavailable")
        series_rows = {"teams": [abbr_a, abbr_b], "available": False,
                       "summary": None, "games": [], "reason": reason}
        if reason:
            warnings.append(reason)
    return series_rows, warnings


def _validate_brief_teams(a: str, b: str, season: str) -> tuple[str, str, str | None]:
    pkg = _pkg()
    if not a or not b:
        return "", "", "pass two teams (a, b)"
    if not season:
        return "", "", "season is unresolved"
    try:
        ida = pkg.coerce_team_id(a)
    except ValueError:
        return "", "", pkg.team_error_message(a)
    try:
        idb = pkg.coerce_team_id(b)
    except ValueError:
        return "", "", pkg.team_error_message(b)
    if ida == idb:
        return "", "", "a and b must be different teams"
    abbr_a = str(pkg._abbrev(a) or "").strip().upper()
    abbr_b = str(pkg._abbrev(b) or "").strip().upper()
    return abbr_a, abbr_b, None


@tool(description="Two-team matchup brief with ratings, form, injuries, season series, and win probability.")
async def get_matchup_brief(a: str = "", b: str = "", season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    from ..league import get_ratings
    from ..prediction import get_game_prediction
    season = pkg.resolve_season(season)
    abbr_a, abbr_b, err_val = _validate_brief_teams(str(a or "").strip(), str(b or "").strip(), season)
    if err_val is not None:
        return {"tool": "get_matchup_brief", "ok": False, "error": err_val}
    card_provenance, row_a, row_b, err = await _brief_rating_rows(
        get_ratings, abbr_a, abbr_b, season)
    if err is not None:
        return {"tool": "get_matchup_brief", "ok": False, "error": err}
    form, err2 = await _brief_form(abbr_a, abbr_b, season)
    if err2 is not None:
        return {"tool": "get_matchup_brief", "ok": False, "error": err2}
    injuries, err3 = await _brief_injuries(abbr_a, abbr_b, season)
    if err3 is not None:
        return {"tool": "get_matchup_brief", "ok": False, "error": err3}
    series_rows, warnings = await _brief_series(abbr_a, abbr_b, season)
    pred = await get_game_prediction.ainvoke({"a": abbr_a, "b": abbr_b, "season": season})
    if not isinstance(pred, dict) or not pred.get("ok"):
        err4 = str(pred.get("error") or "prediction unavailable") if isinstance(pred, dict) else ""
        return {"tool": "get_matchup_brief", "ok": False, "error": err4}
    est = pred.get("estimate") or {}
    inputs = pred.get("inputs") or {}
    prediction_provenance = {
        "kind": str(inputs.get("ratings_provenance") or ""),
        "source": str(inputs.get("ratings_source") or ""),
    }
    provenance_err = _provenance_error(card_provenance, prediction_provenance, season)
    if provenance_err is not None:
        return {"tool": "get_matchup_brief", "ok": False, "error": provenance_err}
    pred_meta = pred.get("meta") if isinstance(pred.get("meta"), dict) else {}
    prediction_rows = {
        "matchup": pred.get("matchup") or {}, "win_prob": est.get("win_prob") or {},
        "projected_score": est.get("projected_score") or {},
        "projected_total": est.get("projected_total"),
        "win_prob_ci90": est.get("win_prob_ci90") or {},
        "total_ci90": est.get("total_ci90") or [],
        "margin_ci90": est.get("margin_ci90") or [],
        "ratings_source": prediction_provenance["source"],
        "ratings_provenance": prediction_provenance["kind"],
    }
    from ... import store as _store

    meta = {"source": str(pred_meta.get("source") or "warehouse"), "season": season,
            "ratings_provenance": card_provenance, **_store.warehouse_identity()}
    if warnings:
        meta["warnings"] = warnings
    return {"tool": "get_matchup_brief", "ok": True,
            "rows": {"teams": [abbr_a, abbr_b], "ratings_provenance": card_provenance,
                     "ratings": {abbr_a: _rating_card(row_a), abbr_b: _rating_card(row_b)},
                     "form": form, "injuries": injuries,
                     "season_series": series_rows, "prediction": prediction_rows},
            "meta": meta}


def _scout_tables(con):
    return {r[0] for r in con.execute("SHOW TABLES").fetchall()}


def _scout_section(season, source, rows, note=None):
    out = {"season": season, "source": source, "rows": rows}
    if note:
        out["note"] = note
    return out


def _scout_recent_form(con, tables, tid, abbr, season):
    if "silver_team_games" not in tables:
        return _scout_section(season, "silver_team_games", None,
                              "table not in warehouse")
    rows = con.execute(
        """SELECT g.GAME_DATE, g.MATCHUP, g.WL, g.PTS, o.PTS
           FROM silver_team_games g
           LEFT JOIN silver_team_games o
             ON o._season = g._season AND o.Game_ID = g.Game_ID
            AND o._entity != g._entity AND o._entity LIKE 'team:%'
           WHERE g._season = ? AND g._entity = ? AND g._entity LIKE 'team:%'
           ORDER BY strptime(g.GAME_DATE, '%b %d, %Y') DESC
           LIMIT 10""",
        [season, f"team:{tid}"],
    ).fetchall()
    games = [{"date": str(r[0]), "matchup": r[1], "wl": r[2],
              "pts": r[3], "opp_pts": r[4]} for r in rows]
    wins = sum(1 for g in games if g["wl"] == "W")
    scored = [g["pts"] for g in games if g["pts"] is not None]
    allowed = [g["opp_pts"] for g in games if g["opp_pts"] is not None]
    return _scout_section(season, "silver_team_games", {
        "last10_record": f"{wins}-{len(games) - wins}",
        "games": games,
        "avg_pts": round(sum(scored) / len(scored), 1) if scored else None,
        "avg_opp_pts": round(sum(allowed) / len(allowed), 1) if allowed else None,
    })


def _scout_four_factors(con, tables, tid, season):
    if "silver_team_games" not in tables:
        return _scout_section(season, "silver_team_games", None,
                              "table not in warehouse")
    row = con.execute(
        """SELECT SUM(g.FGM), SUM(g.FG3M), SUM(g.FGA), SUM(g.TOV), SUM(g.OREB),
                  SUM(g.FTM), SUM(g.FTA), SUM(o.FGM), SUM(o.FG3M), SUM(o.FGA),
                  SUM(o.TOV), SUM(o.OREB), SUM(o.FTA), SUM(o.DREB), SUM(g.DREB)
           FROM silver_team_games g
           LEFT JOIN silver_team_games o
             ON o._season = g._season AND o.Game_ID = g.Game_ID
            AND o._entity != g._entity AND o._entity LIKE 'team:%'
           WHERE g._season = ? AND g._entity = ? AND g._entity LIKE 'team:%'""",
        [season, f"team:{tid}"],
    ).fetchone()
    if not row or not row[0]:
        return _scout_section(season, "silver_team_games", None,
                              "no games seeded for this season")
    (fgm, fg3m, fga, tov, oreb, ftm, fta,
     ofgm, ofg3m, ofga, otov, ooreb, ofta, odreb, gdreb) = row
    poss = fga + 0.44 * fta - oreb + tov
    oposs = ofga + 0.44 * ofta - ooreb + otov

    def factors(fg, fg3, atts, t, orb, drb_opp, fts, p):
        return {
            "efg_pct": round((fg + 0.5 * fg3) / atts, 3) if atts else None,
            "tov_pct": round(t / p, 3) if p else None,
            "oreb_pct": round(orb / (orb + drb_opp), 3)
            if (orb or 0) + (drb_opp or 0) else None,
            "ftr": round(fts / atts, 3) if atts else None,
        }

    return _scout_section(season, "silver_team_games", {
        "offense": factors(fgm, fg3m, fga, tov, oreb, odreb, fta, poss),
        "defense": factors(ofgm, ofg3m, ofga, otov, ooreb, gdreb, ofta, oposs),
        "note": "computed from team boxscore aggregates",
    })


def _scout_shot_profile(con, tables, tid, season):
    if "silver_shots" not in tables:
        return _scout_section(season, "silver_shots", None,
                              "table not in warehouse")
    rows = con.execute(
        """SELECT SHOT_ZONE_BASIC,
                  SUM(SHOT_ATTEMPTED_FLAG), SUM(SHOT_MADE_FLAG)
           FROM silver_shots
           WHERE _season = ? AND TEAM_ID = ?
           GROUP BY SHOT_ZONE_BASIC
           ORDER BY 2 DESC""",
        [season, tid],
    ).fetchall()
    if not rows:
        return _scout_section(season, "silver_shots", None,
                              "no shots seeded for this season")
    total = sum(r[1] for r in rows)
    zones = [{"zone": r[0], "fga": r[1],
              "share": round(r[1] / total, 3) if total else None,
              "fg_pct": round(r[2] / r[1], 3) if r[1] else None}
             for r in rows]
    return _scout_section(season, "silver_shots", zones)


def _scout_lineups(con, tables, tid, season):
    if "silver_lineups" not in tables:
        return _scout_section(season, "silver_lineups", None,
                              "table not in warehouse")
    rows = con.execute(
        """SELECT GROUP_NAME, MIN, PLUS_MINUS, W, L
           FROM silver_lineups
           WHERE _season = ? AND TEAM_ID = ?
           ORDER BY MIN DESC LIMIT 3""",
        [season, tid],
    ).fetchall()
    if not rows:
        return _scout_section(season, "silver_lineups", None,
                              "no lineups seeded for this season")
    lineups = [{"group": r[0], "min": r[1], "plus_minus": r[2],
                "w": r[3], "l": r[4],
                "sample": "thin" if (r[1] or 0) < 50 else None}
               for r in rows]
    return _scout_section(season, "silver_lineups", lineups)


def _scout_full_name(tid):
    from .._core import _STATIC_TEAMS as _TEAMS
    for _abbr, full, team_id in _TEAMS:
        if team_id == tid:
            return full
    return ""


def _scout_injuries(con, tables, tid, abbr, season):
    if "silver_injury_entries" in tables:
        rows = con.execute(
            """SELECT PLAYER, STATUS, INJURY, RETURN_ESTIMATE, REPORT_DATE
               FROM silver_injury_entries
               WHERE _season = ? AND (TEAM_ABBR = ? OR TEAM = ?)
               ORDER BY REPORT_DATE DESC LIMIT 15""",
            [season, abbr, abbr],
        ).fetchall()
        return _scout_section(season, "silver_injury_entries",
                              [{"player": r[0], "status": r[1], "injury": r[2],
                                "return_estimate": r[3], "date": str(r[4])}
                               for r in rows])
    if "silver_injuries" in tables:
        rows = con.execute(
            """SELECT injuries FROM silver_injuries
               WHERE upper(display_name) = upper(?)
               ORDER BY _fetched_at DESC LIMIT 1""",
            [_scout_full_name(tid)],
        ).fetchall()
        if rows:
            names, statuses = [], []
            try:
                import ast as _ast
                items = _ast.literal_eval(str(rows[0][0])) or []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    names.append(str((it.get("athlete") or {})
                                     .get("displayName", "?")))
                    statuses.append(str(it.get("status", "")))
            except Exception:
                pass
            return _scout_section(season, "silver_injuries",
                                  [{"player": n, "status": s}
                                   for n, s in zip(names, statuses)],
                                  "raw ESPN blob; silver_injury_entries not seeded")
    return _scout_section(season, "silver_injuries", None,
                          "no injury table in warehouse")


def _scout_h2h(con, tables, tid, oid, season):
    if "silver_team_games" not in tables:
        return _scout_section(season, "silver_team_games", None,
                              "table not in warehouse")
    rows = con.execute(
        """SELECT g.GAME_DATE, g.MATCHUP, g.WL, g.PTS, o.PTS
           FROM silver_team_games g
           JOIN silver_team_games o
             ON o._season = g._season AND o.Game_ID = g.Game_ID
            AND o._entity = ?
           WHERE g._season = ? AND g._entity = ?
           ORDER BY strptime(g.GAME_DATE, '%b %d, %Y') DESC""",
        [f"team:{tid}", season, f"team:{oid}"],
    ).fetchall()
    games = [{"date": str(r[0]), "matchup": r[1], "wl": r[2],
              "pts": r[3], "opp_pts": r[4]} for r in rows]
    wins = sum(1 for g in games if g["wl"] == "W")
    return _scout_section(season, "silver_team_games", {
        "record": f"{wins}-{len(games) - wins}",
        "games": games,
        "note": "record is from the opponent's perspective",
    })


@tool(description="Opponent scouting dossier for game prep. Returns the "
                  "opponent's recent form (last 10), four factors on offense "
                  "and defense, shot-zone profile, top 5-man lineups, current "
                  "injuries, and this season's head-to-head vs team. Each "
                  "section carries its season and warehouse source. Warehouse "
                  "only; sections degrade with a note when a table is not "
                  "seeded for the season.")
def get_opponent_scout(team: str = "", opponent: str = "",
                       season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    if not team or not opponent:
        return {"tool": "get_opponent_scout", "ok": False,
                "error": "pass two teams (team, opponent)"}
    try:
        tid = pkg.coerce_team_id(team)
        oid = pkg.coerce_team_id(opponent)
    except ValueError as exc:
        return {"tool": "get_opponent_scout", "ok": False, "error": str(exc)}
    if tid == oid:
        return {"tool": "get_opponent_scout", "ok": False,
                "error": "team and opponent must be different teams"}
    abbr = str(pkg._abbrev(team) or "").strip().upper()
    oabbr = str(pkg._abbrev(opponent) or "").strip().upper()

    from ... import store as _store
    con = _store.connect(read_only=True)
    try:
        tables = _scout_tables(con)
        rows = {
            "opponent": {"abbrev": oabbr, "team_id": oid},
            "recent_form": _scout_recent_form(con, tables, oid, oabbr, season),
            "four_factors": _scout_four_factors(con, tables, oid, season),
            "shot_profile": _scout_shot_profile(con, tables, oid, season),
            "top_lineups": _scout_lineups(con, tables, oid, season),
            "injuries": _scout_injuries(con, tables, oid, oabbr, season),
            "head_to_head": _scout_h2h(con, tables, tid, oid, season),
        }
    finally:
        con.close()
    return {"tool": "get_opponent_scout", "ok": True, "rows": rows,
            "meta": {"source": "warehouse", "season": season,
                     "team": abbr}}
