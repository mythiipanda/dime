"""Player desk. Intel, form, comps, zones, splits, possession splits."""

from typing import Any
import asyncio as _asyncio
import polars as pl
from langchain_core.tools import tool

from .. import store
from ..sources import nba_stats
from ._core import SEASON, TTL_GAMELOG, TTL_LEADERS, TTL_PBPSTATS, _warehouse_or_live, coerce_player_id, coerce_team_id


def _num(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_three_zone(name: object) -> bool:
    z = str(name or "").lower()
    return "3" in z or "corner" in z or "break" in z


def zone_diet(rows: object) -> dict[str, float | None]:
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
        if zone == "Restricted Area":
            rim = round(share, 3)
        if _is_three_zone(zone):
            three += share
            found_three = True
    return {"rim_share": rim, "three_share": round(three, 3) if found_three else None}


def pair_history(wowy: object) -> dict[str, object]:
    if not isinstance(wowy, dict) or not wowy.get("ok"):
        err = wowy.get("error", "wowy failed") if isinstance(wowy, dict) else "wowy failed"
        return {"teammates": True, "both_on_net": None,
                "both_on_minutes": 0, "note": str(err)[:160]}
    both = next((r for r in wowy.get("rows", []) or []
                 if isinstance(r, dict) and r.get("split") == "Both ON"), None)
    if not both:
        return {"teammates": True, "both_on_net": None,
                "both_on_minutes": 0, "note": "No shared court time found."}
    try:
        net = round(float(both.get("net_rating")), 1)
    except (TypeError, ValueError):
        net = None
    try:
        mins = round(float(both.get("minutes") or 0), 1)
    except (TypeError, ValueError):
        mins = 0
    return {"teammates": True, "both_on_net": net, "both_on_minutes": mins,
            "note": f"Shared court net {net:+.1f} across {mins} minutes."
            if net is not None else "Shared court time found."}


def portability_fit(a: dict[str, Any], b: dict[str, Any]) -> dict[str, str]:
    au, bu = _num(a.get("usg_pct")), _num(b.get("usg_pct"))
    at, bt = _num(a.get("ts_pct")), _num(b.get("ts_pct"))
    an, bn = _num(a.get("net_onoff")), _num(b.get("net_onoff"))
    na = str(a.get("name") or "A")
    nb = str(b.get("name") or "B")
    verdict: dict[str, str] | None = None
    if au is not None and bu is not None and au >= 30 and bu >= 30:
        verdict = {"fit": "risk",
                   "note": f"{na} and {nb} both use 30 pct or more. One must bend."}
    if verdict is None:
        for high, low, hn, ln in ((a, b, na, nb), (b, a, nb, na)):
            hu, lu = _num(high.get("usg_pct")), _num(low.get("usg_pct"))
            lt = _num(low.get("ts_pct"))
            if hu is not None and lu is not None and lt is not None:
                if hu >= 30 and lu <= 25 and lt >= 0.60:
                    verdict = {"fit": "scalable",
                               "note": f"{ln} profiles as a low usage efficient fit next to {hn}."}
                    break
    if verdict is None:
        if an is not None and bn is not None and abs(an - bn) >= 5:
            lead = na if an > bn else nb
            verdict = {"fit": "leans driver",
                       "note": f"On off tilts to {lead} by {abs(an - bn):.1f} per 100."}
    if verdict is None:
        verdict = {"fit": "neutral", "note": "No clear usage or on off tilt."}
    ar, br = _num(a.get("rim_share")), _num(b.get("rim_share"))
    ath, bth = _num(a.get("three_share")), _num(b.get("three_share"))
    if ar is not None and br is not None and ath is not None and bth is not None:
        verdict["note"] += f" Shot diet rim {ar:.0%} vs {br:.0%}, three {ath:.0%} vs {bth:.0%}."
    return verdict


def _read_df(sql: str, params: list, tries: int = 5) -> list[dict[str, Any]]:
    """Warehouse read with retries. Concurrent writers briefly lock the file."""
    import time as _time

    last: Exception | None = None
    for _ in range(tries):
        try:
            con = store.connect()
            try:
                return (
                    con.execute(sql, params)
                    .fetchdf()
                    .to_dict(orient="records")
                )
            finally:
                con.close()
        except Exception as exc:
            last = exc
            _time.sleep(0.3)
    raise last or RuntimeError("warehouse read failed")


@tool
async def get_compare(
    a: str, b: str, season: str = SEASON,
) -> dict[str, Any]:
    """Side-by-side compare of two players. Names or ids. One call."""
    async def one(who: str) -> dict[str, Any]:
        from collections import Counter as _Counter

        pid = coerce_player_id(who)
        loop = _asyncio.get_running_loop()

        def _gamelogs() -> list:
            try:
                return _read_df(
                    "SELECT * FROM silver_player_gamelogs"
                    " WHERE _season = ? AND _entity = ?",
                    [season, f"player:{pid}"],
                )
            except Exception:
                return []

        def _team_id() -> int:
            try:
                from nba_api.stats.endpoints import CommonPlayerInfo

                info = CommonPlayerInfo(player_id=pid, timeout=10).get_data_frames()[0]
                return int(info["TEAM_ID"].iloc[0])
            except Exception:
                return 0

        def _onoff_rows() -> list:
            try:
                return _read_df(
                    "SELECT * FROM silver_on_off WHERE _season = ? AND _entity = ?",
                    [season, f"player:{pid}"],
                )
            except Exception:
                return []

        games, team = await _asyncio.gather(
            loop.run_in_executor(None, _gamelogs),
            loop.run_in_executor(None, _team_id),
        )
        jobs: dict[str, Any] = {}
        if not games:
            jobs["intel"] = get_player_intel.ainvoke(
                {"player_id": pid, "season": season})
        jobs["last"] = get_last_x.ainvoke(
            {"player_id": pid, "n": 5, "season": season})
        jobs["adv"] = get_advanced.ainvoke({"player": pid, "season": season})
        jobs["zones"] = get_shot_zones.ainvoke(
            {"player_id": pid, "season": season})
        results = await _asyncio.gather(*jobs.values(), return_exceptions=True)
        res = {k: (v if isinstance(v, dict) else {})
               for k, v in zip(jobs, results)}
        if not games:
            games = res.get("intel", {}).get("rows", []) or []
        oo = {"rows": _onoff_rows()}
        if not any(isinstance(r, dict)
                   and r.get("Stat") == "Pts per 100 Possessions"
                   for r in oo.get("rows", []) or []):
            if team:
                cand = await get_on_off.ainvoke(
                    {"player_id": pid, "team_id": team, "season": season})
                if isinstance(cand, dict):
                    oo = cand
        last = res.get("last", {})
        adv = res.get("adv", {})
        adv_rows = adv.get("rows", {}) if adv.get("ok") else {}
        try:
            zones = res.get("zones", {})
            diet = zone_diet(zones.get("rows", [])) if zones.get("ok") else {
                "rim_share": None, "three_share": None}
        except Exception:
            diet = {"rim_share": None, "three_share": None}
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
        matchup = [str(g.get("MATCHUP") or "").split(" ")[0] for g in games]
        team_abbr = (_Counter(m for m in matchup if m).most_common(1)
                     or [("", 0)])[0][0]
        record, net_onoff, rapm = "", None, None
        if team_abbr:
            try:
                from nba_api.stats.static import teams as _static

                full = next(
                    (t["full_name"] for t in _static.get_teams()
                     if t["abbreviation"] == team_abbr), "")
                nick = full.split()[-1] if full else ""
            except Exception:
                full, nick = "", ""
            try:
                row = _read_df(
                    "SELECT WINS, LOSSES FROM silver_standings"
                    " WHERE _season = ? AND (TeamName = ? OR TeamName = ?)"
                    " LIMIT 1",
                    [season, nick, full],
                )
                if row and row[0].get("WINS") is not None:
                    record = f"{row[0]['WINS']}-{row[0]['LOSSES']}"
            except Exception:
                pass
            try:
                rrows = _read_df(
                    "SELECT rapm FROM silver_rapm"
                    " WHERE _season = ? AND CAST(player_id AS VARCHAR)"
                    " = CAST(? AS VARCHAR) AND rapm IS NOT NULL"
                    " LIMIT 1",
                    [season, str(pid)],
                )
                if rrows and rrows[0].get("rapm") is not None:
                    rapm = round(float(rrows[0]["rapm"]), 2)
            except Exception:
                pass
            clutch_pts = None
            try:
                from nba_api.stats.static import players as _static_p

                canon = next(
                    (p["full_name"] for p in _static_p.get_players()
                     if p.get("id") == pid), who)
                crows = _read_df(
                    "SELECT PTS FROM silver_clutch"
                    " WHERE _season = ? AND PLAYER_NAME = ? LIMIT 1",
                    [season, canon],
                )
                if crows and crows[0].get("PTS") is not None:
                    clutch_pts = int(crows[0]["PTS"])
            except Exception:
                pass
        for r in oo.get("rows", []) or []:
            if isinstance(r, dict) and r.get("Stat") == "Pts per 100 Possessions":
                try:
                    net_onoff = round(float(r.get("On") or 0)
                                      - float(r.get("Off") or 0), 1)
                except (TypeError, ValueError):
                    pass
                break
        return {
            "name": who,
            "player_id": pid,
            "team": team_abbr,
            "team_record": record,
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
            "usg_pct": adv_rows.get("USG_PCT"),
            "tov_pct": adv_rows.get("TM_TOV_PCT"),
            "pie": adv_rows.get("PIE"),
            "clutch_pts": clutch_pts,
            "net_onoff": net_onoff,
            "rapm": rapm,
            "rim_share": diet.get("rim_share"),
            "three_share": diet.get("three_share"),
            "last5": [g.get("PTS", 0) for g in last.get("rows", [])],
        }

    left, right = await _asyncio.gather(one(a), one(b))
    ta, tb = str(left.get("team") or ""), str(right.get("team") or "")
    if ta and ta == tb:
        try:
            wowy = await get_wowy.ainvoke(
                {"player_ids": f"{left.get('player_id')},{right.get('player_id')}",
                 "team_id": ta, "season": season})
            pair: dict[str, object] = pair_history(wowy)
        except Exception as exc:
            pair = {"teammates": True, "both_on_net": None,
                    "both_on_minutes": 0, "note": str(exc)[:160]}
    else:
        pair = {"teammates": False, "both_on_net": None,
                "both_on_minutes": 0, "note": "Different teams, no shared court."}
    return {"tool": "get_compare", "ok": True,
            "rows": {"a": left, "b": right, "fit": portability_fit(left, right),
                     "pair": pair},
            "meta": {"source": "nba_api+pbpstats", "season": season,
                     "fit_rule": "both usg>=30 risk; high usg plus low usg with ts>=0.60 scalable; on off gap>=5 leans driver; rim plus three shares append shot diet",
                     "pair_rule": "same team abbrev runs wowy, Both ON net plus minutes"}}


@tool
def get_player_intel(player_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Game log plus shot sample for one player id. Warehouse first."""
    player_id = coerce_player_id(player_id)
    rows, meta = _warehouse_or_live(
        "silver_player_gamelogs", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: nba_stats.player_gamelog(player_id, season), season,
        entity=f"player:{player_id}", ttl_s=TTL_GAMELOG,
    )
    return {"tool": "get_player_intel", "ok": True, "rows": rows, "meta": meta}


@tool
def get_playoff_intel(player_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Playoff game log for one player. Names or ids. Warehouse first."""
    try:
        pid = coerce_player_id(player_id)
    except ValueError:
        return {"tool": "get_playoff_intel", "ok": False,
                "error": f"unknown player: {player_id}"}
    rows, meta = _warehouse_or_live(
        "silver_playoff_gamelogs", "_season = ? AND _entity = ?",
        [season, f"player:{pid}"],
        lambda: nba_stats.player_playoff_gamelog(pid, season), season,
        entity=f"player:{pid}", ttl_s=TTL_GAMELOG,
    )
    if not rows:
        try:
            con = store.connect()
            try:
                tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
                if "silver_playoff_gamelogs" in tables:
                    seasons = sorted(
                        r[0] for r in con.execute(
                            "SELECT DISTINCT _season FROM silver_playoff_gamelogs"
                        ).fetchall() if r[0]
                    )
                else:
                    seasons = []
            finally:
                con.close()
        except Exception:
            seasons = []
        if seasons:
            coverage = ", ".join(seasons)
            err = (f"No playoff games found for {player_id} in {season} "
                   f"(playoff coverage: {coverage}).")
        else:
            err = (f"No playoff games found for {player_id} in {season} "
                   f"and no playoff seasons are stored yet.")
        return {"tool": "get_playoff_intel", "ok": False, "error": err}
    cols = ["GAME_DATE", "MATCHUP", "PTS", "REB", "AST", "MIN"]
    slim = [{k: r.get(k) for k in cols if k in r} for r in rows]
    return {"tool": "get_playoff_intel", "ok": True, "rows": slim, "meta": meta}


@tool
def get_last_x(player_id: str | int, n: int = 10, season: str = SEASON) -> dict[str, Any]:
    """Last n games for one player id, most recent first."""
    player_id = coerce_player_id(player_id)
    rows, meta = _warehouse_or_live(
        "silver_player_gamelogs", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: nba_stats.player_gamelog(player_id, season), season,
        entity=f"player:{player_id}", ttl_s=TTL_GAMELOG,
    )
    if not rows:
        return {"tool": "get_last_x", "ok": False,
                "error": meta.get("error") or "empty upstream response"}
    import polars as _pl
    frame = _pl.DataFrame(rows)
    try:
        frame = frame.with_columns(
            _pl.col("GAME_DATE").str.strptime(_pl.Date, "%b %d, %Y").alias("_d")
        ).sort("_d", descending=True).drop("_d")
    except Exception:
        frame = frame.reverse()
    out = frame.head(min(max(n, 1), 25)).to_dicts()
    return {"tool": "get_last_x", "ok": True, "rows": out, "meta": meta}


@tool
def get_trend(player_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Decay-weighted recent form versus season baseline. DARKO-lite."""
    player_id = coerce_player_id(player_id)
    rows, meta = _warehouse_or_live(
        "silver_player_gamelogs", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: nba_stats.player_gamelog(player_id, season), season,
        entity=f"player:{player_id}", ttl_s=TTL_GAMELOG,
    )
    if not rows:
        return {"tool": "get_trend", "ok": False,
                "error": meta.get("error") or "empty upstream response"}
    try:
        pts = [float(r.get("PTS") or 0) for r in rows]
    except (TypeError, ValueError):
        return {"tool": "get_trend", "ok": False, "error": "bad points"}
    if len(pts) < 5:
        return {"tool": "get_trend", "ok": False, "error": "too few games"}
    decay = 0.94
    weights = [decay ** i for i in range(len(pts))]
    recent = pts[-20:]
    rw = weights[-len(recent):]
    form = sum(p * w for p, w in zip(recent, rw)) / sum(rw)
    base = sum(pts) / len(pts)
    return {"tool": "get_trend", "ok": True,
            "rows": {"games": len(pts),
                     "season_ppg": round(base, 1),
                     "form_ppg": round(form, 1),
                     "delta": round(form - base, 1),
                     "direction": "up" if form > base + 1 else (
                         "down" if form < base - 1 else "flat")},
            "meta": meta}


@tool
def get_percentiles(player_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Percentile ranks for one player id across PTS REB AST STL BLK."""
    player_id = coerce_player_id(player_id)
    cats = ["PTS", "REB", "AST", "STL", "BLK"]
    out: dict[str, Any] = {}
    for cat in cats:
        table = f"silver_leaders_{cat.lower()}"
        rows, _ = _warehouse_or_live(
            table, "_season = ?",
            [season], lambda c=cat: nba_stats.leaders(c, season), season,
            limit=600, ttl_s=TTL_LEADERS,
        )
        hit = next((r for r in rows if r.get("PLAYER_ID") == player_id), None)
        if hit and hit.get("RANK"):
            total = len(store.read_frame(table, "_season = ?", [season]))
            out[cat] = {
                "rank": hit["RANK"],
                "percentile": round(100 * (1 - (hit["RANK"] - 1) / max(total, 1)), 1),
            }
    return {"tool": "get_percentiles", "ok": True, "rows": out,
            "meta": {"source": "nba_api", "season": season}}


@tool
def get_comps(player_id: str | int, season: str = SEASON, k: int = 5) -> dict[str, Any]:
    """Nearest statistical neighbors by per-36 + advanced shape. Same-season only."""
    import math

    from ._core import clamp_season

    season = clamp_season(season)
    try:
        k = max(1, min(int(k or 5), 15))
    except (TypeError, ValueError):
        k = 5
    try:
        pid = coerce_player_id(player_id)
    except ValueError as exc:
        return {"tool": "get_comps", "ok": False, "error": str(exc)}

    try:
        leaders = _read_df(
            "SELECT * FROM silver_leaders_pts WHERE _season = ?", [season])
    except Exception:
        leaders = []
    try:
        adv = _read_df(
            "SELECT * FROM silver_advanced WHERE _season = ?", [season])
    except Exception:
        adv = []

    BOX = [("PTS", "PTS36"), ("REB", "REB36"), ("AST", "AST36"),
           ("STL", "STL36"), ("BLK", "BLK36"), ("FG3A", "FG3A36"),
           ("FTA", "FTA36"), ("TOV", "TOV36")]
    PCTS = ["FG3_PCT", "FT_PCT"]
    ADVS = ["USG_PCT", "TS_PCT", "AST_PCT", "TM_TOV_PCT", "PIE",
            "OFF_RATING", "DEF_RATING", "NET_RATING"]
    LABELS = {
        "PTS36": "scoring volume (PTS/36)",
        "REB36": "rebounding (REB/36)",
        "AST36": "playmaking (AST/36)",
        "STL36": "steals (STL/36)",
        "BLK36": "blocks (BLK/36)",
        "FG3A36": "three-point volume (3PA/36)",
        "FTA36": "foul drawing (FTA/36)",
        "TOV36": "turnovers (TOV/36)",
        "FG3_PCT": "three-point efficiency",
        "FT_PCT": "free-throw efficiency",
        "USG_PCT": "usage rate",
        "TS_PCT": "true shooting",
        "AST_PCT": "assist rate",
        "TM_TOV_PCT": "turnover rate",
        "PIE": "player impact estimate",
        "OFF_RATING": "offensive rating",
        "DEF_RATING": "defensive rating",
        "NET_RATING": "net rating",
    }

    def _archetype(feats: dict[str, Any]) -> str:
        def _f(key: str) -> float | None:
            try:
                v = feats.get(key)
                return None if v is None else float(v)
            except (TypeError, ValueError):
                return None

        usg = _f("USG_PCT")
        if usg is not None and usg <= 1:
            usg *= 100  # warehouse stores usage-class stats as ratios
        ap = _f("AST_PCT")
        if ap is not None and ap <= 1:
            ap *= 100
        ts = _f("TS_PCT")
        if ts is not None and ts > 1:
            ts /= 100
        ast36 = _f("AST36")
        reb36 = _f("REB36")
        blk36 = _f("BLK36")
        fg3a36 = _f("FG3A36")
        pts36 = _f("PTS36")
        if usg is not None and usg >= 30 and ast36 is not None and ast36 >= 7:
            return "high-usage creator"
        if usg is not None and usg >= 30:
            return "high-usage scorer"
        if ap is not None and ap >= 32:
            return "floor general"
        if ast36 is not None and ast36 >= 7.5:
            return "playmaker"
        if reb36 is not None and reb36 >= 11:
            if blk36 is not None and blk36 >= 1.8:
                return "rim protector"
            if ts is not None and ts >= 0.60:
                return "rim-running big"
            return "rebounding big"
        if fg3a36 is not None and fg3a36 >= 8:
            return "movement shooter"
        if usg is not None and usg >= 25:
            return "secondary creator"
        if pts36 is not None and pts36 >= 24:
            return "volume scorer"
        return "rotation player"

    notes = ("cross-era comps unavailable: "
             "warehouse holds player stat profiles for 2025-26 only")
    pool: list[dict[str, Any]] = []
    use_adv = bool(adv)
    if leaders:
        adv_by_id: dict[str, dict[str, Any]] = {}
        for row in adv:
            if isinstance(row, dict) and row.get("PLAYER_ID") is not None:
                adv_by_id[str(row.get("PLAYER_ID"))] = row
        for row in leaders:
            if not isinstance(row, dict):
                continue
            total_min = _num(row.get("MIN"))
            if total_min is None or total_min < 400:
                continue
            feats: dict[str, float | None] = {}
            for col, feat in BOX:
                v = _num(row.get(col))
                feats[feat] = 36 * v / total_min if v is not None else None
            for feat in PCTS:
                feats[feat] = _num(row.get(feat))
            arow = adv_by_id.get(str(row.get("PLAYER_ID")), {})
            for feat in ADVS:
                feats[feat] = _num(arow.get(feat)) if use_adv else None
            try:
                entry_pid = int(row.get("PLAYER_ID"))
            except (TypeError, ValueError):
                continue
            pool.append({"sid": str(row.get("PLAYER_ID")),
                         "pid": entry_pid,
                         "name": row.get("PLAYER"),
                         "team": row.get("TEAM"),
                         "feats": feats})
        if not use_adv:
            notes += "; advanced metrics unavailable, box-score features only"
    else:
        def _mins(v: object) -> float | None:
            m = _num(v)
            if m is not None:
                return m
            s = str(v or "").strip()  # gamelog MIN may be clock "MM:SS"
            if ":" in s:
                try:
                    mm, ss = s.split(":")[:2]
                    return float(mm) + float(ss) / 60
                except (TypeError, ValueError):
                    return None
            return None

        try:
            games = _read_df(
                "SELECT _entity, MIN, PTS, REB, AST, STL, BLK, TOV,"
                " FG3A, FTA, FG3_PCT, FT_PCT"
                " FROM silver_player_gamelogs WHERE _season = ?", [season])
        except Exception:
            games = []
        by_ent: dict[str, list[dict[str, Any]]] = {}
        for g in games:
            if isinstance(g, dict) and g.get("_entity"):
                by_ent.setdefault(str(g.get("_entity")), []).append(g)
        for ent, gs in by_ent.items():
            if len(gs) < 10:
                continue
            mins = [_mins(g.get("MIN")) for g in gs]
            mins = [m for m in mins if m is not None]
            if not mins or sum(mins) < 400:
                continue
            avg_min = sum(mins) / len(mins)
            feats = {}
            for col, feat in BOX:
                vals = [_num(g.get(col)) for g in gs]
                vals = [v for v in vals if v is not None]
                feats[feat] = 36 * (sum(vals) / len(vals)) / avg_min if vals else None
            for feat in PCTS:
                vals = [_num(g.get(feat)) for g in gs]
                vals = [v for v in vals if v is not None]
                feats[feat] = sum(vals) / len(vals) if vals else None
            for feat in ADVS:
                feats[feat] = None
            ent_pid = ent.split(":", 1)[-1] if ":" in ent else ent
            try:
                entry_pid = int(ent_pid)
            except (TypeError, ValueError):
                continue
            pool.append({"sid": str(entry_pid), "pid": entry_pid,
                         "name": None, "team": None, "feats": feats})
        notes += "; leaders missing, estimated from gamelogs"
    if not pool:
        return {"tool": "get_comps", "ok": False,
                "error": f"no player stat profiles for season {season}"}

    target = next((e for e in pool if e["sid"] == str(pid)), None)
    if target is None:
        try:
            from nba_api.stats.static import players as _players
            tname = next((p.get("full_name", str(player_id))
                          for p in _players.get_players()
                          if str(p.get("id")) == str(pid)), str(player_id))
        except Exception:
            tname = str(player_id)
        return {"tool": "get_comps", "ok": False,
                "error": f"no stat profile for {tname} in {season}"}

    features = [f for _, f in BOX] + PCTS + (ADVS if use_adv else [])
    stats: dict[str, tuple[float, float]] = {}
    dropped: list[str] = []
    for feat in features:
        vals = [e["feats"][feat] for e in pool
                if isinstance(e["feats"].get(feat), (int, float))]
        if len(vals) < 2:
            dropped.append(feat)
            continue
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        if var <= 0:
            dropped.append(feat)
            continue
        stats[feat] = (mean, math.sqrt(var))
    kept = [f for f in features if f in stats]
    if not kept:
        return {"tool": "get_comps", "ok": False,
                "error": f"no comparable features for season {season}"}

    zvec: dict[str, dict[str, float]] = {}
    for e in pool:
        z: dict[str, float] = {}
        for feat in kept:
            mean, std = stats[feat]
            v = e["feats"].get(feat)
            z[feat] = ((v - mean) / std if isinstance(v, (int, float))
                       else 0.0)  # mean-imputed when missing
        zvec[e["sid"]] = z
    zt = zvec[target["sid"]]
    scored: list[tuple[float, dict[str, Any]]] = []
    for e in pool:
        if e["sid"] == target["sid"]:
            continue
        ze = zvec[e["sid"]]
        dist = math.sqrt(sum((zt[f] - ze[f]) ** 2 for f in kept))
        scored.append((dist, e))
    scored.sort(key=lambda t: t[0])

    pct_round = {f for f in kept if f.endswith("_PCT")}
    target_arch = _archetype(target["feats"])
    rows: list[dict[str, Any]] = []
    for dist, e in scored[:k]:
        ze = zvec[e["sid"]]
        order = sorted(kept, key=lambda f: abs(zt[f] - ze[f]))[:3]
        drivers = []
        for feat in order:
            tv, cv = target["feats"].get(feat), e["feats"].get(feat)
            nd = 3 if feat in pct_round else 1
            try:
                t_round = round(float(tv), nd) if tv is not None else None
            except (TypeError, ValueError):
                t_round = None
            try:
                c_round = round(float(cv), nd) if cv is not None else None
            except (TypeError, ValueError):
                c_round = None
            drivers.append({"stat": LABELS[feat],
                            "target": t_round, "comp": c_round})
        arch = _archetype(e["feats"])
        rows.append({"PLAYER": e["name"], "PLAYER_ID": e["pid"],
                     "TEAM": e["team"], "season": season, "era": season,
                     "similarity": round(100 / (1 + dist / 20), 1),
                     "archetype": arch,
                     "shared_archetype": arch == target_arch,
                     "drivers": drivers})
    return {"tool": "get_comps", "ok": True,
            "player": {"name": target["name"], "id": pid,
                       "season": season, "archetype": target_arch},
            "rows": rows,
            "meta": {"source": "warehouse", "season": season,
                     "features": kept, "candidates": len(pool),
                     "dropped_features": dropped,
                     "similarity": "100/(1+d/20); d = standardized "
                                   "Euclidean distance over kept features",
                     "notes": notes}}


ADVANCED_COLS = ["PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN",
                 "USG_PCT", "TS_PCT", "EFG_PCT", "AST_PCT", "TM_TOV_PCT",
                 "PIE", "OFF_RATING", "DEF_RATING", "NET_RATING",
                 "USG_PCT_RANK", "TS_PCT_RANK", "PIE_RANK", "NET_RATING_RANK"]


@tool
def get_advanced(player: str | int, season: str = SEASON) -> dict[str, Any]:
    """Advanced box metrics for one player: usage, efficiency, PIE, ratings."""
    player_id = coerce_player_id(player)
    rows: list[dict[str, Any]] = []
    try:
        rows = _read_df(
            "SELECT * FROM silver_advanced"
            " WHERE _season = ? AND CAST(PLAYER_ID AS VARCHAR)"
            " = CAST(? AS VARCHAR)",
            [season, str(player_id)],
        )
    except Exception:
        rows = []
    if not rows:
        res = nba_stats.player_advanced(season)
        if res.ok and res.frame.height:
            try:
                store.save_frame("silver_advanced", res, "player-advanced")
            except Exception:
                pass
            rows = [r for r in res.frame.to_dicts()
                    if str(r.get("PLAYER_ID")) == str(player_id)][:1]
    else:
        rows = rows[:1]
    if not rows:
        return {"tool": "get_advanced", "ok": False,
                "error": f"no advanced row for player {player_id}"}
    slim = {k: rows[0].get(k) for k in ADVANCED_COLS if k in rows[0]}
    return {"tool": "get_advanced", "ok": True, "rows": slim,
            "meta": {"source": "nba_api", "season": season}}


@tool
def get_shot_zones(player_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Zone splits for one player id: rim, midrange, three with shares."""
    player_id = coerce_player_id(player_id)
    import math

    res = nba_stats.shot_chart(player_id, season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_shot_zones", "ok": False,
                "error": res.error or "empty upstream response"}

    def _zone_of(r: dict) -> str:
        zb = str(r.get("SHOT_ZONE_BASIC") or "").strip()
        if zb:
            return zb
        try:
            dist = math.hypot(float(r.get("LOC_X", 0)), float(r.get("LOC_Y", 0))) / 10
        except (TypeError, ValueError):
            return "Mid-Range"
        return ("Restricted Area" if dist < 8
                else ("Above the Break 3" if dist > 23.75 else "Mid-Range"))

    def _is_made(r: dict) -> bool:
        return str(r.get("SHOT_MADE_FLAG", "") or "") == "1" or str(
            r.get("EVENT_TYPE", "")).lower().startswith("made")

    def _is_three(r: dict) -> bool:
        return "3pt" in str(r.get("SHOT_TYPE", "") or "").lower()

    zones: dict[str, list] = {}
    for r in res.frame.to_dicts():
        z = _zone_of(r)
        made = _is_made(r)
        three = _is_three(r)
        slot = zones.setdefault(z, [0, 0, 0])
        slot[1] += 1
        if made:
            slot[0] += 1
            if three:
                slot[2] += 1
    total = sum(a for _, a, _ in zones.values()) or 1
    league_efg: dict[str, float] = {}
    baseline_missing = True
    baseline_detail = ""
    try:
        w = store.read_frame("silver_shots", "_season = ?", [season])
        if (w.height > 0 and "PLAYER_ID" in w.columns
                and "SHOT_ZONE_BASIC" in w.columns
                and "SHOT_MADE_FLAG" in w.columns):
            n_players = w.select("PLAYER_ID").n_unique()
            if n_players >= 10:
                agg: dict[str, list] = {}
                for r in w.to_dicts():
                    zb = str(r.get("SHOT_ZONE_BASIC") or "").strip() or "Mid-Range"
                    s = agg.setdefault(zb, [0, 0, 0])
                    s[1] += 1
                    if _is_made(r):
                        s[0] += 1
                        if _is_three(r):
                            s[2] += 1
                for zb, (m, a, t) in agg.items():
                    if a:
                        league_efg[zb] = round((m + 0.5 * t) / a, 3)
                baseline_missing = False
            else:
                baseline_detail = f"silver_shots has {n_players} player(s), need 10+"
        else:
            baseline_detail = "silver_shots empty or missing zone/made columns"
    except Exception as exc:
        baseline_detail = str(exc)[:120]
    rows = []
    for z, (m, a, t) in sorted(zones.items()):
        fgp = round(m / a, 3) if a else 0.0
        efg = round((m + 0.5 * t) / a, 3) if a else 0.0
        shr = round(a / total, 3)
        row: dict[str, Any] = {"zone": z, "FGM": m, "FGA": a,
                               "FG_PCT": fgp, "share": shr,
                               "eFG_PCT": efg, "SHARE": shr,
                               "fgm": m, "fga": a, "fg_pct": fgp,
                               "freq_pct": shr}
        if not baseline_missing and z in league_efg:
            row["LEAGUE_DELTA"] = round(efg - league_efg[z], 3)
        rows.append(row)
    meta: dict[str, Any] = {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                            "rows": len(rows), "cached": False}
    if baseline_missing:
        meta["baseline_missing"] = True
        if baseline_detail:
            meta["baseline_detail"] = baseline_detail
    else:
        meta["baseline"] = "silver_shots league zone eFG"
    return {"tool": "get_shot_zones", "ok": True, "rows": rows, "meta": meta}


@tool
def get_splits(player_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Home/away plus monthly, wins/losses, last-10, starter splits from the game log."""
    player_id = coerce_player_id(player_id)
    res = nba_stats.player_gamelog(player_id, season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_splits", "ok": False,
                "error": res.error or "empty upstream response"}
    try:
        g = res.frame.with_columns(
            pl.col("MATCHUP").str.contains("@").alias("away")
        )
        cols = g.columns
        if "GAME_DATE" in cols:
            try:
                g = g.with_columns(
                    pl.col("GAME_DATE").str.strptime(
                        pl.Date, "%b %d, %Y", strict=False).alias("_d")
                )
            except Exception:
                pass

        def _row(label: str, f: pl.DataFrame) -> dict[str, Any] | None:
            gp = f.height
            if gp == 0:
                return None
            ppg = round(float(f["PTS"].mean() or 0), 1) if "PTS" in f.columns else 0.0
            row: dict[str, Any] = {"split": label, "GP": gp, "PPG": ppg}
            if "FG_PCT" in f.columns:
                try:
                    row["FG_PCT"] = round(float(f["FG_PCT"].mean() or 0), 3)
                except Exception:
                    pass
            return row

        rows: list[dict[str, Any]] = []
        home = g.filter(~pl.col("away")).select("PTS", "FG_PCT")
        away = g.filter(pl.col("away")).select("PTS", "FG_PCT")
        for r in (_row("home", home), _row("away", away)):
            if r:
                rows.append(r)
        if "WL" in g.columns:
            wins = g.filter(pl.col("WL") == "W").select("PTS", "FG_PCT")
            losses = g.filter(pl.col("WL") == "L").select("PTS", "FG_PCT")
            for r in (_row("wins", wins), _row("losses", losses)):
                if r:
                    rows.append(r)
        ordered: pl.DataFrame | None = None
        if "_d" in g.columns:
            try:
                if g["_d"].drop_nulls().len() > 0:
                    ordered = g.sort("_d", descending=True)
            except Exception:
                ordered = None
        last10 = ordered.head(10) if ordered is not None else g.head(10)
        r = _row("last10", last10.select("PTS", "FG_PCT"))
        if r:
            rows.append(r)
        if "START_POSITION" in g.columns:
            try:
                started = g.filter(
                    pl.col("START_POSITION").is_not_null()
                    & (pl.col("START_POSITION").cast(pl.String) != "")
                )
                benched = g.filter(
                    pl.col("START_POSITION").is_null()
                    | (pl.col("START_POSITION").cast(pl.String) == "")
                )
                for label, f in (("starter", started), ("bench", benched)):
                    rr = _row(label, f.select("PTS", "FG_PCT"))
                    if rr:
                        rows.append(rr)
            except Exception:
                pass
        elif "GS" in g.columns:
            try:
                gs = pl.col("GS").cast(pl.String)
                started = g.filter(gs.is_in(["1", "1.0", "*", "S", "True", "true"]))
                benched = g.filter(~gs.is_in(["1", "1.0", "*", "S", "True", "true"]))
                for label, f in (("starter", started), ("bench", benched)):
                    rr = _row(label, f.select("PTS", "FG_PCT"))
                    if rr:
                        rows.append(rr)
            except Exception:
                pass
        if "GAME_DATE" in g.columns:
            try:
                gm = g.with_columns(
                    pl.col("GAME_DATE").cast(pl.String).str.slice(0, 3).alias("_mon")
                )
                if "_d" in gm.columns:
                    try:
                        order = (gm.filter(pl.col("_d").is_not_null())
                                   .group_by("_mon").agg(pl.col("_d").min().alias("_d0")))
                    except Exception:
                        order = None
                else:
                    order = None
                agg = gm.group_by("_mon").agg(
                    pl.len().alias("GP"),
                    pl.col("PTS").mean().alias("_ppg"),
                    pl.col("FG_PCT").mean().alias("_fg")
                    if "FG_PCT" in gm.columns else pl.len().alias("_fg"),
                )
                if order is not None:
                    try:
                        agg = agg.join(order, on="_mon", how="left").sort("_d0").drop("_d0")
                    except Exception:
                        agg = agg.sort("_mon")
                else:
                    agg = agg.sort("_mon")
                for d in agg.to_dicts():
                    try:
                        gp = int(d.get("GP") or 0)
                        if gp == 0:
                            continue
                        mrow: dict[str, Any] = {
                            "split": str(d.get("_mon")),
                            "GP": gp,
                            "PPG": round(float(d.get("_ppg") or 0), 1),
                        }
                        if "FG_PCT" in gm.columns:
                            mrow["FG_PCT"] = round(float(d.get("_fg") or 0), 3)
                        rows.append(mrow)
                    except (TypeError, ValueError):
                        continue
            except Exception:
                pass
        rows = rows[:12]
    except Exception as exc:
        return {"tool": "get_splits", "ok": False, "error": str(exc)[:160]}
    return {"tool": "get_splits", "ok": True, "rows": rows,
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": len(rows), "cached": False}}


@tool
def get_on_off(player_id: str | int, team_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """On and off splits for one player on one team. Possession level."""
    player_id = coerce_player_id(player_id)
    team_id = coerce_team_id(team_id)
    from ..sources import pbpstats

    rows, meta = _warehouse_or_live(
        "silver_on_off", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pbpstats.on_off(player_id, team_id, season), season,
        entity=f"player:{player_id}", ttl_s=TTL_PBPSTATS,
    )
    return {"tool": "get_on_off", "ok": True, "rows": rows, "meta": meta}


@tool
def get_wowy(
    player_a: str = "",
    player_b: str = "",
    player_ids: str = "",
    team_id: str | int = 0,
    season: str = SEASON,
) -> dict[str, Any]:
    """With-or-without-you (WOWY) 4-way lineup combination splits for two players.

    Accepts player_a and player_b by name or id, or comma-separated player_ids.
    Computes Both ON, A ON / B OFF, B ON / A OFF, and Both OFF with minutes,
    offensive rating, defensive rating, and net rating from warehouse lineups.
    """
    raw_a = (player_a or "").strip()
    raw_b = (player_b or "").strip()
    if not raw_a and not raw_b and player_ids:
        parts = [p.strip() for p in player_ids.split(",") if p.strip()]
        if len(parts) >= 2:
            raw_a, raw_b = parts[0], parts[1]
        elif len(parts) == 1:
            raw_a = parts[0]

    pid_a = coerce_player_id(raw_a) if raw_a else 0
    pid_b = coerce_player_id(raw_b) if raw_b else 0

    if pid_a and pid_b:
        con = store.connect(read_only=True)
        try:
            tid = coerce_team_id(team_id) if team_id else None
            if not tid:
                shared = con.execute(
                    """
                    SELECT TEAM_ID, TEAM_ABBREVIATION, COUNT(*) FROM silver_lineups
                    WHERE _season = ?
                      AND GROUP_ID LIKE '%-' || ? || '-%'
                      AND GROUP_ID LIKE '%-' || ? || '-%'
                    GROUP BY TEAM_ID, TEAM_ABBREVIATION
                    ORDER BY COUNT(*) DESC LIMIT 1
                    """,
                    [season, str(pid_a), str(pid_b)],
                ).fetchone()
                if not shared:
                    return {"tool": "get_wowy", "ok": False,
                            "error": f"{raw_a} and {raw_b} never shared "
                                     f"the court in {season}. WOWY needs teammates."}
                tid, tabbr = shared[0], shared[1]
            else:
                tabbr = str(tid)
                both = con.execute(
                    """
                    SELECT COUNT(*) FROM silver_lineups
                    WHERE _season = ? AND TEAM_ID = ?
                      AND GROUP_ID LIKE '%-' || ? || '-%'
                      AND GROUP_ID LIKE '%-' || ? || '-%'
                    """,
                    [season, tid, str(pid_a), str(pid_b)],
                ).fetchone()
                if not both or not both[0]:
                    return {"tool": "get_wowy", "ok": False,
                            "error": f"{raw_a} and {raw_b} never shared "
                                     f"the court for team {tabbr} in {season}."}

            if tid:
                df = con.execute(
                    """
                    SELECT 
                      CASE 
                        WHEN GROUP_ID LIKE '%-' || ? || '-%' AND GROUP_ID LIKE '%-' || ? || '-%' THEN 'Both ON'
                        WHEN GROUP_ID LIKE '%-' || ? || '-%' AND GROUP_ID NOT LIKE '%-' || ? || '-%' THEN ? || ' ON, ' || ? || ' OFF'
                        WHEN GROUP_ID NOT LIKE '%-' || ? || '-%' AND GROUP_ID LIKE '%-' || ? || '-%' THEN ? || ' ON, ' || ? || ' OFF'
                        ELSE 'Both OFF'
                      END AS split,
                      ROUND(SUM(MIN), 1) AS minutes,
                      ROUND(SUM(FGA - OREB + TOV + 0.44 * FTA), 0) AS possessions,
                      ROUND(100.0 * SUM(PTS) / NULLIF(SUM(FGA - OREB + TOV + 0.44 * FTA), 0), 2) AS off_rating,
                      ROUND(100.0 * SUM(PTS - PLUS_MINUS) / NULLIF(SUM(FGA - OREB + TOV + 0.44 * FTA), 0), 2) AS def_rating,
                      ROUND(100.0 * SUM(PLUS_MINUS) / NULLIF(SUM(FGA - OREB + TOV + 0.44 * FTA), 0), 2) AS net_rating
                    FROM silver_lineups
                    WHERE TEAM_ID = ? AND _season = ?
                    GROUP BY split
                    ORDER BY minutes DESC
                    """,
                    [str(pid_a), str(pid_b), str(pid_a), str(pid_b), raw_a, raw_b, str(pid_a), str(pid_b), raw_b, raw_a, tid, season],
                ).fetchdf()

                if len(df) > 0:
                    rows = df.to_dict(orient="records")
                    both_on = next((r for r in rows if r["split"] == "Both ON"), None)
                    net_str = f"{both_on['net_rating']:+.1f}" if both_on and both_on.get("net_rating") is not None else "N/A"
                    min_val = both_on['minutes'] if both_on else 0
                    verdict = f"{tabbr}: Both on court net rating {net_str} across {min_val} minutes."
                    return {
                        "tool": "get_wowy",
                        "ok": True,
                        "team": tabbr,
                        "player_a": raw_a,
                        "player_b": raw_b,
                        "rows": rows,
                        "verdict": verdict,
                        "meta": {"source": "silver_lineups", "season": season, "team": tabbr},
                    }
        except Exception:
            pass
        finally:
            con.close()

    # Fallback to PBPStats API if warehouse lacks the lineup rows
    from ..sources import pbpstats

    ids = [p for p in (pid_a, pid_b) if p]
    resolved_team = coerce_team_id(team_id) if team_id else 0
    entity_key = f"wowy:{raw_a}_{raw_b}"
    rows, meta = _warehouse_or_live(
        "silver_wowy", "_season = ? AND _entity = ?",
        [season, entity_key],
        lambda: pbpstats.wowy(ids, resolved_team, season), season,
        entity=entity_key, ttl_s=TTL_PBPSTATS,
    )
    return {"tool": "get_wowy", "ok": True, "rows": rows, "meta": meta}


@tool
def get_four_factors(player_id: str | int, team_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Four factor on-off splits for one player on one team."""
    player_id = coerce_player_id(player_id)
    team_id = coerce_team_id(team_id)
    from ..sources import pbpstats

    rows, meta = _warehouse_or_live(
        "silver_four_factors", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pbpstats.four_factors(player_id, team_id, season), season,
        entity=f"player:{player_id}", ttl_s=TTL_PBPSTATS,
    )
    return {"tool": "get_four_factors", "ok": True, "rows": rows, "meta": meta}


@tool
async def get_shot_compare(a: str, b: str, season: str = SEASON) -> dict[str, Any]:
    """Shot-diet showdown: zone eFG and share for two players."""
    async def _zones(who: str) -> dict[str, dict]:
        try:
            pid = coerce_player_id(who)
            res = await get_shot_zones.ainvoke({"player_id": pid, "season": season})
            return {r.get("zone", "?"): r for r in res.get("rows", [])}
        except Exception:
            return {}
    ma, mb = await _asyncio.gather(_zones(a), _zones(b))
    rows: list[dict[str, Any]] = []
    for z in sorted(set(ma) | set(mb)):
        ra, rb = ma.get(z, {}), mb.get(z, {})
        ae = float(ra.get("eFG_PCT", 0) or 0)
        be = float(rb.get("eFG_PCT", 0) or 0)
        ash = float(ra.get("SHARE", ra.get("share", 0)) or 0)
        bsh = float(rb.get("SHARE", rb.get("share", 0)) or 0)
        edge = "wash" if max(ash, bsh) < 0.05 or ae == be else (a if ae > be else b)
        rows.append({"zone": z, "a_eFG": ae, "b_eFG": be,
                     "a_share": ash, "b_share": bsh, "edge": edge})
    rim = next((r for r in rows if r["zone"] == "Restricted Area"), None)
    rim_owner = "wash" if not rim or max(rim["a_share"], rim["b_share"]) < 0.05 or rim["a_eFG"] == rim["b_eFG"] else (a if rim["a_eFG"] > rim["b_eFG"] else b)
    threes = [r for r in rows if "3" in r["zone"] or "corner" in r["zone"].lower() or "break" in r["zone"].lower()]
    arc = max(threes, key=lambda r: max(r["a_share"], r["b_share"]), default=None)
    arc_owner = "wash" if not arc or arc["a_eFG"] == arc["b_eFG"] else (a if arc["a_eFG"] > arc["b_eFG"] else b)
    arc_zone = arc["zone"] if arc else "no threes"
    verdict = f"{rim_owner} owns the rim; {arc_owner} owns the arc ({arc_zone})."
    return {"tool": "get_shot_compare", "ok": True, "rows": rows,
            "verdict": verdict, "meta": {"source": "nba_api", "season": season,
            "a": a, "b": b, "arc_zone": arc_zone, "arc_edge": arc_owner}}


@tool
def get_raptor_history(player: str, season: str = "") -> dict[str, Any]:
    """Season-by-season RAPTOR and WAR for one player name. Warehouse only."""
    name = (player or "").strip()
    if not name:
        return {"tool": "get_raptor_history", "ok": False, "error": "empty player name"}
    con = store.connect()
    try:
        q = ("SELECT * FROM silver_raptor_player WHERE LOWER(PLAYER_NAME) = LOWER(?)"
             + (" AND _season = ?" if season else "") + " ORDER BY _season ASC LIMIT 25")
        try:
            frame = pl.from_arrow(con.execute(
                q, [name] + ([season] if season else [])).fetch_arrow_table())
        except Exception as exc:
            return {"tool": "get_raptor_history", "ok": False,
                    "error": f"raptor warehouse not seeded: {str(exc)[:120]}"}
        try:
            teams = {r[1]: r[0] for r in con.execute(
                """SELECT TEAM, _season FROM silver_raptor_team
                WHERE LOWER(PLAYER_NAME) = LOWER(?) AND SEASON_TYPE = 'RS'""",
                [name]).fetchall()}
        except Exception:
            teams = {}
    finally:
        con.close()
    if frame.height == 0:
        return {"tool": "get_raptor_history", "ok": False,
                "error": f"no RAPTOR history for '{name}'"
                + (f" in {season}" if season else "")}
    rows = [{"SEASON": r.get("_season"), "TEAM": teams.get(r.get("_season")),
             "MP": r.get("MP"), "RAPTOR_O": r.get("RAPTOR_OFFENSE"),
             "RAPTOR_D": r.get("RAPTOR_DEFENSE"), "RAPTOR": r.get("RAPTOR_TOTAL"),
             "WAR": r.get("WAR_TOTAL")} for r in frame.to_dicts()]
    return {"tool": "get_raptor_history", "ok": True, "rows": rows,
            "meta": {"source": "fivethirtyeight:raptor", "seasons": len(rows)}}


DPOY_MINUTES = 500
UNSUNG_MIN_MINUTES = 200
UNSUNG_MAX_MINUTES = 1000


@tool
def get_hustle_boards(season: str = SEASON, top: int = 10) -> dict[str, Any]:
    """Hustle leaderboards from warehouse only: DPOY composite, screen-assist
    kings, and unsung defenders with elite per-minute hustle in small roles."""
    try:
        top = max(1, min(int(top or 10), 25))
    except (TypeError, ValueError):
        top = 10
    try:
        dpoy = _read_df(
            """SELECT PLAYER_NAME, TEAM_ABBREVIATION, G, MIN,
            DEFLECTIONS, CHARGES_DRAWN, CONTESTED_SHOTS,
            (DEFLECTIONS + CHARGES_DRAWN + CONTESTED_SHOTS) AS HUSTLE,
            ROUND((DEFLECTIONS + CHARGES_DRAWN + CONTESTED_SHOTS)
                / NULLIF(MIN, 0), 4) AS HUSTLE_PER_MIN
            FROM silver_hustle_player
            WHERE _season = ? AND MIN >= ?
            ORDER BY HUSTLE_PER_MIN DESC LIMIT ?""",
            [season, DPOY_MINUTES, top],
        )
        kings = _read_df(
            "SELECT PLAYER_NAME, TEAM_ABBREVIATION, G, MIN,"
            " SCREEN_ASSISTS, SCREEN_AST_PTS,"
            " ROUND(SCREEN_ASSISTS * 1.0 / NULLIF(G, 0), 2) AS screen_ast_per_game"
            " FROM silver_hustle_player WHERE _season = ?"
            " ORDER BY SCREEN_ASSISTS DESC LIMIT ?",
            [season, top],
        )
        unsung = _read_df(
            "SELECT h.PLAYER_NAME, h.TEAM_ABBREVIATION, h.G, h.MIN,"
            " h.DEFLECTIONS, h.CHARGES_DRAWN, h.CONTESTED_SHOTS,"
            " h.BOX_OUTS, h.LOOSE_BALLS_RECOVERED,"
            " ROUND((h.DEFLECTIONS + h.CHARGES_DRAWN + h.CONTESTED_SHOTS)"
            " * 36.0 / NULLIF(h.MIN, 0), 2) AS hustle_per36,"
            " ROUND(l.PTS * 1.0 / NULLIF(l.GP, 0), 1) AS ppg"
            " FROM silver_hustle_player h"
            " LEFT JOIN silver_leaders_pts l"
            " ON CAST(l.PLAYER_ID AS VARCHAR) = CAST(h.PLAYER_ID AS VARCHAR)"
            " AND l._season = h._season"
            " WHERE h._season = ? AND h.MIN >= ? AND h.MIN < ? AND h.G >= 20"
            " ORDER BY hustle_per36 DESC LIMIT ?",
            [season, UNSUNG_MIN_MINUTES, UNSUNG_MAX_MINUTES, top],
        )
    except Exception as exc:
        return {"tool": "get_hustle_boards", "ok": False,
                "error": f"hustle warehouse not seeded: {str(exc)[:120]}"}
    if not dpoy:
        return {"tool": "get_hustle_boards", "ok": False,
                "error": f"no hustle rows for {season}"}
    return {"tool": "get_hustle_boards", "ok": True,
            "rows": {"dpoy": dpoy, "screen_assist_kings": kings,
                     "unsung_defenders": unsung},
            "meta": {"source": "nba_api", "season": season, "top": top,
                     "dpoy_formula": "(deflections + charges drawn"
                     " + contested shots) per minute, 500+ minutes",
                     "unsung_rule": "MIN 200-1000 with G >= 20,"
                     " ranked by hustle per 36, ppg joined for usage context"}}


@tool
def get_debate_card(a: str, b: str, season: str = SEASON,
                    topic: str = "") -> dict[str, Any]:
    """Generate a shareable HTML debate card comparing two players.

    Returns a self-contained HTML file with side-by-side stats,
    styled for sharing. Saves to workspace and returns the path.
    Optional topic labels the debate (e.g. "MVP race").
    """
    import html as _html
    from pathlib import Path as _Path

    # Get comparison data — safe whether or not we're inside a running loop.
    import asyncio as _asyncio
    import concurrent.futures as _cf

    def _run(coro):
        try:
            _asyncio.get_running_loop()
        except RuntimeError:
            return _asyncio.run(coro)
        # Already inside a loop: run the coroutine in a fresh loop on a
        # worker thread to avoid "event loop is already running".
        with _cf.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(_asyncio.run, coro).result()

    comp = _run(get_compare.ainvoke({"a": a, "b": b, "season": season}))
    if not comp.get("ok"):
        return {"tool": "get_debate_card", "ok": False,
                "error": comp.get("error", "comparison failed")}

    rows = comp.get("rows", {})
    # Extract player data
    players = []
    for key in ["a", "b"]:
        p = rows.get(key, {})
        if isinstance(p, dict):
            players.append(p)

    if len(players) < 2:
        return {"tool": "get_debate_card", "ok": False,
                "error": "could not load both players"}

    def _stat(p: dict, *keys: str) -> str:
        for k in keys:
            v = p.get(k)
            if v is not None:
                return str(v)
        return "—"

    # Build HTML card
    def _row(label: str, va: str, vb: str) -> str:
        return (
            f'<div class="row"><span class="stat-a">{_html.escape(va)}</span>'
            f'<span class="label">{_html.escape(label)}</span>'
            f'<span class="stat-b">{_html.escape(vb)}</span></div>'
        )

    stats_html = ""
    for label, keys in [
        ("PPG", ("ppg", "PTS")),
        ("RPG", ("rpg", "REB")),
        ("APG", ("apg", "AST")),
        ("FG%", ("fg_pct", "FG_PCT")),
        ("3P%", ("fg3_pct", "FG3_PCT")),
        ("Games", ("gp", "G", "GP")),
    ]:
        stats_html += _row(label, _stat(players[0], *keys), _stat(players[1], *keys))

    name_a = _html.escape(_stat(players[0], "name", "PLAYER", "player"))
    name_b = _html.escape(_stat(players[1], "name", "PLAYER", "player"))
    topic_html = ""
    if str(topic or "").strip():
        topic_html = (
            "<div class=\"topic\">" + _html.escape(str(topic).strip())
            + "</div>")

    html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name_a} vs {name_b} — Dime Debate Card</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; background: #f5f5f4;
  display: flex; justify-content: center; padding: 24px; margin: 0; }}
.card {{ background: #fff; border-radius: 16px; padding: 32px; max-width: 520px;
  width: 100%; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
.header {{ text-align: center; margin-bottom: 24px; }}
.topic {{ display: inline-block; font-size: 12px; font-weight: 600;
  color: #0891b2; border: 1px solid #0891b2; border-radius: 999px;
  padding: 3px 12px; margin-bottom: 10px; letter-spacing: 1px; }}
.vs {{ font-size: 13px; color: #78716c; letter-spacing: 2px; margin: 8px 0; }}
h1 {{ font-size: 22px; margin: 0; color: #1c1917; }}
.season {{ font-size: 13px; color: #a8a29e; margin-top: 4px; }}
.row {{ display: flex; align-items: center; padding: 10px 0;
  border-bottom: 1px solid #f5f5f4; }}
.row:last-child {{ border-bottom: none; }}
.stat-a, .stat-b {{ flex: 1; font-size: 17px; font-weight: 600; color: #1c1917; }}
.stat-a {{ text-align: left; }}
.stat-b {{ text-align: right; }}
.label {{ flex: 1; text-align: center; font-size: 12px; color: #a8a29e;
  letter-spacing: 1px; }}
.footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #d6d3d1; }}
.accent {{ color: #0891b2; }}
</style></head><body>
<div class="card">
<div class="header">
{topic_html}
<h1>{name_a} <span class="accent">vs</span> {name_b}</h1>
<div class="season">{_html.escape(season)} season · via Dime</div>
</div>
{stats_html}
<div class="footer">Settle the debate with data</div>
</div></body></html>"""

    # Save to workspace
    out_dir = _Path.home() / "workspace" / "dime" / "backend" / "data" / "cards"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_a = "".join(c for c in name_a if c.isalnum())[:20]
    safe_b = "".join(c for c in name_b if c.isalnum())[:20]
    fname = f"debate_{safe_a}_vs_{safe_b}_{season.replace('-', '')}.html"
    out_path = out_dir / fname
    out_path.write_text(html_doc, encoding="utf-8")

    return {"tool": "get_debate_card", "ok": True,
            "rows": {"path": str(out_path), "players": [name_a, name_b]},
            "meta": {"season": season, "format": "html"}}
