import re
from typing import Any
import unicodedata as _ud

from langchain_core.tools import tool

from ...contracts import contract_details, match_record, normalize_name, salary_records
from .._core import coerce_team_id
from ._helpers import _owned_connection, _pkg, _warehouse_tables, declare_money
from .cba_cap import _salary_vintage


def _norm_draft_year(season: str) -> str:
    season = _pkg().resolve_season(season)
    s = str(season or "").strip()
    if re.fullmatch(r"(19|20)\d\d", s):
        return s
    m = re.fullmatch(r"((?:19|20)\d\d)-(\d\d)", s)
    if m and int(m.group(2)) == (int(m.group(1)) + 1) % 100:
        return str(int(m.group(1)) + 1)
    raise ValueError(
        f"could not match {s!r} to a draft year "
        "(use a calendar year like 2025 or a season slug like 2024-25)")


@tool(description=('College production stats plus combine measurements for a draft class, sorted by an ad-hoc blend (2*PTS + 50*TS + USG), top 30 rows only. ''This is NOT the published big-board/mock-draft ranking and rows carry no board rank; for big-board order, mock placement, or any blend/join of board rank with production, query silver_draft_boards (ORDER, PLAYER_NAME, BOARD) joined to silver_prospect_stats via sql_exec instead. Pick-value math, career-WAR-by-slot and draft value-curve asks belong to silver_draft_value_curve (SLOT, MEDIAN_CAREER_WAR, VALUE_INDEX) via sql_exec, and swap-rights or pick-ownership asks to get_draft_capital — this board carries neither.'))
def get_draft_board(season: str = "2025") -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        season = _norm_draft_year(season)
    except ValueError as exc:
        return {"tool": "get_draft_board", "ok": False, "error": str(exc)}

    from ...sources import cbb as _cbb

    def norm(s: object) -> str:
        return "".join(c for c in _ud.normalize("NFKD", str(s or ""))
                       if not _ud.combining(c)).lower().strip()

    prod = _cbb.get_player_stats(2025 if season == "2025" else int(season))
    if not prod.ok or prod.frame.height == 0:
        rows, meta = pkg._warehouse_or_live(
            "silver_combine", "_season = ?",
            [season], lambda: pkg.nba_stats.combine(season), season,
        )
        if rows:
            meta = dict(meta)
            meta["note"] = ("college production stats unavailable; "
                            "combine measurements only")
            return {"tool": "get_draft_board", "ok": True,
                    "rows": rows[:30], "meta": meta}
        return {"tool": "get_draft_board", "ok": False,
                "error": (f"{season} college stats are unavailable "
                          "(upstream source blocked). Draft data covers "
                          "through the 2025 draft; the 2026 lottery and "
                          "class are not in the dataset.")}
    rows, meta = pkg._warehouse_or_live(
        "silver_combine", "_season = ?",
        [season], lambda: pkg.nba_stats.combine(season), season,
    )
    meas = {norm(r.get("PLAYER_NAME")): r for r in rows}
    board = []
    for p in prod.frame.to_dicts():
        m = meas.get(norm(p.get("PLAYER_NAME")), {})
        try:
            score = (float(p.get("PTS") or 0) * 2
                     + float(p.get("TS_PCT") or 0) * 50
                     + float(p.get("USG") or 0))
        except (TypeError, ValueError):
            continue
        board.append({"PLAYER": p.get("PLAYER_NAME"), "TEAM": p.get("TEAM"),
                      "PTS": p.get("PTS"), "TS_PCT": p.get("TS_PCT"),
                      "USG": p.get("USG"),
                      "HEIGHT": m.get("HEIGHT_WO_SHOES_FT_IN"),
                      "WINGSPAN": m.get("WINGSPAN_FT_IN"),
                      "SCORE": round(score, 1)})
    board.sort(key=lambda d: d["SCORE"], reverse=True)
    return {"tool": "get_draft_board", "ok": True, "rows": board[:30],
            "meta": {"source": "barttorvik+nba_api", "season": season,
                     "matched_measurements": sum(1 for b in board[:30]
                                                 if b["HEIGHT"]),
                     "formula": "2*PTS + 50*TS + USG"}}


@tool(description='Draft combine measurements plus shooting drills for one draft year. Returns at most 25 rows: for cohort-wide rankings, counts, means, or every-prospect sweeps (rank the whole class, how many prospects, cohort average), query silver_combine via sql_exec instead — the full class is there and this slice will not match it.')
def get_combine(season: str = "2025") -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        season = _norm_draft_year(season)
    except ValueError as exc:
        return {"tool": "get_combine", "ok": False, "error": str(exc)}
    rows, meta = pkg._warehouse_or_live(
        "silver_combine", "_season = ?",
        [season], lambda: pkg.nba_stats.combine(season), season,
    )
    if not rows:
        try:
            con = pkg.store.connect(read_only=True)
            try:
                avail = [r[0] for r in con.execute(
                    "SELECT DISTINCT _season FROM silver_combine "
                    "ORDER BY 1 DESC").fetchall()]
            finally:
                con.close()
        except Exception:
            avail = []
        if avail:
            sub = str(avail[0])
            rows, meta = pkg._warehouse_or_live(
                "silver_combine", "_season = ?",
                [sub], lambda: pkg.nba_stats.combine(sub), sub,
            )
            if rows:
                meta = dict(meta)
                meta["note"] = (f"requested draft year {season} is not "
                                f"seeded; showing {sub}, the newest "
                                "available combine year")
                season = sub
    if not rows:
        return {"tool": "get_combine", "ok": False,
                "error": meta.get("error") or "empty upstream response"}
    if len(rows) > 25:
        meta = dict(meta)
        meta["truncation"] = (f"showing 25 of {len(rows)} rows; for "
                              "cohort-wide rankings, counts or means query "
                              "silver_combine via sql_exec; the full class "
                              "is there")
    return {"tool": "get_combine", "ok": True, "rows": rows[:25],
            "meta": meta}


_CONTRACT_WEIGHTS = {"PTS": 1.0, "REB": 1.2, "AST": 1.5,
                     "STL": 2.0, "BLK": 2.0, "TOV": -1.5}


def _contract_norm(s: object) -> str:
    return normalize_name(s)


def _contract_tables(con) -> tuple[bool, set[str]]:
    tables = _warehouse_tables(con)
    if 'silver_leaders_pts' not in tables:
        return False, set()
    return (bool({'silver_cap_players', 'silver_salaries'} & tables),
            {r[1] for r in
             con.execute("PRAGMA table_info(silver_leaders_pts)").fetchall()})


def _contract_fetched(con) -> tuple[object, object]:
    try:
        tables = _warehouse_tables(con)
        cap_table = 'silver_salaries' if 'silver_salaries' in tables else 'silver_cap_players'
        return (con.execute(
            "SELECT MAX(_fetched_at) FROM silver_leaders_pts").fetchall()[0][0],
            con.execute(
                f"SELECT MAX(_fetched_at) FROM {cap_table}").fetchall()[0][0])
    except Exception:
        return None, None


def _contract_read(con, season: str):
    ready, have = _contract_tables(con)
    if not ready:
        return "empty", None, None, None, None
    pid = 'PLAYER_ID' if 'PLAYER_ID' in have else 'NULL'
    prod = con.execute(
        f"""SELECT PLAYER, TEAM, GP, PTS, REB, AST, STL, BLK, TOV, {pid}
        FROM silver_leaders_pts WHERE _season = ?""", [season]).fetchall()
    cap = salary_records(con)
    prod_date, cap_date = _contract_fetched(con)
    return None, have, prod, cap, (prod_date, cap_date)


def _contract_fitted(cap: list, by_name: dict, min_gp: int,
                     use_w: dict) -> list[dict[str, Any]]:
    fitted = []
    production = [{'PLAYER_NAME': r[0], 'TEAM': r[1], 'PLAYER_ID': r[9], 'production': r}
                  for r in by_name.values()]
    for contract in cap:
        player, team, salary = contract['PLAYER_NAME'], contract['TEAM'], contract['salary']
        match = match_record(production, player, contract.get('PLAYER_ID'), team)
        if match is None:
            continue
        _, lteam, gp, pts, reb, ast, stl, blk, tov = match['production'][:9]
        gp = gp or 0
        if gp < min_gp or gp <= 0:
            continue
        fitted.append({
            **contract_details(contract),
            "PLAYER": player, "TEAM": team or lteam,
            "SALARY": salary or 0, "GP": gp,
            "SCORE": _contract_score(match['production'], use_w)})
    return fitted


def _contract_regression(fitted: list[dict[str, Any]]) -> tuple[float, float]:
    n = len(fitted)
    mx = sum(f["SCORE"] for f in fitted) / n
    my = sum(f["SALARY"] for f in fitted) / n
    var = sum((f["SCORE"] - mx) ** 2 for f in fitted)
    if var <= 0:
        raise ValueError("no production variance")
    slope = sum((f["SCORE"] - mx) * (f["SALARY"] - my)
                for f in fitted) / var
    intercept = my - slope * mx
    for f in fitted:
        f["PREDICTED"] = int(round(slope * f["SCORE"] + intercept))
        f["RESIDUAL"] = int(f["SALARY"]) - int(f["PREDICTED"])
        f["SCORE"] = round(f["SCORE"], 2)
    return slope, intercept


def _contract_team_scope(team_arg: str) -> str:
    if not team_arg:
        return ""
    try:
        from nba_api.stats.static import teams as _teams

        tid = coerce_team_id(team_arg)
        for t in _teams.get_teams():
            if t.get("id") == tid:
                return str(t.get("abbreviation", "")).upper()
    except (ValueError, TypeError):
        return ""
    return ""


def _contract_over_under(fitted: list[dict], span: int) -> list[dict]:
    return (sorted(fitted, key=lambda f: f["RESIDUAL"], reverse=True)[:span]
            + sorted(fitted, key=lambda f: f["RESIDUAL"])[:span])


def _contract_rows(fitted: list[dict], player_arg: str, team_scope: str):
    if player_arg:
        want = _contract_norm(player_arg)
        matched = [f for f in fitted if _contract_norm(f.get("PLAYER")) == want]
        if not matched:
            return None, f"no qualified value row for {player_arg}"
        return matched[:1], None
    if team_scope:
        scoped = [f for f in fitted
                  if str(f.get("TEAM") or "").upper() == team_scope]
        if not scoped:
            return None, f"no qualified players on {team_scope}"
        return _contract_over_under(scoped, 5), None
    return _contract_over_under(fitted, 10), None


def _contract_score(row: tuple, use_w: dict) -> float | None:
    gp = row[2] or 0
    if gp <= 0:
        return None
    vals = {"PTS": row[3] or 0, "REB": row[4] or 0, "AST": row[5] or 0,
            "STL": row[6] or 0, "BLK": row[7] or 0, "TOV": row[8] or 0}
    return sum(vals[c] / gp * use_w[c] for c in use_w)


def _last_qualified_row(con, want: str, min_gp: int, season: str,
                        have: set[str]):
    pid = 'PLAYER_ID' if 'PLAYER_ID' in have else 'NULL'
    seasons = [r[0] for r in con.execute(
        "SELECT DISTINCT _season FROM silver_leaders_pts").fetchall()]
    seasons = sorted((s for s in seasons if str(s) != str(season)),
                     key=lambda s: str(s)[:4], reverse=True)
    for s in seasons:
        for r in con.execute(
                f"""SELECT PLAYER, TEAM, GP, PTS, REB, AST, STL, BLK, TOV,
                {pid} FROM silver_leaders_pts WHERE _season = ?""",
                [s]).fetchall():
            if _contract_norm(r[0]) == want and (r[2] or 0) >= min_gp:
                return s, r
    return None, None


def _contract_low_sample(player_arg: str, prod: list, cap: list,
                         have: set[str], use_w: dict, min_gp: int,
                         season: str, slope: float, intercept: float):
    want = _contract_norm(player_arg)
    cur = next((r for r in prod if _contract_norm(r[0]) == want), None)
    gp_current = (cur[2] or 0) if cur else 0
    with _owned_connection(None) as con:
        last_season, last_row = _last_qualified_row(con, want, min_gp,
                                                  season, have)
    if gp_current <= 0 and last_row is None:
        return None, None
    if gp_current > 0:
        source_row, source_season, stale = cur, season, False
    else:
        source_row, source_season, stale = last_row, last_season, True
    score = _contract_score(source_row, use_w)
    if score is None:
        return None, None
    contract = match_record(cap, player_arg,
                            source_row[9] if len(source_row) > 9 else None,
                            str(source_row[1] or ""))
    salary = (contract or {}).get('salary')
    predicted = int(round(slope * score + intercept))
    row = {
        **contract_details(contract),
        "PLAYER": source_row[0], "TEAM": source_row[1],
        "SALARY": salary, "GP": source_row[2] or 0,
        "SCORE": round(score, 2), "PREDICTED": predicted,
        "RESIDUAL": (int(salary) - predicted) if salary is not None else None,
        "PRODUCTION_SEASON": source_season,
    }
    if stale:
        row["FALLBACK_PRODUCTION"] = True
    elif 0 < gp_current < min_gp:
        row["LOW_SAMPLE"] = True
    return row, {
        "estimate": ("fallback_season" if stale
                     else ("low_sample" if gp_current < min_gp
                           else "unqualified")),
        "games_played": gp_current,
        "min_gp_threshold": min_gp,
        "production_season": source_season,
        "last_qualified_season": last_season,
    }


@tool(description="Contract value residuals from production vs salary.\n\nReturns league leaders by default; pass team for one roster or player for\none named player's modeled salary and residual.")
def get_contract_value(season: str | None = None, min_gp: int = 20,
                       team: str = "", player: str = "") -> dict[str, Any]:
    pkg = _pkg()
    season = str(pkg.resolve_season(season) or "").strip() or pkg.resolve_season(None)
    try:
        min_gp = max(10, min(int(min_gp), 82))
    except (TypeError, ValueError):
        min_gp = 20

    requested_season = season
    with _owned_connection(None) as con:
        err, have, prod, cap, dates = _contract_read(con, season)
    if err:
        return {"tool": "get_contract_value", "ok": False, "error": err}
    season_fallback = None
    if not prod:
        with _owned_connection(None, read_only=True) as probe:
            latest = probe.execute(
                "SELECT MAX(_season) FROM silver_leaders_pts").fetchone()
        latest = str(latest[0] or "") if latest else ""
        if latest and latest != season:
            season = latest
            season_fallback = latest
            with _owned_connection(None) as con:
                err, have, prod, cap, dates = _contract_read(con, season)
            if err:
                return {"tool": "get_contract_value", "ok": False,
                        "error": err}
    if not prod:
        return {"tool": "get_contract_value", "ok": False,
                "error": f"no production rows for {season}"}
    missing = [c for c in _CONTRACT_WEIGHTS if c not in have]
    use_w = {c: (0.0 if c in missing else w)
             for c, w in _CONTRACT_WEIGHTS.items()}
    by_name: dict[tuple, tuple] = {}
    for r in prod:
        key = ('id', r[9]) if r[9] is not None else ('name', _contract_norm(r[0]))
        by_name.setdefault(key, r)
    fitted = _contract_fitted(cap, by_name, min_gp, use_w)
    if len(fitted) < 2:
        return {"tool": "get_contract_value", "ok": False,
                "error": "not enough qualified players"}
    try:
        slope, intercept = _contract_regression(fitted)
    except ValueError as exc:
        return {"tool": "get_contract_value", "ok": False, "error": str(exc)}
    team_scope = _contract_team_scope(str(team or "").strip())
    rows, row_error = _contract_rows(fitted, str(player or "").strip(),
                                     team_scope)
    player_below_floor = False
    if rows is None and str(player or "").strip():
        wider = _contract_fitted(cap, by_name, 1, use_w)
        rows, row_error = _contract_rows(wider, str(player or "").strip(),
                                         team_scope)
        player_below_floor = rows is not None and any(
            int(r.get("GP") or 0) < min_gp for r in rows)
    player_arg = str(player or "").strip()
    rows, row_error = _contract_rows(fitted, player_arg, team_scope)
    estimate_meta = None
    if rows is None and player_arg:
        est_row, estimate_meta = _contract_low_sample(
            player_arg, prod, cap, have, use_w, min_gp, season,
            slope, intercept)
        if est_row is not None:
            rows = [est_row]
    if rows is None:
        return {"tool": "get_contract_value", "ok": False, "error": row_error}
    for row in rows:
        row["PREDICTED"] = round(slope * row["SCORE"] + intercept, 2)
        row["RESIDUAL"] = round(row["SALARY"] - row["PREDICTED"], 2)
    prod_date, cap_date = dates
    meta = {"formula": (
                          "score = PTS + 1.2*REB + 1.5*AST + 2*STL + 2*BLK - "
                          "1.5*TOV (per game); salary_hat = slope*score + "
                          "intercept (OLS by hand); residual = salary - "
                          "salary_hat"),
                     "weights": _CONTRACT_WEIGHTS,
                     "missing_columns_zero_weight": missing,
                     "slope": round(slope, 2), "intercept": round(intercept, 2),
                     "n_qualified": len(fitted), "min_gp": min_gp,
                     "player_below_min_gp": player_below_floor,
                     "production_season": season,
                     "salary_season": _salary_vintage()[0] or "2026-27",
                     "production_date": prod_date, "salary_date": cap_date,
                     "overpaid_first": True,
                     "team_scope": team_scope or None,
                     **({"requested_season": requested_season,
                         "production_fallback": season_fallback}
                        if season_fallback else {})}
    if estimate_meta:
        meta["production_season"] = estimate_meta["production_season"]
        meta["estimate"] = estimate_meta
        meta["estimate_note"] = (
            f"unqualified sample: {estimate_meta['games_played']} GP in "
            f"{season} (threshold {min_gp}); PREDICTED uses "
            f"{estimate_meta['production_season']} production against the "
            f"{season} salary fit"
            + (f"; last qualified season "
               f"{estimate_meta['last_qualified_season']}"
               if estimate_meta.get('last_qualified_season') else ""))
    out = {"tool": "get_contract_value", "ok": True, "rows": rows,
            "meta": meta}
    return declare_money(out, ["SALARY", "salary"])


@tool(description='Star-probability classifier from college production (honest proxy).')
def get_draft_model(season: str = "2025") -> dict[str, Any]:
    season = _pkg().resolve_season(season)
    try:
        from ...sources import cbb as _cbb
        from sklearn.linear_model import LogisticRegression
        season = _norm_draft_year(season)
        prod = _cbb.get_player_stats(int(season))
        if not prod.ok or prod.frame.height == 0:
            return {"tool": "get_draft_model", "ok": False,
                    "error": prod.error or "college stats empty"}
        feats = ["PTS", "TS_PCT", "USG", "REB", "AST"]
        pls = [p for p in prod.frame.to_dicts()
               if all(p.get(k) is not None for k in feats)]
        if len(pls) < 50:
            return {"tool": "get_draft_model", "ok": False,
                    "error": "not enough rows"}
        scores = [float(p["PTS"]) * 2 + float(p["TS_PCT"]) * 50
                  + float(p["USG"]) for p in pls]
        cut = sorted(scores, reverse=True)[max(0, len(scores) // 10 - 1)]
        y = [1 if s >= cut else 0 for s in scores]
        mus = [sum(float(p[f]) for p in pls) / len(pls) for f in feats]
        sds = []
        for j, f in enumerate(feats):
            v = sum((float(p[f]) - mus[j]) ** 2 for p in pls) / len(pls)
            sds.append(v ** 0.5 or 1.0)
        X = [[(float(p[f]) - mus[j]) / sds[j] for j, f in enumerate(feats)]
             for p in pls]
        clf = LogisticRegression(max_iter=1000).fit(X, y)
        proba = [float(v) for v in clf.predict_proba(X)[:, 1]]
        acc = sum((pr >= 0.5) == bool(t) for pr, t in zip(proba, y)) / len(y)
        top = sorted(range(len(pls)), key=lambda i: proba[i], reverse=True)[:20]
        rows = [{"PLAYER": pls[i].get("PLAYER_NAME"), "TEAM": pls[i].get("TEAM"),
                 "PTS": pls[i].get("PTS"), "TS_PCT": pls[i].get("TS_PCT"),
                 "USG": pls[i].get("USG"), "STAR_P": round(proba[i], 3)}
                for i in top]
        meta = {"source": "barttorvik+sklearn", "season": str(season),
                "n": len(pls), "features": feats,
                "label": "top-decile of 2*PTS+50*TS+USG",
                "accuracy": round(acc, 3),
                "disclaimer": "Label is a production proxy, not real NBA "
                "outcomes. In-sample accuracy only, no cross-validation."}
        return {"tool": "get_draft_model", "ok": True, "rows": rows, "meta": meta}
    except Exception as exc:
        return {"tool": "get_draft_model", "ok": False,
                "error": str(exc)[:200]}
