import sys
from typing import Any

import polars as pl
from langchain_core.tools import tool

from ...contracts import player_name_key_sql as _player_name_key_sql


def _pkg():
    return sys.modules[__package__]


def _opp_tier_splits(frame: Any, season: str) -> list[dict[str, Any]]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    if "MATCHUP" not in frame.columns or "PTS" not in frame.columns:
        return []
    ranks = {
        str(r.get("TEAM_NAME", "")): r.get("DEF_RATING_RANK")
        for r in pkg._read_df("SELECT TEAM_NAME, DEF_RATING_RANK FROM silver_team_ratings WHERE _season = ?", [season])
    }
    if not ranks:
        return []
    from nba_api.stats.static import teams as _static

    abbr = {t["abbreviation"]: t["full_name"] for t in _static.get_teams()}
    tiers: dict[str, list[float]] = {"vs top-10 defense": [], "vs rest": []}
    for g in frame.to_dicts():
        try:
            opp = str(g.get("MATCHUP") or "").split()[-1].upper()
            rank = ranks.get(abbr.get(opp, ""), None)
            pts = float(g.get("PTS") or 0)
            tiers["vs top-10 defense" if rank is not None and rank <= 10 else "vs rest"].append(pts)
        except (TypeError, ValueError, IndexError):
            continue
    out = []
    for label, pts in tiers.items():
        if not pts:
            continue
        out.append({"split": label, "GP": len(pts), "PPG": round(sum(pts) / len(pts), 1)})
    return out


def _split_row(label: str, f) -> dict[str, Any] | None:
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


def _starter_splits(g) -> list:
    import polars as _pl

    out: list[dict[str, Any]] = []
    if "START_POSITION" in g.columns:
        try:
            started = g.filter(_pl.col("START_POSITION").is_not_null() & (_pl.col("START_POSITION").cast(_pl.String) != ""))
            benched = g.filter(_pl.col("START_POSITION").is_null() | (_pl.col("START_POSITION").cast(_pl.String) == ""))
            for label, f in (("starter", started), ("bench", benched)):
                rr = _split_row(label, f.select("PTS", "FG_PCT"))
                if rr:
                    out.append(rr)
        except Exception:
            pass
        return out
    if "GS" in g.columns:
        try:
            gs = _pl.col("GS").cast(_pl.String)
            started = g.filter(gs.is_in(["1", "1.0", "*", "S", "True", "true"]))
            benched = g.filter(~gs.is_in(["1", "1.0", "*", "S", "True", "true"]))
            for label, f in (("starter", started), ("bench", benched)):
                rr = _split_row(label, f.select("PTS", "FG_PCT"))
                if rr:
                    out.append(rr)
        except Exception:
            pass
    return out


def _monthly_splits(g) -> list:
    import polars as _pl

    out: list[dict[str, Any]] = []
    if "GAME_DATE" not in g.columns:
        return out
    try:
        _raw_mon = _pl.col("GAME_DATE").cast(_pl.String).str.slice(0, 3)
        _mon_expr = _raw_mon
        if "_d" in g.columns:
            _d_dtype = g.schema.get("_d")
            if _d_dtype is not None and type(_d_dtype) in (_pl.Date, _pl.Datetime):
                _mon_expr = _pl.when(_pl.col("_d").is_not_null()).then(_pl.col("_d").dt.strftime("%b")).otherwise(_raw_mon)
        gm = g.with_columns(_mon_expr.alias("_mon"))
        order = (
            gm.filter(_pl.col("_d").is_not_null()).group_by("_mon").agg(_pl.col("_d").min().alias("_d0"))
            if "_d" in gm.columns
            else None
        )
        agg = gm.group_by("_mon").agg(
            _pl.len().alias("GP"),
            _pl.col("PTS").mean().alias("_ppg"),
            _pl.col("FG_PCT").mean().alias("_fg") if "FG_PCT" in gm.columns else _pl.len().alias("_fg"),
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
                mrow: dict[str, Any] = {"split": str(d.get("_mon")), "GP": gp, "PPG": round(float(d.get("_ppg") or 0), 1)}
                if "FG_PCT" in gm.columns:
                    mrow["FG_PCT"] = round(float(d.get("_fg") or 0), 3)
                out.append(mrow)
            except (TypeError, ValueError):
                continue
    except Exception:
        pass
    return out


def _with_parsed_dates(g, _pl):
    if "GAME_DATE" not in g.columns:
        return g
    try:
        return g.with_columns(
            _pl.col("GAME_DATE")
            .str.strptime(_pl.Date, "%b %d, %Y", strict=False)
            .fill_null(_pl.col("GAME_DATE").str.strptime(_pl.Date, "%Y-%m-%d", strict=False))
            .alias("_d")
        )
    except Exception:
        return g


@tool(description="Home/away plus monthly, wins/losses, last-10, starter splits from the game log.")
def get_splits(player_id: str | int, season: str | None = None) -> dict[str, Any]:
    import polars as _pl

    pkg = _pkg()
    season = pkg.resolve_season(season)
    player_id = pkg.coerce_player_id(player_id)
    rows_data, warehouse_meta = pkg._warehouse_or_live(
        "silver_player_gamelogs",
        "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pkg.nba_stats.player_gamelog(player_id, season),
        season,
        entity=f"player:{player_id}",
        live_first=True,
        limit=500,
    )
    if not rows_data:
        return {"tool": "get_splits", "ok": False, "error": warehouse_meta.get("error") or "empty upstream response"}

    frame = _pl.DataFrame(rows_data)
    meta_source = warehouse_meta.get("source", "warehouse")
    meta_fetched = warehouse_meta.get("fetched_at", "")
    try:
        g = _with_parsed_dates(frame.with_columns(_pl.col("MATCHUP").str.contains("@").alias("away")), _pl)
        rows: list[dict[str, Any]] = []
        home = g.filter(~_pl.col("away")).select("PTS", "FG_PCT")
        away = g.filter(_pl.col("away")).select("PTS", "FG_PCT")
        for r in (_split_row("home", home), _split_row("away", away)):
            if r:
                rows.append(r)
        if "WL" in g.columns:
            wins = g.filter(_pl.col("WL") == "W").select("PTS", "FG_PCT")
            losses = g.filter(_pl.col("WL") == "L").select("PTS", "FG_PCT")
            for r in (_split_row("wins", wins), _split_row("losses", losses)):
                if r:
                    rows.append(r)
        ordered = g.sort("_d", descending=True) if "_d" in g.columns and g["_d"].drop_nulls().len() > 0 else None
        last10 = ordered.head(10) if ordered is not None else g.head(10)
        r = _split_row("last10", last10.select("PTS", "FG_PCT"))
        if r:
            rows.append(r)
        rows.extend(_starter_splits(g))
        rows.extend(_monthly_splits(g))
        rows = rows[:12]
    except Exception as exc:
        return {"tool": "get_splits", "ok": False, "error": str(exc)[:160]}
    try:
        rows.extend(pkg._opp_tier_splits(frame, season))
    except Exception:
        pass
    return {
        "tool": "get_splits",
        "ok": True,
        "rows": rows,
        "meta": {**warehouse_meta, "source": meta_source, "fetched_at": meta_fetched,
                 "rows": len(rows), "cached": warehouse_meta.get("cached", False)},
    }


@tool(description="Season-by-season RAPTOR and WAR for one player name. Warehouse only.")
def get_raptor_history(player: str, season: str = "") -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    name = (player or "").strip()
    if not name:
        return {"tool": "get_raptor_history", "ok": False, "error": "empty player name"}
    con = pkg.store.connect(read_only=True)
    try:
        q = (
            "SELECT * FROM silver_raptor_player WHERE "
            f"{_player_name_key_sql('PLAYER_NAME')} = {_player_name_key_sql('?')}"
            + (" AND _season = ?" if season else "")
            + " ORDER BY _season ASC LIMIT 25"
        )
        try:
            frame = pl.from_arrow(con.execute(q, [name] + ([season] if season else [])).fetch_arrow_table())
        except Exception as exc:
            return {"tool": "get_raptor_history", "ok": False, "error": f"raptor warehouse not seeded: {str(exc)[:120]}"}
        try:
            teams = {
                r[1]: r[0]
                for r in con.execute(
                    "SELECT TEAM, _season FROM silver_raptor_team WHERE "
                    f"{_player_name_key_sql('PLAYER_NAME')} = {_player_name_key_sql('?')} AND SEASON_TYPE = 'RS'",
                    [name],
                ).fetchall()
            }
        except Exception:
            teams = {}
        try:
            covered = [r[0] for r in con.execute(
                "SELECT DISTINCT _season FROM silver_raptor_player ORDER BY 1"
            ).fetchall() if r and r[0]]
        except Exception:
            covered = []
    finally:
        con.close()
    if frame.height == 0:
        where = f" in {season}" if season else ""
        pointer = (f" - silver_raptor_player covers {covered[0]} through {covered[-1]}; "
                   f"for seasons outside that range use sql_exec over silver_hist_player_seasons"
                   if covered else "")
        return {"tool": "get_raptor_history", "ok": False,
                "error": f"no RAPTOR history for '{name}'{where}{pointer}"}
    rows = [
        {
            "SEASON": r.get("_season"),
            "TEAM": teams.get(r.get("_season")),
            "MP": r.get("MP"),
            "RAPTOR_O": r.get("RAPTOR_OFFENSE"),
            "RAPTOR_D": r.get("RAPTOR_DEFENSE"),
            "RAPTOR": r.get("RAPTOR_TOTAL"),
            "WAR": r.get("WAR_TOTAL"),
        }
        for r in frame.to_dicts()
    ]
    return {
        "tool": "get_raptor_history",
        "ok": True,
        "rows": rows,
        "meta": {
            "source": "fivethirtyeight:raptor",
            "seasons": len(rows),
            "coverage": "RAPTOR ends 2021-22; later seasons read as gaps, never estimates",
        },
    }


IMPACT_PRIOR_FEATURES = ("USG_PCT", "TS_PCT", "AST_PCT", "REB_PCT", "TM_TOV_PCT")
IMPACT_PRIOR_MIN_POSS = 3000
IMPACT_PRIOR_MIN_N = 30
IMPACT_SHRINK_K = 1500
IMPACT_RAPTOR_ONOFF_W = 0.20
IMPACT_DISCLAIMER = "This is a statistical estimate, not a measured impact metric. Never present it as RAPTOR, RAPM, or BPM."


def _solve_linear(a: list[list[float]], b: list[float]) -> list[float] | None:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            return None
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))) / m[i][i]
        if abs(m[i][i]) < 1e-12:
            return None
    return x


def _fit_box_prior(season: str) -> dict[str, Any] | None:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        rows = pkg._read_df(
            "SELECT PLAYER_NAME, TEAM_ID, POSS, NET_RATING, " + ", ".join(IMPACT_PRIOR_FEATURES) + " FROM silver_advanced WHERE _season = ?",
            [season],
        )
        team_net = {
            r["TEAM_ID"]: r["NET_RATING"]
            for r in pkg._read_df("SELECT TEAM_ID, NET_RATING FROM silver_team_ratings WHERE _season = ?", [season])
            if r["NET_RATING"] is not None
        }
    except Exception:
        return None
    trainers = [
        r
        for r in rows
        if (r.get("POSS") or 0) >= IMPACT_PRIOR_MIN_POSS
        and r.get("NET_RATING") is not None
        and r.get("TEAM_ID") in team_net
        and all(r.get(f) is not None for f in IMPACT_PRIOR_FEATURES)
    ]
    if len(trainers) < IMPACT_PRIOR_MIN_N:
        return None
    cols = ["_bias"] + list(IMPACT_PRIOR_FEATURES)
    xs = [[1.0] + [float(r[f]) for f in IMPACT_PRIOR_FEATURES] for r in trainers]
    ys = [float(r["NET_RATING"]) - float(team_net[r["TEAM_ID"]]) for r in trainers]
    p = len(cols)
    ata = [[sum(x[i] * x[j] for x in xs) for j in range(p)] for i in range(p)]
    aty = [sum(x[i] * y for x, y in zip(xs, ys)) for i in range(p)]
    beta = _solve_linear(ata, aty)
    if beta is None:
        return None
    pred = [sum(b * x for b, x in zip(beta, x)) for x in xs]
    mean = sum(ys) / len(ys)
    ss_res = sum((y - q) ** 2 for y, q in zip(ys, pred))
    ss_tot = sum((y - mean) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {"intercept": beta[0], "coefs": dict(zip(IMPACT_PRIOR_FEATURES, beta[1:])), "n": len(trainers), "r2": r2}


def _raptor_row(player_id: int, name: str, season: str) -> dict[str, Any] | None:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    rows = pkg._read_df(
        "SELECT PLAYER_NAME, POSS, MP, RAPTOR_BOX_TOTAL, RAPTOR_ONOFF_TOTAL, RAPTOR_TOTAL "
        "FROM silver_raptor_player WHERE _season = ? "
        "AND (CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR) OR "
        f"{_player_name_key_sql('PLAYER_NAME')} = {_player_name_key_sql('?')}) LIMIT 1",
        [season, str(player_id), name],
    )
    return rows[0] if rows else None


def _stale_raptor(player_id: int, name: str, season: str) -> dict[str, Any] | None:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    rows = pkg._read_df(
        "SELECT _season, RAPTOR_TOTAL FROM silver_raptor_player WHERE _season < ? AND RAPTOR_TOTAL IS NOT NULL "
        "AND (CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR) OR "
        f"{_player_name_key_sql('PLAYER_NAME')} = {_player_name_key_sql('?')}) "
        "ORDER BY _season DESC LIMIT 1",
        [season, str(player_id), name],
    )
    return rows[0] if rows else None


def _raptor_component_result(base: dict[str, Any], raptor: dict[str, Any], player_id: int, name: str, season: str) -> dict[str, Any]:
    box = raptor.get("RAPTOR_BOX_TOTAL")
    onoff = raptor.get("RAPTOR_ONOFF_TOTAL")
    if box is None or onoff is None:
        return {
            **base,
            "ok": False,
            "error": f"RAPTOR components missing for '{name}' in {season}; measured RAPTOR exists, use get_raptor_history instead",
        }
    w = IMPACT_RAPTOR_ONOFF_W
    estimate = (1 - w) * float(box) + w * float(onoff)
    return {
        **base,
        "ok": True,
        "season": season,
        "player": {"player_id": player_id, "name": raptor.get("PLAYER_NAME") or name},
        "estimate_per_100": round(estimate, 2),
        "method": "raptor_components",
        "method_kind": "estimate",
        "methodology": (
            "Empirical RAPTOR reconstruction: 0.80 * box component + 0.20 * on-off component. "
            "Weight fitted from 4,684 player-seasons (2013-14..2021-22); implied on/off weight 0.19-0.22, "
            "flat across minutes. Blend reconstructs RAPTOR_TOTAL with MAE 0.66, p95 residual 2.16 per 100 possessions."
        ),
        "components": {
            "raptor_box_per_100": round(float(box), 2),
            "raptor_onoff_per_100": round(float(onoff), 2),
            "onoff_weight": w,
            "possessions": raptor.get("POSS"),
            "minutes": raptor.get("MP"),
        },
        "measured": {
            "metric": "RAPTOR",
            "total_per_100": round(float(raptor["RAPTOR_TOTAL"]), 2),
            "season": season,
            "note": "Measured metric shown for comparison; the estimate above remains an estimate.",
        },
        "confidence": {
            "level": "high",
            "notes": ["Measured RAPTOR exists for this player-season; estimate is a component reconstruction for comparison."],
        },
    }


def _prior_contribution(row: dict[str, Any], season: str, notes: list[str]) -> tuple[float, dict[str, Any]]:
    prior = _fit_box_prior(season)
    if prior is None:
        notes.append("Box prior could not be fitted (too few high-minute players); prior falls back to 0.0.")
        return 0.0, {"fitted": False}
    if any(row.get(f) is None for f in IMPACT_PRIOR_FEATURES):
        notes.append(f"Player box features incomplete; prior falls back to the high-minute mean lift of {prior['intercept']:+.2f}.")
        return float(prior["intercept"]), {"fitted": True, "n": prior["n"], "r2": round(prior["r2"], 3), "note": "feature fallback"}
    prior_value = float(prior["intercept"]) + sum(float(prior["coefs"][f]) * float(row[f]) for f in IMPACT_PRIOR_FEATURES)
    return prior_value, {"fitted": True, "n": prior["n"], "r2": round(prior["r2"], 3)}


@tool(
    description="Estimated per-100-possession impact from box-score and on-court components.\n\nWhen measured RAPTOR is unavailable for a player-season, this synthesizes an\nestimate from silver_advanced and silver_team_ratings. It does not read\nsilver_rapm or silver_impact, so the fallback says nothing about RAPM or BPM\ncoverage.\nALWAYS an estimate (is_estimate=True): never present it as measured.\nMethods: box_prior_shrinkage (marginal on-court lift shrunk toward an\nOLS box-score prior, current season) or raptor_components (empirical\n80/20 box/on-off blend, historical seasons with RAPTOR components)."
)
def get_impact_estimate(player: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    base: dict[str, Any] = {"tool": "get_impact_estimate", "is_estimate": True, "disclaimer": IMPACT_DISCLAIMER}
    try:
        player_id = pkg.coerce_player_id(player)
    except ValueError as exc:
        return {**base, "ok": False, "error": str(exc)}
    name = str(player).strip()
    season = (season or pkg.resolve_season(None) or "").strip()

    raptor = _raptor_row(player_id, name, season)
    if raptor and raptor.get("RAPTOR_TOTAL") is not None:
        return _raptor_component_result(base, raptor, player_id, name, season)

    adv = pkg._read_df(
        "SELECT PLAYER_NAME, TEAM_ABBREVIATION, TEAM_ID, GP, MIN, POSS, NET_RATING, "
        + ", ".join(IMPACT_PRIOR_FEATURES)
        + " FROM silver_advanced WHERE _season = ? AND CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR) LIMIT 1",
        [season, str(player_id)],
    )
    if not adv:
        return {**base, "ok": False, "error": f"no component data for '{name}' in {season}: no RAPTOR row and no advanced box row"}
    row = adv[0]
    notes: list[str] = [
        f"No measured RAPTOR row for '{name}' in {season}; RAPTOR coverage is frozen at 2021-22. "
        "This estimate uses silver_advanced and silver_team_ratings only; it does not read silver_rapm or silver_impact."
    ]
    try:
        team_net = {
            r["TEAM_ID"]: r["NET_RATING"]
            for r in pkg._read_df("SELECT TEAM_ID, NET_RATING FROM silver_team_ratings WHERE _season = ?", [season])
            if r["NET_RATING"] is not None
        }
    except Exception:
        team_net = {}
    poss = float(row.get("POSS") or 0)
    on_court = row.get("NET_RATING")
    tnet = team_net.get(row.get("TEAM_ID"))
    if on_court is None:
        return {**base, "ok": False, "error": f"advanced row for '{name}' lacks NET_RATING"}
    if tnet is None:
        notes.append("Team net rating unavailable; lift computed vs a league-average team (0.0).")
        tnet = 0.0
    lift = float(on_court) - float(tnet)
    prior_value, prior_detail = _prior_contribution(row, season, notes)
    k = IMPACT_SHRINK_K
    w_meas = poss / (poss + k) if poss > 0 else 0.0
    estimate = w_meas * lift + (1 - w_meas) * prior_value
    level = "high" if poss >= 3000 else ("medium" if poss >= 1000 else "low")
    if w_meas < 0.5:
        notes.append(f"Prior-dominated estimate: only {poss:.0f} possessions vs prior strength {k}; measured on-court lift gets {w_meas:.0%} weight.")
    notes.append("On-court lift is unadjusted for teammates, opponents, and lineup context; it is not RAPM.")
    stale = _stale_raptor(player_id, name, season)
    stale_out = (
        {
            "metric": "RAPTOR",
            "total_per_100": round(float(stale["RAPTOR_TOTAL"]), 2),
            "season": stale["_season"],
            "note": "Stale measured metric shown for context only; not used in the estimate.",
        }
        if stale
        else None
    )
    return {
        **base,
        "ok": True,
        "season": season,
        "player": {"player_id": player_id, "name": row.get("PLAYER_NAME") or name, "team": row.get("TEAM_ABBREVIATION")},
        "estimate_per_100": round(estimate, 2),
        "method": "box_prior_shrinkage",
        "method_kind": "estimate",
        "methodology": (
            "Marginal on-court lift (player on-court NET_RATING minus team NET_RATING, per 100 possessions) "
            "shrunk toward an OLS box-score prior: lift ~ USG_PCT + TS_PCT + AST_PCT + REB_PCT + TM_TOV_PCT, "
            f"fitted on players with 3000+ possessions in {season}. Shrinkage: estimate = (poss * lift + {k} * prior) / (poss + {k})."
        ),
        "components": {
            "measured_lift_per_100": round(lift, 2),
            "measured_possessions": round(poss),
            "box_prior_per_100": round(prior_value, 2),
            "box_prior": prior_detail,
            "measured_weight": round(w_meas, 3),
            "prior_weight": round(1 - w_meas, 3),
            "shrinkage_K_possessions": k,
            "games": row.get("GP"),
            "minutes": row.get("MIN"),
        },
        "measured": None,
        "stale_measured": stale_out,
        "confidence": {"level": level, "notes": notes},
    }


DPOY_MINUTES = 500
UNSUNG_MIN_MINUTES = 200
UNSUNG_MAX_MINUTES = 1000


@tool(description="Hustle leaderboards from warehouse only: DPOY composite, screen-assist\nkings, and unsung defenders with elite per-minute hustle in small roles.")
def get_hustle_boards(season: str | None = None, top: int = 10) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        top = max(1, min(int(top or 10), 25))
    except (TypeError, ValueError):
        top = 10
    try:
        dpoy = pkg._read_df(
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
        kings = pkg._read_df(
            "SELECT PLAYER_NAME, TEAM_ABBREVIATION, G, MIN, SCREEN_ASSISTS, SCREEN_AST_PTS, "
            "ROUND(SCREEN_ASSISTS * 1.0 / NULLIF(G, 0), 2) AS screen_ast_per_game "
            "FROM silver_hustle_player WHERE _season = ? ORDER BY SCREEN_ASSISTS DESC LIMIT ?",
            [season, top],
        )
        unsung = pkg._read_df(
            "SELECT h.PLAYER_NAME, h.TEAM_ABBREVIATION, h.G, h.MIN, h.DEFLECTIONS, h.CHARGES_DRAWN, h.CONTESTED_SHOTS, "
            "h.BOX_OUTS, h.LOOSE_BALLS_RECOVERED, "
            "ROUND((h.DEFLECTIONS + h.CHARGES_DRAWN + h.CONTESTED_SHOTS) * 36.0 / NULLIF(h.MIN, 0), 2) AS hustle_per36, "
            "ROUND(l.PTS * 1.0 / NULLIF(l.GP, 0), 1) AS ppg FROM silver_hustle_player h "
            "LEFT JOIN silver_leaders_pts l ON CAST(l.PLAYER_ID AS VARCHAR) = CAST(h.PLAYER_ID AS VARCHAR) AND l._season = h._season "
            "WHERE h._season = ? AND h.MIN >= ? AND h.MIN < ? AND h.G >= 20 ORDER BY hustle_per36 DESC LIMIT ?",
            [season, UNSUNG_MIN_MINUTES, UNSUNG_MAX_MINUTES, top],
        )
    except Exception as exc:
        return {"tool": "get_hustle_boards", "ok": False, "error": f"hustle warehouse not seeded: {str(exc)[:120]}"}
    if not dpoy:
        return {"tool": "get_hustle_boards", "ok": False, "error": f"no hustle rows for {season}"}
    return {
        "tool": "get_hustle_boards",
        "ok": True,
        "rows": {"dpoy": dpoy, "screen_assist_kings": kings, "unsung_defenders": unsung},
        "meta": {
            "source": "nba_api",
            "season": season,
            "top": top,
            "dpoy_formula": "(deflections + charges drawn + contested shots) per minute, 500+ minutes",
            "unsung_rule": "MIN 200-1000 with G >= 20, ranked by hustle per 36, ppg joined for usage context",
        },
    }
