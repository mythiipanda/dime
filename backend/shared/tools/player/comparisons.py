import asyncio as _asyncio
import datetime as _dt
import re
import sys
from typing import Any

from langchain_core.tools import tool


def _pkg():
    return sys.modules[__package__]


def zone_diet(rows: object) -> dict[str, float | None]:
    pkg = _pkg()
    try:
        items = list(rows or [])
    except TypeError:
        return {"rim_share": None, "three_share": None}
    rim = None
    three = 0.0
    found_three = False
    for r in items:
        if not isinstance(r, dict):
            continue
        try:
            share = float(r.get("SHARE", r.get("share", 0)) or 0)
        except (TypeError, ValueError):
            continue
        zone = str(r.get("zone", ""))
        if zone in ("Restricted Area", "rim"):
            rim = round(share, 3)
        if pkg._is_three_zone(zone):
            three += share
            found_three = True
    return {"rim_share": rim, "three_share": round(three, 3) if found_three else None}


def pair_history(wowy: object) -> dict[str, object]:
    if not isinstance(wowy, dict) or not wowy.get("ok"):
        err = wowy.get("error", "wowy failed") if isinstance(wowy, dict) else "wowy failed"
        return {"teammates": True, "both_on_net": None, "both_on_minutes": 0, "note": str(err)[:160]}
    both = next((r for r in wowy.get("rows", []) or [] if isinstance(r, dict) and r.get("split") == "Both ON"), None)
    if not both:
        return {"teammates": True, "both_on_net": None, "both_on_minutes": 0, "note": "No shared court time found."}
    try:
        net = round(float(both.get("net_rating")), 1)
    except (TypeError, ValueError):
        net = None
    try:
        mins = round(float(both.get("minutes") or 0), 1)
    except (TypeError, ValueError):
        mins = 0
    return {
        "teammates": True,
        "both_on_net": net,
        "both_on_minutes": mins,
        "note": f"Shared court net {net:+.1f} across {mins} minutes." if net is not None else "Shared court time found.",
    }


def portability_fit(a: dict[str, Any], b: dict[str, Any]) -> dict[str, str]:
    pkg = _pkg()
    au, bu = pkg._num(a.get("usg_pct")), pkg._num(b.get("usg_pct"))
    an, bn = pkg._num(a.get("net_onoff")), pkg._num(b.get("net_onoff"))
    na = str(a.get("name") or "A")
    nb = str(b.get("name") or "B")
    verdict: dict[str, str] | None = None
    if au is not None and bu is not None and au >= 30 and bu >= 30:
        verdict = {"fit": "risk", "note": f"{na} and {nb} both use 30 pct or more. One must bend."}
    if verdict is None:
        for high, low, hn, ln in ((a, b, na, nb), (b, a, nb, na)):
            hu, lu = pkg._num(high.get("usg_pct")), pkg._num(low.get("usg_pct"))
            lt = pkg._num(low.get("ts_pct"))
            if hu is not None and lu is not None and lt is not None and hu >= 30 and lu <= 25 and lt >= 0.60:
                verdict = {
                    "fit": "scalable",
                    "note": f"{ln} profiles as a low usage efficient fit next to {hn}.",
                }
                break
    if verdict is None and an is not None and bn is not None and abs(an - bn) >= 5:
        lead = na if an > bn else nb
        verdict = {"fit": "leans driver", "note": f"On off tilts to {lead} by {abs(an - bn):.1f} per 100."}
    if verdict is None:
        verdict = {"fit": "neutral", "note": "No clear usage or on off tilt."}
    ar, br = pkg._num(a.get("rim_share")), pkg._num(b.get("rim_share"))
    ath, bth = pkg._num(a.get("three_share")), pkg._num(b.get("three_share"))
    if ar is not None and br is not None and ath is not None and bth is not None:
        verdict["note"] += f" Shot diet rim {ar:.0%} vs {br:.0%}, three {ath:.0%} vs {bth:.0%}."
    return verdict


def _player_season_team(pid: int, season: str) -> str:
    try:
        rows = _pkg()._read_df(
            "SELECT TEAM FROM silver_player_season WHERE _season = ? AND CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR) LIMIT 1",
            [season, str(pid)],
        )
    except Exception:
        return ""
    if not rows:
        return ""
    return str(rows[0].get("TEAM") or "")


def _format_h2h_note(
    left: dict[str, Any], right: dict[str, Any], ta: str, tb: str,
    meetings: list[dict[str, Any]], a_games: list, b_games: list,
) -> str:
    if meetings:
        a_pts = [m["a_pts"] for m in meetings if m["a_pts"] is not None]
        b_pts = [m["b_pts"] for m in meetings if m["b_pts"] is not None]
        note = f"Different teams; they shared the floor in {len(meetings)} game(s) this season"
        if a_pts:
            note += f" ({left.get('name') or 'player A'} averaged {sum(a_pts) / len(a_pts):.1f} pts in those games)"
        if b_pts:
            note += f"; {right.get('name') or 'player B'} averaged {sum(b_pts) / len(b_pts):.1f} pts"
        return note + "."
    if a_games or b_games:
        return f"Different teams; {ta} and {tb} met, but the two players did not appear in the same game."
    return f"Different teams; {ta} and {tb} did not meet this season."


_CANONICAL_GID = re.compile(r"^\d{10}$")


def _meeting_date(raw) -> str:
    s = str(raw or "").strip()
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return _dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return s


def _games_by_meeting_date(games) -> dict[str, Any]:
    by_date: dict[str, Any] = {}
    for g in games:
        key = _meeting_date(g.get("GAME_DATE"))
        cur = by_date.get(key)
        if cur is None or (
            _CANONICAL_GID.match(str(g.get("Game_ID") or ""))
            and not _CANONICAL_GID.match(str(cur.get("Game_ID") or ""))
        ):
            by_date[key] = g
    return by_date


def _different_teams_pair(left: dict[str, Any], right: dict[str, Any], season: str) -> dict[str, Any]:
    season = _pkg().resolve_season(season)
    from ..headtohead import HeadToHeadSchemaError, _load_player_games, vs_opponent

    lid, rid = left.get("player_id"), right.get("player_id")
    ta, tb = str(left.get("team") or ""), str(right.get("team") or "")
    base: dict[str, Any] = {"teammates": False, "both_on_net": None, "both_on_minutes": 0}
    na = str(left.get("name") or "player A")
    nb = str(right.get("name") or "player B")
    if not (lid and rid and ta and tb):
        base["note"] = (
            f"Team matchup could not be determined from game logs; comparing {na} and {nb} "
            f"on season stats for {season} without head-to-head meetings."
        )
        return base
    try:
        a_games = vs_opponent(_load_player_games(int(lid), season), tb)
        b_games = vs_opponent(_load_player_games(int(rid), season), ta)
    except HeadToHeadSchemaError as exc:
        base["note"] = f"{exc}; comparing {na} and {nb} on season stats for {season}."
        return base
    except Exception:
        base["note"] = "Different teams; meeting logs unavailable."
        return base
    a_by_date = _games_by_meeting_date(a_games)
    b_by_date = _games_by_meeting_date(b_games)
    shared = sorted(set(a_by_date) & set(b_by_date))
    meetings = []
    for day in shared:
        ga, gb = a_by_date[day], b_by_date[day]
        gid = str(ga.get("Game_ID"))
        meetings.append(
            {
                "game_id": gid,
                "date": ga.get("GAME_DATE"),
                "matchup": ga.get("MATCHUP"),
                "a_pts": ga.get("PTS"),
                "a_reb": ga.get("REB"),
                "a_ast": ga.get("AST"),
                "a_wl": ga.get("WL"),
                "b_pts": gb.get("PTS"),
                "b_reb": gb.get("REB"),
                "b_ast": gb.get("AST"),
            }
        )
    base["h2h_meetings"] = meetings
    base["note"] = _format_h2h_note(left, right, ta, tb, meetings, a_games, b_games)
    return base


async def _compare_subresults(who, pid, season, games):
    pkg = _pkg()
    job_defs: dict[str, tuple[Any, dict[str, Any]]] = {}
    if not games:
        job_defs["intel"] = (pkg.get_player_intel, {"player_id": pid, "season": season})
    job_defs["last"] = (pkg.get_last_x, {"player_id": pid, "n": 5, "season": season})
    job_defs["adv"] = (pkg.get_advanced, {"player": pid, "season": season})
    job_defs["zones"] = (pkg.get_shot_zones, {"player_id": pid, "season": season})

    async def _invoke(label: str, subtool: Any, args: dict[str, Any]) -> Any:
        last: Exception | None = None
        for attempt in range(4):
            try:
                return await subtool.ainvoke(args)
            except Exception as exc:
                last = exc
                pkg._logger.warning("get_compare sub-call %s failed for %s (try %d/4): %r", label, who, attempt + 1, exc)
                await _asyncio.sleep(0.2 * (attempt + 1))
        pkg._logger.warning("get_compare sub-call %s failed 4 times for %s: %r", label, who, last)
        return last

    results = await _asyncio.gather(*(_invoke(k, t, a) for k, (t, a) in job_defs.items()))
    res: dict[str, Any] = {}
    sub_errors: dict[str, str] = {}
    for key, val in zip(job_defs, results):
        if isinstance(val, BaseException):
            res[key] = {}
            sub_errors[key] = f"{type(val).__name__}: {str(val)[:160]}"
        else:
            res[key] = val if isinstance(val, dict) else {}
    return res, sub_errors


def _compare_team_record(team_abbr, pid, season) -> str:
    pkg = _pkg()
    record = ""
    _lookup = team_abbr or pkg._player_season_team(pid, season)
    if _lookup:
        try:
            from nba_api.stats.static import teams as _static

            hit = next((t for t in _static.get_teams() if _lookup in (t["abbreviation"], t["full_name"])), None)
            full = hit["full_name"] if hit else ""
            nick = full.split()[-1] if full else ""
        except Exception:
            full, nick = "", ""
        try:
            row = pkg._read_df(
                "SELECT WINS, LOSSES FROM silver_standings WHERE _season = ? AND (TeamName = ? OR TeamName = ?) LIMIT 1",
                [season, nick, full],
            )
            if row and row[0].get("WINS") is not None:
                record = f"{row[0]['WINS']}-{row[0]['LOSSES']}"
        except Exception:
            pass
    return record


def _compare_rapm(pid, season):
    try:
        rrows = _pkg()._read_df(
            "SELECT rapm FROM silver_rapm WHERE _season = ? AND CAST(player_id AS VARCHAR) = CAST(? AS VARCHAR) AND rapm IS NOT NULL LIMIT 1",
            [season, str(pid)],
        )
        if rrows and rrows[0].get("rapm") is not None:
            return round(float(rrows[0]["rapm"]), 2)
    except Exception:
        pass
    return None


def _compare_clutch_pts(pid, who, season):
    try:
        from nba_api.stats.static import players as _static_p

        canon = next((p["full_name"] for p in _static_p.get_players() if p.get("id") == pid), who)
        crows = _pkg()._read_df(
            "SELECT PTS FROM silver_clutch WHERE _season = ? AND PLAYER_NAME = ? LIMIT 1",
            [season, canon],
        )
        if crows and crows[0].get("PTS") is not None:
            return int(crows[0]["PTS"])
    except Exception:
        pass
    return None


def _compare_net_onoff(oo):
    net_onoff = None
    for r in oo.get("rows", []) or []:
        if isinstance(r, dict) and r.get("Stat") == "Pts per 100 Possessions":
            try:
                net_onoff = round(float(r.get("On") or 0) - float(r.get("Off") or 0), 1)
            except (TypeError, ValueError):
                pass
            break
    return net_onoff


async def _compare_one(who: str, season: str) -> dict[str, Any]:
    from collections import Counter as _Counter

    pkg = _pkg()
    pid = pkg.coerce_player_id(who)
    loop = _asyncio.get_running_loop()

    def _gamelogs() -> list:
        try:
            return pkg._read_df(
                "SELECT * FROM silver_player_gamelogs WHERE _season = ? AND _entity = ?",
                [season, f"player:{pid}"],
            )
        except Exception:
            return []

    def _team_id(abbr: str) -> int:
        if abbr:
            try:
                return pkg.coerce_team_id(abbr)
            except Exception:
                pass
        try:
            from nba_api.stats.endpoints import CommonPlayerInfo

            info = CommonPlayerInfo(player_id=pid, timeout=10).get_data_frames()[0]
            return int(info["TEAM_ID"].iloc[0])
        except Exception:
            return 0

    def _onoff_rows() -> list:
        try:
            return pkg._read_df(
                "SELECT * FROM silver_on_off WHERE _season = ? AND _entity = ?",
                [season, f"player:{pid}"],
            )
        except Exception:
            return []

    games = await loop.run_in_executor(None, _gamelogs)
    res, sub_errors = await pkg._compare_subresults(who, pid, season, games)
    if not games:
        _intel = res.get("intel", {}) or {}
        _imeta = _intel.get("meta") or {}
        games = [] if _imeta.get("coverage") == "season_line" else (_intel.get("rows", []) or [])
    if not games:
        return {
            "name": pkg._display_name(who),
            "player_id": pid,
            "missing_population": True,
            "missing": ["season_game_logs"],
            "sub_call_errors": sub_errors,
        }
    matchup = [str(g.get("MATCHUP") or "").split(" ")[0] for g in games]
    team_abbr = (_Counter(m for m in matchup if m).most_common(1) or [("", 0)])[0][0]
    team = await loop.run_in_executor(None, _team_id, team_abbr)
    oo = {"rows": _onoff_rows()}
    if not any(isinstance(r, dict) and r.get("Stat") == "Pts per 100 Possessions" for r in oo.get("rows", []) or []):
        if team:
            cand = await pkg.get_on_off.ainvoke({"player_id": pid, "team_id": team, "season": season})
            if isinstance(cand, dict):
                oo = cand
    last = res.get("last", {})
    adv = res.get("adv", {})
    adv_rows = adv.get("rows", {}) if adv.get("ok") else {}
    try:
        zones = res.get("zones", {})
        diet = pkg.zone_diet(zones.get("rows", [])) if zones.get("ok") else {"rim_share": None, "three_share": None}
    except Exception:
        diet = {"rim_share": None, "three_share": None}

    missing: list[str] = []
    if diet.get("three_share") is None:
        missing.append("three_share")
    if diet.get("rim_share") is None:
        missing.append("rim_share")
    gp = len(games)

    def _sum(key: str) -> float:
        return sum(float(g.get(key) or 0) for g in games)

    def _avg(key: str) -> float:
        return round(_sum(key) / max(gp, 1), 1)

    fgm, fga = _sum("FGM"), _sum("FGA")
    fg3m = _sum("FG3M")
    ftm, fta = _sum("FTM"), _sum("FTA")
    pts_total = _sum("PTS")
    ts = round(pts_total / max(2 * (fga + 0.44 * fta), 1), 3)
    efg = round((fgm + 0.5 * fg3m) / max(fga, 1), 3)
    ft_points_share = round(ftm / max(pts_total, 1), 3)
    fg_points_share = round((pts_total - ftm) / max(pts_total, 1), 3)
    net_onoff = pkg._compare_net_onoff(oo)
    return {
        "name": pkg._display_name(who),
        "player_id": pid,
        "team": team_abbr,
        "team_record": pkg._compare_team_record(team_abbr, pid, season),
        "gp": gp,
        "ppg": round(pts_total / max(gp, 1), 1),
        "rpg": _avg("REB"),
        "apg": _avg("AST"),
        "spg": _avg("STL"),
        "bpg": _avg("BLK"),
        "mpg": _avg("MIN"),
        "tov": _avg("TOV"),
        "fg_pct": round(fgm / max(fga, 1), 3),
        "fg3_pct": round(_sum("FG3M") / max(_sum("FG3A"), 1), 3),
        "ft_pct": round(ftm / max(fta, 1), 3),
        "ts_pct": ts,
        "efg_pct": efg,
        "ft_points_share": ft_points_share,
        "fg_points_share": fg_points_share,
        "usg_pct": adv_rows.get("USG_PCT"),
        "tov_pct": adv_rows.get("TM_TOV_PCT"),
        "pie": adv_rows.get("PIE"),
        "clutch_pts": pkg._compare_clutch_pts(pid, who, season),
        "net_onoff": net_onoff,
        "rapm": pkg._compare_rapm(pid, season),
        "rim_share": diet.get("rim_share"),
        "three_share": diet.get("three_share"),
        "last5": [g.get("PTS", 0) for g in last.get("rows", [])],
        "missing": missing + (["net_onoff"] if net_onoff is None else []),
        "sub_call_errors": sub_errors,
    }


@tool(description="Side-by-side compare of two players. Names or ids. One call.")
async def get_compare(a: str, b: str, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    left, right = await _asyncio.gather(pkg._compare_one(a, season), pkg._compare_one(b, season))
    missing_sides = [side for side, item in (("a", left), ("b", right)) if item.get("missing_population")]
    if missing_sides:
        return {
            "tool": "get_compare",
            "ok": False,
            "error": f"player comparison source population is missing for side(s): {', '.join(missing_sides)}",
            "rows": {"a": left, "b": right},
            "meta": {"source": "warehouse", "season": season, "missing_sides": missing_sides},
        }
    ta, tb = str(left.get("team") or ""), str(right.get("team") or "")
    if ta and ta == tb:
        try:
            wowy = await pkg.get_wowy.ainvoke(
                {"player_ids": f"{left.get('player_id')},{right.get('player_id')}", "team_id": ta, "season": season}
            )
            pair: dict[str, object] = pkg.pair_history(wowy)
        except Exception as exc:
            pair = {"teammates": True, "both_on_net": None, "both_on_minutes": 0, "note": str(exc)[:160]}
    else:
        pair = pkg._different_teams_pair(left, right, season)
    sub_call_errors: dict[str, str] = {}
    for side, player in (("a", left), ("b", right)):
        for key, err in (player.get("sub_call_errors") or {}).items():
            sub_call_errors[f"{side}.{key}"] = err
    return {
        "tool": "get_compare",
        "ok": True,
        "rows": {"a": left, "b": right, "fit": pkg.portability_fit(left, right), "pair": pair},
        "meta": {
            "source": "nba_api+pbpstats",
            "season": season,
            "fit_rule": (
                "both usg>=30 risk; high usg plus low usg with ts>=0.60 scalable; "
                "on off gap>=5 leans driver; rim plus three shares append shot diet"
            ),
            "pair_rule": "same team abbrev runs wowy, Both ON net plus minutes",
            "sub_call_errors": sub_call_errors,
        },
    }


def _metric_row(
    metric: str, label: str, method: str, a: object, b: object,
    na: str, nb: str, higher_wins: bool = True,
) -> dict[str, Any]:
    def _f(v: object) -> float | None:
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    fa, fb = _f(a), _f(b)
    if fa is not None and fb is not None and max(abs(fa), abs(fb)) <= 1.5:
        eps = 0.02
    else:
        eps = 0.01 * max(abs(fa or 0), abs(fb or 0), 1.0)
    if fa is None or fb is None:
        leader = "na"
    elif abs(fa - fb) < eps:
        leader = "tie"
    elif (fa > fb) == higher_wins:
        leader = "a"
    else:
        leader = "b"
    who = na if leader == "a" else nb if leader == "b" else ""
    if who:
        note = f"{who} leads {label}."
    elif leader == "tie" and fa is not None and fb is not None:
        note = f"{label} effectively even (gap within noise)."
    else:
        note = f"{label} tied or missing."
    return {"metric": metric, "label": label, "method": method, "a": fa, "b": fb, "leader": leader, "note": note}


def _metric_player_stats(pid: int, name: str, season: str) -> dict[str, Any]:
    pkg = _pkg()
    out: dict[str, Any] = {}
    try:
        r = pkg._read_df(
            "SELECT RAPTOR_OFFENSE, RAPTOR_DEFENSE, RAPTOR_TOTAL, WAR_TOTAL, _season "
            "FROM silver_raptor_player WHERE LOWER(PLAYER_NAME) = LOWER(?) ORDER BY _season DESC LIMIT 1",
            [name],
        )
        if r:
            out.update({k: r[0].get(k) for k in ("RAPTOR_OFFENSE", "RAPTOR_DEFENSE", "RAPTOR_TOTAL", "WAR_TOTAL")})
            out["raptor_season"] = r[0].get("_season")
    except Exception:
        pass
    try:
        r = pkg._read_df(
            "SELECT rapm FROM silver_rapm WHERE _season = ? AND CAST(player_id AS VARCHAR) = CAST(? AS VARCHAR) AND rapm IS NOT NULL LIMIT 1",
            [season, str(pid)],
        )
        if r and r[0].get("rapm") is not None:
            out["rapm"] = round(float(r[0]["rapm"]), 2)
    except Exception:
        pass
    try:
        r = pkg._read_df(
            'SELECT "On", "Off" FROM silver_on_off WHERE _season = ? AND _entity = ? AND Stat = ? LIMIT 1',
            [season, f"player:{pid}", "Pts per 100 Possessions"],
        )
        if r:
            out["onoff"] = round(float(r[0].get("On") or 0) - float(r[0].get("Off") or 0), 1)
    except Exception:
        pass
    try:
        r = pkg._read_df(
            "SELECT PIE, TS_PCT, USG_PCT FROM silver_advanced WHERE _season = ? AND CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR) LIMIT 1",
            [season, str(pid)],
        )
        if r:
            out.update({k: r[0].get(k) for k in ("PIE", "TS_PCT", "USG_PCT")})
    except Exception:
        pass
    return out


def _build_metric_rows(ma: dict[str, Any], mb: dict[str, Any], na: str, nb: str, raptor_current: bool) -> list[dict[str, Any]]:
    specs = (
        ("raptor", "RAPTOR", "box plus on-off, FiveThirtyEight", "RAPTOR_TOTAL"),
        ("raptor_o", "RAPTOR offense", "box plus on-off", "RAPTOR_OFFENSE"),
        ("raptor_d", "RAPTOR defense", "box plus on-off", "RAPTOR_DEFENSE"),
        ("war", "WAR", "wins above replacement", "WAR_TOTAL"),
        ("rapm", "RAPM-lite", "ridge on stint differentials", "rapm"),
        ("onoff", "on-off net", "lineup splits, noisy", "onoff"),
        ("pie", "PIE", "box-score share", "PIE"),
        ("ts", "true shooting", "scoring efficiency", "TS_PCT"),
    )
    rows = [_metric_row(m, lbl, meth, ma.get(col), mb.get(col), na, nb) for m, lbl, meth, col in specs]
    for row in rows:
        row["eligible_for_verdict"] = row["metric"] not in {"raptor", "raptor_o", "raptor_d", "war"} or raptor_current
        if not row["eligible_for_verdict"] and row["leader"] in ("a", "b"):
            row["note"] += " Historical context only; excluded from verdict."
    return rows


def _score_metric_verdict(rows: list[dict[str, Any]], na: str, nb: str, stale: str) -> tuple[str, str]:
    decided = [r for r in rows if r["leader"] in ("a", "b") and r["eligible_for_verdict"]]
    va = sum(1 for r in decided if r["leader"] == "a")
    vb = sum(1 for r in decided if r["leader"] == "b")
    if not decided:
        agreement, verdict = "none", "No current-season shared metrics cover both players."
    elif va == len(decided):
        agreement, verdict = "agree", f"Every verdict-eligible metric favors {na}."
    elif vb == len(decided):
        agreement, verdict = "agree", f"Every verdict-eligible metric favors {nb}."
    else:
        split = [r["label"] for r in decided if r["leader"] == ("a" if va >= vb else "b")]
        agreement = "split"
        verdict = (
            f"Metrics split {va}-{vb}. "
            f"{na if va >= vb else nb} leads {', '.join(split[:3])}; "
            "check RAPTOR defense vs on-off noise before concluding."
        )
    if stale:
        verdict += f" RAPTOR rows are {stale} vintage."
    return agreement, verdict


@tool(
    description="Cross-metric adjudication for two players. Referees impact metrics.\n\nPulls RAPTOR, RAPM-lite, on-off net, and PIE/TS from the warehouse and\nreports which metrics agree. EPM, LEBRON, DARKO, and DRIP are listed\nas unavailable, never invented."
)
def compare_metrics(a: str | int, b: str | int, season: str | None = None) -> dict[str, Any]:
    import unicodedata as _ud
    from nba_api.stats.static import players as _static_p

    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        pida = pkg.coerce_player_id(a)
        pidb = pkg.coerce_player_id(b)
    except ValueError as exc:
        return {"tool": "compare_metrics", "ok": False, "error": str(exc)[:160]}
    names = {p.get("id"): p.get("full_name", "") for p in _static_p.get_players()}

    def _ascii(s: str) -> str:
        return "".join(c for c in _ud.normalize("NFKD", s or "") if not _ud.combining(c))

    na = _ascii(str(names.get(pida, a)))
    nb = _ascii(str(names.get(pidb, b)))
    ma, mb = _metric_player_stats(pida, na, season), _metric_player_stats(pidb, nb, season)
    vintage = {s for s in (ma.get("raptor_season"), mb.get("raptor_season")) if s}
    stale = sorted(vintage)[-1] if vintage and sorted(vintage)[-1] != season else ""
    raptor_current = bool(vintage) and vintage == {season}
    rows = _build_metric_rows(ma, mb, na, nb, raptor_current)
    agreement, verdict = _score_metric_verdict(rows, na, nb, stale)
    return {
        "tool": "compare_metrics",
        "ok": True,
        "rows": {
            "a": na,
            "b": nb,
            "metrics": rows,
            "agreement": agreement,
            "verdict": verdict,
            "unavailable": [{"metric": m, "note": "not in warehouse, never estimated"} for m in ("EPM", "LEBRON", "DARKO", "DRIP")],
        },
        "meta": {
            "source": "warehouse",
            "season": season,
            "raptor_season_a": ma.get("raptor_season"),
            "raptor_season_b": mb.get("raptor_season"),
            "raptor_gap": not raptor_current,
            "raptor_coverage": "RAPTOR ends 2021-22; later seasons read as gaps",
        },
    }
