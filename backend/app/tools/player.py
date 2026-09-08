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
    return {"tool": "get_comps", "ok": True, "rows": rows,
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
    zones = {"rim": [0, 0], "mid": [0, 0], "three": [0, 0]}
    for r in res.frame.to_dicts():
        try:
            dist = math.hypot(float(r.get("LOC_X", 0)), float(r.get("LOC_Y", 0))) / 10
        except (TypeError, ValueError):
            continue
        made = str(r.get("SHOT_MADE_FLAG", "") or "") == "1" or str(
            r.get("EVENT_TYPE", "")).lower().startswith("made")
        z = "rim" if dist < 8 else ("three" if dist > 23.75 else "mid")
        zones[z][1] += 1
        zones[z][0] += 1 if made else 0
    total = sum(a for _, a in zones.values()) or 1
    rows = [
        {"zone": z, "FGM": m, "FGA": a,
         "FG_PCT": round(m / a, 3) if a else 0.0,
         "share": round(a / total, 3)}
        for z, (m, a) in zones.items()
    ]
    return {"tool": "get_shot_zones", "ok": True, "rows": rows,
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": 3, "cached": False}}


@tool
def get_splits(player_id: str | int, season: str = SEASON) -> dict[str, Any]:
    """Home versus away plus monthly splits from the game log."""
    player_id = coerce_player_id(player_id)
    res = nba_stats.player_gamelog(player_id, season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_splits", "ok": False,
                "error": res.error or "empty upstream response"}
    try:
        g = res.frame.with_columns(
            pl.col("MATCHUP").str.contains("@").alias("away")
        )
        home = g.filter(~pl.col("away")).select("PTS", "FG_PCT")
        away = g.filter(pl.col("away")).select("PTS", "FG_PCT")
        rows = [
            {"split": "home", "GP": home.height,
             "PPG": round(home["PTS"].mean() or 0, 1)},
            {"split": "away", "GP": away.height,
             "PPG": round(away["PTS"].mean() or 0, 1)},
        ]
    except Exception as exc:
        return {"tool": "get_splits", "ok": False, "error": str(exc)[:160]}
    return {"tool": "get_splits", "ok": True, "rows": rows,
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": 2, "cached": False}}


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
