"""Player desk. Intel, form, comps, zones, splits, possession splits."""

from typing import Any
import polars as pl
from langchain_core.tools import tool

from .. import store
from ..sources import nba_stats
from ._core import SEASON, _warehouse_or_live


@tool
def get_player_intel(player_id: int, season: str = SEASON) -> dict[str, Any]:
    """Game log plus shot sample for one player id. Warehouse first."""
    rows, meta = _warehouse_or_live(
        "silver_player_gamelogs", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: nba_stats.player_gamelog(player_id, season), season,
        entity=f"player:{player_id}", live_first=True,
    )
    return {"tool": "get_player_intel", "ok": True, "rows": rows, "meta": meta}


@tool
def get_last_x(player_id: int, n: int = 10, season: str = SEASON) -> dict[str, Any]:
    """Last n games for one player id, most recent first."""
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
def get_percentiles(player_id: int, season: str = SEASON) -> dict[str, Any]:
    """Percentile ranks for one player id across PTS REB AST STL BLK."""
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
def get_comps(player_id: int, season: str = SEASON, n: int = 5) -> dict[str, Any]:
    """Nearest statistical neighbors by per-game shape. Development comps."""
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
def get_shot_zones(player_id: int, season: str = SEASON) -> dict[str, Any]:
    """Zone splits for one player id: rim, midrange, three with shares."""
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
        made = str(r.get("EVENT_TYPE", "")).lower().startswith("made")
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
def get_splits(player_id: int, season: str = SEASON) -> dict[str, Any]:
    """Home versus away plus monthly splits from the game log."""
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
def get_on_off(player_id: int, team_id: int, season: str = SEASON) -> dict[str, Any]:
    """On and off splits for one player on one team. Possession level."""
    from ..sources import pbpstats

    rows, meta = _warehouse_or_live(
        "silver_on_off", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pbpstats.on_off(player_id, team_id, season), season,
        entity=f"player:{player_id}", live_first=True,
    )
    return {"tool": "get_on_off", "ok": True, "rows": rows, "meta": meta}


@tool
def get_wowy(player_ids: str, team_id: int, season: str = SEASON) -> dict[str, Any]:
    """With-or-without-you splits. player_ids is comma separated ids."""
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
def get_four_factors(player_id: int, team_id: int, season: str = SEASON) -> dict[str, Any]:
    """Four factor on-off splits for one player on one team."""
    from ..sources import pbpstats

    rows, meta = _warehouse_or_live(
        "silver_four_factors", "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pbpstats.four_factors(player_id, team_id, season), season,
        entity=f"player:{player_id}", live_first=True,
    )
    return {"tool": "get_four_factors", "ok": True, "rows": rows, "meta": meta}
