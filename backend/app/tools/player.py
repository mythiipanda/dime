"""Player desk. Intel, form, comps, zones, splits, possession splits."""

from typing import Any
import asyncio as _asyncio
import polars as pl
from langchain_core.tools import tool

from .. import store
from ..sources import nba_stats
from ._core import SEASON, _warehouse_or_live, coerce_player_id, coerce_team_id


@tool
async def get_compare(
    a: str, b: str, season: str = SEASON,
) -> dict[str, Any]:
    """Side-by-side compare of two players. Names or ids. One call."""
    async def one(who: str) -> dict[str, Any]:
        pid = coerce_player_id(who)
        intel = await get_player_intel.ainvoke(
            {"player_id": pid, "season": season})
        games = intel.get("rows", [])
        team = 0
        try:
            from nba_api.stats.endpoints import CommonPlayerInfo

            info = CommonPlayerInfo(player_id=pid, timeout=10).get_data_frames()[0]
            team = int(info["TEAM_ID"].iloc[0])
        except Exception:
            team = 0
        oo = {"rows": []}
        if team:
            oo = await get_on_off.ainvoke(
                {"player_id": pid, "team_id": team, "season": season})
        last = await get_last_x.ainvoke(
            {"player_id": pid, "n": 5, "season": season})
        pts = [g.get("PTS", 0) for g in intel.get("rows", [])[:10]]
        fgm = sum(g.get("FGM", 0) or 0 for g in games)
        fga = sum(g.get("FGA", 0) or 0 for g in games)
        fg3m = sum(g.get("FG3M", 0) or 0 for g in games)
        fta = sum(g.get("FTA", 0) or 0 for g in games)
        pts_total = sum(g.get("PTS", 0) or 0 for g in games)
        ts = round(pts_total / max(2 * (fga + 0.44 * fta), 1), 3)
        efg = round((fgm + 0.5 * fg3m) / max(fga, 1), 3)
        return {
            "name": who,
            "player_id": pid,
            "gp": len(games),
            "ppg": round(sum(pts) / max(len(pts), 1), 1),
            "ts_pct": ts,
            "efg_pct": efg,
            "on_off": (oo.get("rows", []) or [{}])[0],
            "last5": [g.get("PTS", 0) for g in last.get("rows", [])],
        }

    left, right = await _asyncio.gather(one(a), one(b))
    return {"tool": "get_compare", "ok": True,
            "rows": {"a": left, "b": right},
            "meta": {"source": "nba_api+pbpstats", "season": season}}


@tool
def get_player_intel(player_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Game log plus shot sample for one player id. Warehouse first."""
    player_id = coerce_player_id(player_id)
    rows, meta = _warehouse_or_live(
        "silver_player_gamelogs", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: nba_stats.player_gamelog(player_id, season), season,
        entity=f"player:{player_id}", live_first=True,
    )
    return {"tool": "get_player_intel", "ok": True, "rows": rows, "meta": meta}


@tool
def get_last_x(player_id: str | int, n: int = 10, season: str = SEASON) -> dict[str, Any]:
    """Last n games for one player id, most recent first."""
    player_id = coerce_player_id(player_id)
    res = nba_stats.player_gamelog(player_id, season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_last_x", "ok": False,
                "error": res.error or "empty upstream response"}
    frame = res.frame
    try:
        frame = frame.with_columns(
            pl.col("GAME_DATE").str.strptime(pl.Date, "%b %d, %Y").alias("_d")
        ).sort("_d", descending=True).drop("_d")
    except Exception:
        frame = frame.reverse()
    rows = frame.head(min(max(n, 1), 25)).to_dicts()
    store.save_frame("silver_player_gamelogs", res, f"player:{player_id}")
    return {"tool": "get_last_x", "ok": True, "rows": rows,
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": len(rows), "cached": False}}


@tool
def get_trend(player_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Decay-weighted recent form versus season baseline. DARKO-lite."""
    import math

    player_id = coerce_player_id(player_id)
    res = nba_stats.player_gamelog(player_id, season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_trend", "ok": False,
                "error": res.error or "empty upstream response"}
    try:
        pts = [float(r.get("PTS") or 0) for r in res.frame.to_dicts()]
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
            "meta": {"source": res.meta.source, "season": season}}


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
            limit=600,
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
def get_comps(player_id: str | int, season: str = SEASON, n: int = 5) -> dict[str, Any]:
    """Nearest statistical neighbors by per-game shape. Development comps."""
    player_id = coerce_player_id(player_id)
    import math

    base, _ = _warehouse_or_live(
        "silver_player_gamelogs", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: nba_stats.player_gamelog(player_id, season), season,
        entity=f"player:{player_id}", live_first=True,
    )
    if not base:
        return {"tool": "get_comps", "ok": False, "error": "no baseline games"}
    dims = ["PTS", "REB", "AST", "FG_PCT", "FG3_PCT", "MIN"]
    try:
        avgs = {d: sum(float(r.get(d) or 0) for r in base) / len(base) for d in dims}
    except (TypeError, ValueError):
        return {"tool": "get_comps", "ok": False, "error": "bad baseline"}
    cands, _ = _warehouse_or_live(
        "silver_leaders_pts", "_season = ?",
        [season], lambda: nba_stats.leaders("PTS", season), season,
        limit=600,
    )
    per_game = []
    for r in cands:
        try:
            gp = float(r.get("GP") or 0)
            if gp <= 0:
                continue
            per_game.append((
                r,
                {d: float(r.get(d) or 0) / (gp if d in ("PTS", "REB", "AST", "MIN") else 1)
                 for d in dims},
            ))
        except (TypeError, ValueError):
            continue
    scales: dict[str, float] = {}
    for d in dims:
        vals = [p[d] for _, p in per_game]
        mean = sum(vals) / max(len(vals), 1)
        var = sum((v - mean) ** 2 for v in vals) / max(len(vals), 1)
        scales[d] = var ** 0.5 or 1.0
    scored = []
    for r, per in per_game:
        try:
            v = [(per[d] - avgs[d]) / scales[d] for d in dims]
            dist = math.sqrt(sum(x * x for x in v))
            if r.get("PLAYER_ID") != player_id:
                scored.append((dist, r.get("PLAYER"), r.get("TEAM")))
        except (TypeError, ValueError):
            continue
    scored.sort()
    rows = [{"PLAYER": name, "TEAM": team, "distance": round(d, 2)}
            for d, name, team in scored[:n]]
    latest: dict[str, dict] = {}
    try:
        names = [r["PLAYER"] for r in rows]
        if names:
            con = store.connect()
            try:
                ph = ",".join("?" for _ in names)
                up = [str(x).upper() for x in names]
                q = ("SELECT PLAYER_NAME,_season,RAPTOR_TOTAL,WAR_TOTAL "
                     "FROM silver_raptor_player "
                     f"WHERE UPPER(PLAYER_NAME) IN ({ph}) ORDER BY _season DESC")
                try:
                    rf = pl.from_arrow(con.execute(q, up).fetch_arrow_table())
                except Exception:
                    rf = pl.DataFrame([])
                for d in rf.to_dicts():
                    k = str(d.get("PLAYER_NAME") or "").upper()
                    if k and k not in latest:
                        latest[k] = d
            finally:
                con.close()
    except Exception:
        latest = {}
    for r in rows:
        hit = latest.get(str(r.get("PLAYER")).upper())
        r["RAPTOR"] = hit.get("RAPTOR_TOTAL") if hit else None
        r["WAR"] = hit.get("WAR_TOTAL") if hit else None
    cov = sum(1 for r in rows if r.get("RAPTOR") is not None)
    return {"tool": "get_comps", "ok": True, "rows": rows,
            "meta": {"source": "nba_api", "season": season,
                     "raptor_coverage": f"{cov}/{len(rows)} neighbors with RAPTOR"}}


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
                               "eFG_PCT": efg, "SHARE": shr}
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
        entity=f"player:{player_id}", live_first=True,
    )
    return {"tool": "get_on_off", "ok": True, "rows": rows, "meta": meta}


@tool
def get_wowy(player_ids: str, team_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """With-or-without-you splits. player_ids is comma separated ids."""
    team_id = coerce_team_id(team_id)
    from ..sources import pbpstats

    ids = [int(x) for x in player_ids.split(",") if x.strip().isdigit()]
    rows, meta = _warehouse_or_live(
        "silver_wowy", "_season = ? AND _entity = ?",
        [season, f"wowy:{player_ids}"],
        lambda: pbpstats.wowy(ids, team_id, season), season,
        entity=f"wowy:{player_ids}", live_first=True,
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
        entity=f"player:{player_id}", live_first=True,
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
             + (" AND _season = ?" if season else "") + " ORDER BY _season DESC LIMIT 10")
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
