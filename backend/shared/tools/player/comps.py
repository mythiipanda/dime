import sys
from typing import Any

from langchain_core.tools import tool


def _pkg():
    return sys.modules[__package__]


BOX = [
    ("PTS", "PTS36"), ("REB", "REB36"), ("AST", "AST36"), ("STL", "STL36"),
    ("BLK", "BLK36"), ("FG3A", "FG3A36"), ("FTA", "FTA36"), ("TOV", "TOV36"),
]
PCTS = ["FG3_PCT", "FT_PCT"]
ADVS = ["USG_PCT", "TS_PCT", "AST_PCT", "TM_TOV_PCT", "PIE", "OFF_RATING", "DEF_RATING", "NET_RATING"]
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


def _comps_archetype(feats: dict[str, Any]) -> str:
    def _f(key: str) -> float | None:
        try:
            v = feats.get(key)
            return None if v is None else float(v)
        except (TypeError, ValueError):
            return None

    usg = _f("USG_PCT")
    if usg is not None and usg <= 1:
        usg *= 100
    ap = _f("AST_PCT")
    if ap is not None and ap <= 1:
        ap *= 100
    ts = _f("TS_PCT")
    if ts is not None and ts > 1:
        ts /= 100
    ast36, reb36, blk36, fg3a36, pts36 = _f("AST36"), _f("REB36"), _f("BLK36"), _f("FG3A36"), _f("PTS36")
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


def _comps_mins(v: object) -> float | None:
    m = _pkg()._num(v)
    if m is not None:
        return m
    s = str(v or "").strip()
    if ":" in s:
        try:
            mm, ss = s.split(":")[:2]
            return float(mm) + float(ss) / 60
        except (TypeError, ValueError):
            return None
    return None


def _pool_from_leaders(leaders, adv, use_adv):
    pkg = _pkg()
    adv_by_id = {str(r.get("PLAYER_ID")): r for r in adv if isinstance(r, dict) and r.get("PLAYER_ID") is not None}
    pool = []
    for row in leaders:
        if not isinstance(row, dict):
            continue
        total_min = pkg._num(row.get("MIN"))
        if total_min is None or total_min < 400:
            continue
        feats = {}
        for col, feat in BOX:
            v = pkg._num(row.get(col))
            feats[feat] = 36 * v / total_min if v is not None else None
        for feat in PCTS:
            feats[feat] = pkg._num(row.get(feat))
        arow = adv_by_id.get(str(row.get("PLAYER_ID")), {})
        for feat in ADVS:
            feats[feat] = pkg._num(arow.get(feat)) if use_adv else None
        try:
            entry_pid = int(row.get("PLAYER_ID"))
        except (TypeError, ValueError):
            continue
        pool.append({"sid": str(row.get("PLAYER_ID")), "pid": entry_pid, "name": row.get("PLAYER"), "team": row.get("TEAM"), "feats": feats})
    return pool


def _pool_from_gamelogs(season):
    pkg = _pkg()
    try:
        games = pkg._read_df(
            "SELECT _entity, MIN, PTS, REB, AST, STL, BLK, TOV, FG3M, FG3A, FTM, FTA, FG3_PCT, FT_PCT "
            "FROM silver_player_gamelogs WHERE _season = ?",
            [season],
        )
    except Exception:
        games = []
    by_ent: dict[str, list[dict[str, Any]]] = {}
    for g in games:
        if isinstance(g, dict) and g.get("_entity"):
            by_ent.setdefault(str(g.get("_entity")), []).append(g)
    pool = []
    for ent, gs in by_ent.items():
        feats = _gamelog_feats(gs)
        if feats is None:
            continue
        ent_pid = ent.split(":", 1)[-1] if ":" in ent else ent
        try:
            entry_pid = int(ent_pid)
        except (TypeError, ValueError):
            continue
        pool.append({"sid": str(entry_pid), "pid": entry_pid, "name": None, "team": None, "feats": feats})
    return pool


def _gamelog_feats(gs):
    pkg = _pkg()
    if len(gs) < 10:
        return None
    mins = [m for m in (_comps_mins(g.get("MIN")) for g in gs) if m is not None]
    if not mins or sum(mins) < 400:
        return None
    avg_min = sum(mins) / len(mins)
    feats: dict[str, float | None] = {}
    for col, feat in BOX:
        vals = [v for v in (pkg._num(g.get(col)) for g in gs) if v is not None]
        feats[feat] = 36 * (sum(vals) / len(vals)) / avg_min if vals else None
    for feat, make_col, att_col in (("FG3_PCT", "FG3M", "FG3A"), ("FT_PCT", "FTM", "FTA")):
        makes = 0.0
        attempts = 0.0
        for g in gs:
            make, att = pkg._num(g.get(make_col)), pkg._num(g.get(att_col))
            if make is not None and att is not None:
                makes += make
                attempts += att
        feats[feat] = makes / attempts if attempts else None
    for feat in ADVS:
        feats[feat] = None
    return feats


def _comps_pool(season, leaders, adv):
    notes = "cross-era comps unavailable"
    use_adv = bool(adv)
    if leaders:
        pool = _pool_from_leaders(leaders, adv, use_adv)
        if not use_adv:
            notes += "; advanced metrics unavailable, box-score features only"
        return notes, pool
    pool = _pool_from_gamelogs(season)
    notes += "; leaders missing, estimated from gamelogs"
    return notes, pool


def _feature_stats(pool, features):
    import math

    stats = {}
    dropped = []
    for feat in features:
        vals = [e["feats"][feat] for e in pool if isinstance(e["feats"].get(feat), (int, float))]
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
    return stats, kept, dropped


def _comp_row(e, dist, zvec, zt, kept, target, target_arch, pct_round, season):
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
        drivers.append({"stat": LABELS[feat], "target": t_round, "comp": c_round})
    arch = _comps_archetype(e["feats"])
    return {
        "PLAYER": e["name"],
        "PLAYER_ID": e["pid"],
        "TEAM": e["team"],
        "season": season,
        "era": season,
        "similarity": round(100 / (1 + dist / 20), 1),
        "archetype": arch,
        "shared_archetype": arch == target_arch,
        "drivers": drivers,
    }


def _score_comp_candidates(pool, target, kept, stats, pct_round, season, k):
    import math

    zvec: dict[str, dict[str, float]] = {}
    for e in pool:
        zvec[e["sid"]] = {
            feat: ((e["feats"].get(feat) - stats[feat][0]) / stats[feat][1] if isinstance(e["feats"].get(feat), (int, float)) else 0.0)
            for feat in kept
        }
    zt = zvec[target["sid"]]
    scored = sorted(
        ((math.sqrt(sum((zt[f] - zvec[e["sid"]][f]) ** 2 for f in kept)), e) for e in pool if e["sid"] != target["sid"]),
        key=lambda t: t[0],
    )
    target_arch = _comps_archetype(target["feats"])
    rows = [_comp_row(e, dist, zvec, zt, kept, target, target_arch, pct_round, season) for dist, e in scored[:k]]
    return target_arch, rows


@tool(description="Nearest statistical neighbors by per-36 + advanced shape. Same-season only.")
def get_comps(player_id: str | int, season: str | None = None, k: int = 5) -> dict[str, Any]:
    from .._core import clamp_season

    pkg = _pkg()
    season = clamp_season(pkg.resolve_season(season))
    try:
        k = max(1, min(int(k or 5), 15))
    except (TypeError, ValueError):
        k = 5
    try:
        pid = pkg.coerce_player_id(player_id)
    except ValueError as exc:
        return {"tool": "get_comps", "ok": False, "error": str(exc)}

    try:
        leaders = pkg._read_df("SELECT * FROM silver_leaders_pts WHERE _season = ?", [season])
    except Exception:
        leaders = []
    try:
        adv = pkg._read_df("SELECT * FROM silver_advanced WHERE _season = ?", [season])
    except Exception:
        adv = []

    notes, pool = _comps_pool(season, leaders, adv)
    if not pool:
        return {"tool": "get_comps", "ok": False, "error": f"no player stat profiles for season {season}"}
    target = next((e for e in pool if e["sid"] == str(pid)), None)
    if target is None:
        try:
            from nba_api.stats.static import players as _players

            tname = next((p.get("full_name", str(player_id)) for p in _players.get_players() if str(p.get("id")) == str(pid)), str(player_id))
        except Exception:
            tname = str(player_id)
        return {"tool": "get_comps", "ok": False, "error": f"no stat profile for {tname} in {season}"}

    features = [f for _, f in BOX] + PCTS + (ADVS if bool(adv) else [])
    stats, kept, dropped = _feature_stats(pool, features)
    if not kept:
        return {"tool": "get_comps", "ok": False, "error": f"no comparable features for season {season}"}
    pct_round = {f for f in kept if f.endswith("_PCT")}
    target_arch, rows = _score_comp_candidates(pool, target, kept, stats, pct_round, season, k)
    return {
        "tool": "get_comps",
        "ok": True,
        "player": {"name": target["name"], "id": pid, "season": season, "archetype": target_arch},
        "rows": rows,
        "meta": {
            "source": "warehouse",
            "season": season,
            "features": kept,
            "candidates": len(pool),
            "dropped_features": dropped,
            "similarity": "100/(1+d/20); d = standardized Euclidean distance over kept features",
            "notes": notes,
        },
    }
