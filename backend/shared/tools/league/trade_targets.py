from typing import Any

from langchain_core.tools import tool

from ...contracts import canonical_team_abbr
from ._helpers import _owned_connection, declare_money
from .cba_cap import CAP, _payroll_source, _salary_date, _resolve_team_abbr
from .draft_contracts import _contract_norm
from .._core import team_error_message
from .value_contracts import _cap_band, _prod_rows, _PROD_WEIGHTS, _value_score

_MIN_GP = 25
_MIN_MPG = 12.0
_LIMIT = 15

_POS_GROUPS = {
    "g": "G", "guard": "G", "guards": "G",
    "f": "F", "wing": "F", "wings": "F", "forward": "F", "forwards": "F",
    "c": "C", "center": "C", "centers": "C", "big": "C", "bigs": "C",
}


def _table_cols(con, table: str) -> set[str]:
    try:
        return {r[1] for r in con.execute(
            f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def _position_map(con) -> tuple[dict[str, str], str | None]:
    if "silver_boxscores" not in {r[0] for r in con.execute(
            "SHOW TABLES").fetchall()}:
        return {}, "silver_boxscores missing"
    cols = _table_cols(con, "silver_boxscores")
    need = {"firstName", "familyName", "position", "_season"}
    if not need <= cols:
        return {}, f"silver_boxscores lacks {sorted(need - cols)}"
    latest = con.execute(
        "SELECT MAX(_season) FROM silver_boxscores").fetchone()[0]
    counts: dict[str, dict[str, int]] = {}
    for first, last, pos in con.execute(
            "SELECT firstName, familyName, position FROM silver_boxscores "
            "WHERE _season = ? AND position <> ''", [latest]).fetchall():
        key = _contract_norm(f"{first} {last}")
        counts.setdefault(key, {})
        counts[key][str(pos)] = counts[key].get(str(pos), 0) + 1
    return ({k: max(v.items(), key=lambda kv: kv[1])[0]
             for k, v in counts.items()}, str(latest))


def _advanced_map(con, season: str) -> dict[str, dict]:
    cols = _table_cols(con, "silver_advanced")
    if not cols:
        return {}
    pick = [c for c in ["PLAYER_NAME", "AGE", "GP", "MIN", "DEF_RATING",
                        "NET_RATING", "TS_PCT", "USG_PCT", "PIE"]
            if c in cols]
    if "PLAYER_NAME" not in pick:
        return {}
    out = {}
    for tup in con.execute(
            f"SELECT {', '.join(pick)} FROM silver_advanced "
            "WHERE _season = ?", [season]).fetchall():
        row = dict(zip(pick, tup))
        out.setdefault(_contract_norm(row.get("PLAYER_NAME")), row)
    return out


def _rapm_map(con, season: str) -> dict[str, dict]:
    cols = _table_cols(con, "silver_rapm")
    if not cols:
        return {}
    pick = [c for c in ["name", "rapm", "possessions"] if c in cols]
    if "name" not in pick:
        return {}
    out = {}
    for tup in con.execute(
            f"SELECT {', '.join(pick)} FROM silver_rapm "
            "WHERE _season = ?", [season]).fetchall():
        row = dict(zip(pick, tup))
        out.setdefault(_contract_norm(row.get("name")), row)
    return out


def _hustle_map(con) -> tuple[dict[str, dict], str | None]:
    cols = _table_cols(con, "silver_hist_hustle")
    if not cols:
        return {}, None
    pick = [c for c in ["player_name", "g", "deflections", "contested_shots",
                        "season"] if c in cols]
    if "player_name" not in pick:
        return {}, None
    latest = con.execute(
        "SELECT MAX(season) FROM silver_hist_hustle").fetchone()[0]
    out = {}
    for tup in con.execute(
            f"SELECT {', '.join(pick)} FROM silver_hist_hustle "
            "WHERE season = ?", [latest]).fetchall():
        row = dict(zip(pick, tup))
        out.setdefault(_contract_norm(row.get("player_name")), row)
    return out, str(latest)


def _cap_player_map(con) -> dict[str, dict]:
    cols = _table_cols(con, "silver_cap_players")
    if not cols:
        return {}
    pick = [c for c in ["player", "contract_type", "player_option",
                        "team_option", "guaranteed"] if c in cols]
    if "player" not in pick:
        return {}
    out = {}
    for tup in con.execute(
            f"SELECT {', '.join(pick)} FROM silver_cap_players").fetchall():
        row = dict(zip(pick, tup))
        out.setdefault(_contract_norm(row.get("player")), row)
    return out


@tool(description="Trade-target screening list for a declared roster need. "
    "Scans every non-acquirer contract on the latest salary sheet and ranks "
    "eligible candidates on the pinned production score "
    "(PTS + 1.2REB + 1.5AST + 2STL + 2BLK - 1.5TOV per game). Filters: "
    "'position' (G/F/C or guard/wing/big), 'max_salary', 'min_gp', 'min_mpg'. "
    "Each row carries contract cost (salary, cap share, cheap/mid/expensive "
    "band, option flags), age, production rates, defensive indicators "
    "(def_rating, deflections, contested shots, rapm) and value-per-$1M so "
    "the fit reasoning can happen on real numbers. 'team' is the acquiring "
    "team - its roster is excluded from the target pool.")
def get_trade_targets(need: str = "", team: str = "", position: str = "",
                      max_salary: int | None = None, min_gp: int = _MIN_GP,
                      min_mpg: float = _MIN_MPG, limit: int = _LIMIT,
                      season: str | None = None) -> dict[str, Any]:
    raw_team = str(team or "").strip()
    acquirer = (_resolve_team_abbr(canonical_team_abbr(raw_team)) or "").upper() \
        if raw_team else ""
    if raw_team and not acquirer:
        return {"tool": "get_trade_targets", "ok": False,
                "error": team_error_message(raw_team),
                "rows": [], "columns": _COLUMNS}
    pos = _POS_GROUPS.get(str(position or "").strip().lower())
    if str(position or "").strip() and pos is None:
        return {"tool": "get_trade_targets", "ok": False,
                "error": f"unknown position '{position}' - "
                         "use G/F/C or guard/wing/big",
                "rows": [], "columns": _COLUMNS}
    with _owned_connection(None, read_only=True) as con:
        if not season:
            try:
                season = con.execute(
                    "SELECT MAX(_season) FROM silver_leaders_pts"
                    ).fetchone()[0]
            except Exception:
                season = None
        season = str(season or "")
        prod, have, err = _prod_rows(con, season)
        if err:
            return {"tool": "get_trade_targets", "ok": False,
                    "error": err, "rows": [], "columns": _COLUMNS}
        if not prod:
            return {"tool": "get_trade_targets", "ok": False,
                    "error": f"no production rows for {season}",
                    "rows": [], "columns": _COLUMNS}
        from shared.contracts import salary_records
        cap = salary_records(con)
        if not cap:
            return {"tool": "get_trade_targets", "ok": False,
                    "error": "no salary rows - silver_salaries missing",
                    "rows": [], "columns": _COLUMNS}
        pos_map, pos_season = _position_map(con)
        adv = _advanced_map(con, season)
        rapm = _rapm_map(con, season)
        hustle, hustle_season = _hustle_map(con)
        cap_players = _cap_player_map(con)
        salary_date = _salary_date(con)
        source = _payroll_source(con)
    prod_by_name = {}
    for r in prod:
        prod_by_name.setdefault(_contract_norm(r.get("PLAYER")), r)
    missing = [c for c in _PROD_WEIGHTS if c not in have]
    use_w = {c: (0.0 if c in missing else w)
             for c, w in _PROD_WEIGHTS.items()}
    skipped = {"acquirer": 0, "max_salary": 0, "position": 0,
               "no_production": 0, "floor": 0}
    rows: list[dict] = []
    for c in cap:
        name = str(c.get("PLAYER_NAME") or "")
        player_team = canonical_team_abbr(c.get("TEAM"))
        salary = int(c.get("salary") or 0)
        if acquirer and player_team == acquirer:
            skipped["acquirer"] += 1
            continue
        if max_salary is not None and salary > int(max_salary):
            skipped["max_salary"] += 1
            continue
        key = _contract_norm(name)
        player_pos = pos_map.get(key)
        if pos and player_pos != pos:
            skipped["position"] += 1
            continue
        p = prod_by_name.get(key)
        if p is None:
            skipped["no_production"] += 1
            continue
        gp = int(p.get("GP") or 0)
        mins = float(p.get("MIN") or 0)
        mpg = round(mins / gp, 1) if gp and mins else 0.0
        if gp < int(min_gp) or mpg < float(min_mpg):
            skipped["floor"] += 1
            continue
        score = _value_score(p, use_w)
        vpd = round(score / (salary / 1_000_000), 3) if salary > 0 else None
        a = adv.get(key) or {}
        r_ = rapm.get(key) or {}
        h = hustle.get(key) or {}
        cp = cap_players.get(key) or {}
        h_g = int(h.get("g") or 0)
        row = {"player": name, "team": player_team,
               "position": player_pos,
               "age": a.get("AGE"), "salary": salary,
               "cap_share": round(salary / CAP["cap"], 4),
               "cost_band": _cap_band(salary / CAP["cap"]),
               "contract_type": cp.get("contract_type"),
               "player_option": cp.get("player_option"),
               "team_option": cp.get("team_option"),
               "guaranteed": cp.get("guaranteed"),
               "gp": gp, "mpg": mpg,
               "target_score": score,
               "value_per_m": vpd,
               "def_rating": a.get("DEF_RATING"),
               "net_rating": a.get("NET_RATING"),
               "ts_pct": a.get("TS_PCT"),
               "usg_pct": a.get("USG_PCT"),
               "rapm": r_.get("rapm"),
               "deflections_pg": round(float(h["deflections"]) / h_g, 2)
               if h_g and h.get("deflections") is not None else None,
               "contested_shots_pg": round(float(h["contested_shots"]) / h_g, 2)
               if h_g and h.get("contested_shots") is not None else None}
        prod_team = canonical_team_abbr(p.get("TEAM"))
        if prod_team and prod_team != player_team:
            row["production_team"] = prod_team
        rows.append(row)
    rows.sort(key=lambda r: -r["target_score"])
    for i, r in enumerate(rows, 1):
        r["target_rank"] = i
    rows = rows[: int(limit)]
    checks = [
        {"rule": "cohort eligibility", "checked": True,
         "note": f"pinned: GP>={min_gp} and MPG>={min_mpg} on {season} "
                 f"per-game rates; skipped: {skipped}"},
        {"rule": "need text", "checked": False,
         "note": "the declared need is carried as context, not parsed - "
                 "fit reasoning belongs to the answer, not the tool"},
        {"rule": "ranking formula", "checked": True,
         "note": "target_score = PTS + 1.2REB + 1.5AST + 2STL + 2BLK "
                 "- 1.5TOV per game - production proxy, not impact"
                 + (f"; missing columns zero-weighted: {missing}"
                    if missing else "")},
        {"rule": "defensive indicators", "checked": True,
         "note": "def_rating/deflections/contested_shots/rapm are "
                 "columns to reason over; STL/BLK are the only "
                 "defensive terms in the score - POA defense unmodeled"
                 + (f"; hustle season {hustle_season}" if hustle_season else
                    "; no hustle table")},
        {"rule": "position source", "checked": bool(pos_map),
         "note": f"position = mode of silver_boxscores "
                 f"({pos_season or 'missing'}) - may lag a role change"
                 if pos_map else "silver_boxscores position unavailable"},
        {"rule": "acquisition cost", "checked": True,
         "note": "cost_band is salary share only - outgoing matching and "
                 "apron legality are get_trade_legality's job; draft "
                 "compensation not modeled"},
        {"rule": "salary vintage", "checked": True,
         "note": "salaries from the latest silver_salaries sheet; "
                 "production season may lag - production_team marks "
                 "moved players"},
    ]
    out = {"tool": "get_trade_targets", "ok": True,
            "rows": rows,
            "need": str(need or ""),
            "acquiring_team": acquirer or None,
            "cohort": {"evaluated": len(cap),
                       "eligible": len(rows),
                       "skipped": skipped},
            "checks": checks,
            "salary_date": salary_date,
            "meta": {"source": source, "season": season,
                     "position_season": pos_season,
                     "hustle_season": hustle_season,
                     "formula": "target_score = PTS + 1.2REB + 1.5AST + "
                                "2STL + 2BLK - 1.5TOV per game",
                     "weights": _PROD_WEIGHTS,
                     "missing_columns_zero_weight": missing,
                     "cap": CAP["cap"],
                     "disclaimer": "Screening list only - deterministic "
                     "cohort + production ranking inputs. Fit and "
                     "acquisition cost beyond salary share are the "
                     "analyst's call."}}
    return declare_money(out, ["salary"])


_COLUMNS = ["player", "team", "position", "age", "salary", "cap_share",
            "cost_band", "contract_type", "gp", "mpg", "target_score",
            "value_per_m", "def_rating", "net_rating", "ts_pct",
            "rapm", "target_rank"]
