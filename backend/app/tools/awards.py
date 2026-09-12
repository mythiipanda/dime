"""Award races from warehouse stats only."""

from typing import Any

from langchain_core.tools import tool

from .. import store
from ._core import SEASON, clamp_season

MIP_MSG = ("MIP needs prior-season per-player stats; silver_hist_gamelogs "
           "is team-level and there is no player-seasons table in the warehouse")

AWARD_SPECS: dict[str, dict[str, Any]] = {
    "MVP": {
        "aliases": {"mvp", "most valuable player"},
        "components": [("ppg", 0.35, 1), ("team_win_pct", 0.20, 1), ("net_rating", 0.15, 1),
                       ("apg", 0.15, 1), ("rpg", 0.15, 1)],
        "qualification": {"min_gp": 20, "min_minutes": 500},
    },
    "DPOY": {
        "aliases": {"dpoy", "defensive player of the year", "defensive player", "best defender"},
        "components": [("bpg", 0.30, 1), ("spg", 0.20, 1), ("def_rating", 0.20, -1),
                       ("dreb_pg", 0.15, 1), ("team_opp_ppg", 0.15, -1)],
        "qualification": {"min_gp": 20, "min_minutes": 500},
    },
    "ROY": {
        "aliases": {"roy", "rookie of the year", "rookie", "best rookie"},
        "components": [("ppg", 0.40, 1), ("eff_pg", 0.25, 1), ("apg", 0.20, 1), ("rpg", 0.15, 1)],
        "qualification": {"min_gp": 20, "min_minutes": 300, "max_age": 21},
        "proxy_caveat": "warehouse has no rookie flag; candidates limited to age <= 21 as a rookie proxy",
    },
    "6MOY": {
        "aliases": {"6moy", "sixth man of the year", "sixth man", "sixthman", "6th man", "best bench"},
        "components": [("ppg", 0.40, 1), ("ts_pct", 0.25, 1), ("eff_pg", 0.20, 1), ("apg", 0.15, 1)],
        "qualification": {"min_gp": 20, "min_minutes": 400, "max_mpg": 30.0},
        "proxy_caveat": "warehouse has no starter/bench split; candidates limited to under 30.0 MPG as a bench-adjacent proxy",
    },
    "MIP": {
        "aliases": {"mip", "most improved player", "most improved"},
        "components": [], "qualification": {}, "unavailable": MIP_MSG,
    },
}

FEATURE_LABELS = {
    "ppg": "PPG", "apg": "APG", "rpg": "RPG", "bpg": "BPG", "spg": "SPG", "dreb_pg": "DREB/G",
    "eff_pg": "EFF/G", "ts_pct": "TS%", "net_rating": "net rating", "def_rating": "DEF rating",
    "team_win_pct": "team win%", "team_opp_ppg": "opp PPG",
}

_ROUND3 = {"ts_pct", "team_win_pct"}


def _round_val(key: str, value: object) -> float:
    return round(float(value or 0), 3) if key in _ROUND3 else round(float(value or 0), 1)


def normalize_award(name: object) -> str | None:
    key = str(name or "").strip().lower()
    for canon, spec in AWARD_SPECS.items():
        if key == canon.lower() or key in spec.get("aliases", set()):
            return canon
    return None


def _formula(spec: dict[str, Any]) -> str:
    out = ""
    for i, (feat, weight, sign) in enumerate(spec["components"]):
        tag = f"{weight:g}*z({FEATURE_LABELS.get(feat, feat)})"
        if i == 0:
            out = f"-{tag}" if sign < 0 else tag
        else:
            out += f" - {tag}" if sign < 0 else f" + {tag}"
    return out


def _qualification(spec: dict[str, Any]) -> str:
    qual = spec.get("qualification", {})
    parts = []
    if "min_gp" in qual:
        parts.append(f"GP>={qual['min_gp']}")
    if "min_minutes" in qual:
        parts.append(f"MIN>={qual['min_minutes']}")
    if "max_age" in qual:
        parts.append(f"AGE<={qual['max_age']}")
    if "max_mpg" in qual:
        parts.append(f"MPG<={qual['max_mpg']}")
    return ", ".join(parts)


def _missing_table() -> str | None:
    try:
        con = store.connect()
    except Exception:
        return None
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    for table in ("silver_leaders_pts", "silver_advanced", "silver_standings"):
        if table not in tables:
            return table
    return None


def _pool(season: str) -> list[dict[str, Any]]:
    return store._read_df(
        """SELECT l.PLAYER AS player, l.TEAM AS team,
        l.GP AS gp, l.MIN AS mins,
        l.PTS * 1.0 / NULLIF(l.GP, 0) AS ppg,
        l.REB * 1.0 / NULLIF(l.GP, 0) AS rpg,
        l.AST * 1.0 / NULLIF(l.GP, 0) AS apg,
        l.STL * 1.0 / NULLIF(l.GP, 0) AS spg,
        l.BLK * 1.0 / NULLIF(l.GP, 0) AS bpg,
        l.DREB * 1.0 / NULLIF(l.GP, 0) AS dreb_pg,
        l.EFF * 1.0 / NULLIF(l.GP, 0) AS eff_pg,
        l.MIN * 1.0 / NULLIF(l.GP, 0) AS mpg,
        a.AGE AS age, a.TS_PCT AS ts_pct,
        a.NET_RATING AS net_rating, a.DEF_RATING AS def_rating,
        s.WINS * 1.0 / NULLIF(s.WINS + s.LOSSES, 0) AS team_win_pct,
        s.OppPointsPG AS team_opp_ppg
        FROM silver_leaders_pts l
        LEFT JOIN silver_advanced a
        ON CAST(a.PLAYER_ID AS VARCHAR) = CAST(l.PLAYER_ID AS VARCHAR)
        AND a._season = l._season
        LEFT JOIN silver_standings s
        ON s.TeamID = l.TEAM_ID AND s._season = l._season
        WHERE l._season = ?""",
        [season],
    )


@tool
def get_award_race(award: str, season: str = SEASON) -> dict[str, Any]:
    """Award race top 5 for MVP/DPOY/ROY/6MOY.

    The formula is computed from warehouse stats only and listed in meta.
    """
    import statistics as _stats

    season = clamp_season(season)
    canon = normalize_award(award)
    if canon is None:
        valid = ", ".join(sorted(AWARD_SPECS))
        return {"tool": "get_award_race", "ok": False, "rows": {},
                "meta": {}, "error": f"unknown award '{award}'; valid awards: {valid}"}
    spec = AWARD_SPECS[canon]
    if spec.get("unavailable"):
        return {"tool": "get_award_race", "ok": False, "rows": {},
                "meta": {"award": canon, "season": season}, "error": spec["unavailable"]}
    missing = _missing_table()
    if missing:
        return {"tool": "get_award_race", "ok": False, "rows": {},
                "meta": {"award": canon, "season": season},
                "error": f"warehouse table missing: {missing}"}
    try:
        pool = _pool(season)
    except Exception as exc:
        return {"tool": "get_award_race", "ok": False, "rows": {},
                "meta": {"award": canon, "season": season},
                "error": f"warehouse read failed: {str(exc)[:120]}"}
    if not pool:
        return {"tool": "get_award_race", "ok": False, "rows": {},
                "meta": {"award": canon, "season": season},
                "error": f"no rows for season {season}"}
    qual = spec.get("qualification", {})
    comps = spec["components"]
    eligible = []
    for row in pool:
        try:
            gp = row.get("gp") or 0
            mins = row.get("mins") or 0
            if gp < qual.get("min_gp", 0) or mins < qual.get("min_minutes", 0):
                continue
            if "max_age" in qual and (row.get("age") is None
                                      or float(row["age"]) > qual["max_age"]):
                continue
            if "max_mpg" in qual and (row.get("mpg") is None
                                      or float(row["mpg"]) > qual["max_mpg"]):
                continue
            if any(row.get(feat) is None for feat, _, _ in comps):
                continue
        except (TypeError, ValueError):
            continue
        eligible.append(row)
    if not eligible:
        return {"tool": "get_award_race", "ok": False, "rows": {},
                "meta": {"award": canon, "season": season},
                "error": f"no qualified candidates for {canon} in season {season}"}
    means, stds, bests = {}, {}, {}
    signs = {feat: sign for feat, _, sign in comps}
    for feat, _, _ in comps:
        vals = [float(r[feat]) for r in eligible]
        means[feat] = sum(vals) / len(vals)
        stds[feat] = _stats.pstdev(vals) if len(vals) > 1 else 0.0
        bests[feat] = max(vals) if signs[feat] > 0 else min(vals)
    scored = []
    for row in eligible:
        contribs = []
        total = 0.0
        for feat, weight, sign in comps:
            std = stds[feat]
            z = 0.0 if std < 1e-9 else (float(row[feat]) - means[feat]) / std
            contrib = weight * sign * z
            total += contrib
            contribs.append((contrib, feat, z))
        contribs.sort(key=lambda t: t[0], reverse=True)
        scored.append((total, row, contribs))
    scored.sort(key=lambda t: t[0], reverse=True)
    candidates = []
    for rank, (total, row, contribs) in enumerate(scored[:5], 1):
        drivers = [{"stat": FEATURE_LABELS.get(feat, feat),
                    "value": _round_val(feat, row[feat]),
                    "z": round(z, 2)} for _, feat, z in contribs[:3]]
        leader = next((f for _, f, _ in contribs[:3]
                       if float(row[f]) == bests[f]), None)
        if leader is not None:
            case_for = (f"leads the pool in {FEATURE_LABELS.get(leader, leader)} "
                        f"at {_round_val(leader, row[leader])}")
        else:
            top_feat, top_z = contribs[0][1], contribs[0][2]
            case_for = (f"strongest edge is {FEATURE_LABELS.get(top_feat, top_feat)} "
                        f"at {_round_val(top_feat, row[top_feat])} (z {top_z:+.2f})")
        weak_feat = contribs[-1][1]
        weak_label = FEATURE_LABELS.get(weak_feat, weak_feat)
        weak_val, weak_avg = _round_val(weak_feat, row[weak_feat]), _round_val(weak_feat, means[weak_feat])
        raw, avg = float(row[weak_feat]), means[weak_feat]
        below = (raw < avg) if signs[weak_feat] > 0 else (raw > avg)
        if below:
            case_against = (f"below pool average in {weak_label} "
                            f"({weak_val} vs pool avg {weak_avg})")
        else:
            case_against = (f"weakest edge is {weak_label} "
                            f"({weak_val} vs pool avg {weak_avg})")
        candidates.append({"rank": rank, "player": row["player"], "team": row["team"],
                           "score": round(total, 2), "drivers": drivers,
                           "case_for": case_for, "case_against": case_against})
    meta: dict[str, Any] = {
        "award": canon, "season": season, "formula": _formula(spec),
        "qualification": _qualification(spec),
        "components": [{"feature": feat, "weight": weight,
                        "direction": "higher-is-better" if sign > 0 else "lower-is-better"}
                       for feat, weight, sign in comps],
        "source": "warehouse (nba_api)",
        "advanced_metrics": "EPM/LEBRON/DARKO/RAPTOR not in warehouse; not fabricated",
    }
    if spec.get("proxy_caveat"):
        meta["proxy_caveat"] = spec["proxy_caveat"]
    from ._core import season_static as _season_static
    if _season_static(season):
        # QA #30 nit: season ended in June; a "top candidate" card must
        # not read like a live race. The dataset has no award outcomes.
        meta["season_complete"] = True
        meta["note"] = (f"{season} is complete. These are formula-based "
                        f"statistical candidates from final stats; the "
                        f"dataset does not record the actual award "
                        f"outcome, so present them as model picks, not "
                        f"a live race or official result.")
    return {"tool": "get_award_race", "ok": True,
            "rows": {"candidates": candidates}, "meta": meta}
