from typing import Any

from langchain_core.tools import tool

from ...contracts import canonical_team_abbr
from ._helpers import _owned_connection, _pkg, declare_money
from .cba_cap import CAP, _payroll_source, _salary_date, _resolve_team_abbr
from .draft_contracts import _contract_norm
from .._core import season_rows_error, team_error_message

_CHEAP_CAP_SHARE = 0.10
_EXPENSIVE_CAP_SHARE = 0.20
_ROTATION_MIN_GP = 20
_ROTATION_MPG = 12.0
_BARGAIN_RATIO = 1.25
_OVERPAID_RATIO = 0.75
_PROD_WEIGHTS = {"PTS": 1.0, "REB": 1.2, "AST": 1.5,
                 "STL": 2.0, "BLK": 2.0, "TOV": -1.5}


def _value_score(row: dict, use_w: dict[str, float]) -> float:
    return round(sum(float(row.get(c) or 0) * w
                     for c, w in use_w.items()), 2)


def _prod_rows(con, season: str) -> tuple[list[dict], set[str], str | None]:
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "silver_leaders_pts" not in tables:
        return [], set(), "silver_leaders_pts missing - no production source"
    cols = {r[1] for r in con.execute(
        "PRAGMA table_info(silver_leaders_pts)").fetchall()}
    need = ["PLAYER", "TEAM", "GP", "MIN"] + list(_PROD_WEIGHTS)
    have = {c for c in need if c in cols}
    pick = [c for c in need if c in have]
    rows = [dict(zip(pick, tup)) for tup in con.execute(
        f"SELECT {', '.join(pick)} FROM silver_leaders_pts "
        "WHERE _season = ?", [season]).fetchall()]
    return rows, have, None


def _cap_band(cap_share: float) -> str:
    if cap_share < _CHEAP_CAP_SHARE:
        return "cheap"
    if cap_share > _EXPENSIVE_CAP_SHARE:
        return "expensive"
    return "mid"


def _team_rows(team: str, prod: list[dict], cap: list[dict],
               have: set[str], use_w: dict[str, float]) -> list[dict]:
    team = canonical_team_abbr(team)
    prod_by_name: dict[str, dict] = {}
    for r in prod:
        prod_by_name.setdefault(_contract_norm(r.get("PLAYER")), r)
    out: list[dict] = []
    for c in cap:
        name = str(c.get("PLAYER_NAME") or "")
        salary = int(c.get("salary") or 0)
        p = prod_by_name.get(_contract_norm(name))
        gp = int(p.get("GP") or 0) if p else 0
        mins = float(p.get("MIN") or 0) if p else 0.0
        mpg = round(mins / gp, 1) if gp and mins else 0.0
        rotation = gp >= _ROTATION_MIN_GP and mpg >= _ROTATION_MPG
        score = _value_score(p, use_w) if p else None
        cap_share = round(salary / CAP["cap"], 4)
        vpd = round(score / (salary / 1_000_000), 3) \
            if score is not None and salary > 0 else None
        row = {"player": name, "team": team,
               "salary": salary, "cap_share": cap_share,
               "cap_band": _cap_band(cap_share),
               "gp": gp, "mpg": mpg, "rotation": rotation,
               "value_score": score, "value_per_m": vpd}
        production_team = canonical_team_abbr(p.get("TEAM")) if p else ""
        if p and production_team != team:
            row["production_team"] = production_team
        if p is None:
            row["no_production"] = True
        out.append(row)
    qualified = [r["value_per_m"] for r in out if r["value_per_m"] is not None]
    median = sorted(qualified)[len(qualified) // 2] if qualified else None
    for r in out:
        v = r["value_per_m"]
        if v is None or median is None or not r["rotation"]:
            r["value_flag"] = "unqualified"
        elif v >= median * _BARGAIN_RATIO:
            r["value_flag"] = "bargain"
        elif v <= median * _OVERPAID_RATIO:
            r["value_flag"] = "overpaid"
        else:
            r["value_flag"] = "neutral"
    out.sort(key=lambda r: (-1 if r["value_per_m"] is None
                            else -r["value_per_m"]))
    for i, r in enumerate(out, 1):
        r["value_rank"] = i if r["value_per_m"] is not None else None
    return out


def _summary(rows: list[dict]) -> dict[str, Any]:
    rot = [r for r in rows if r["rotation"]]
    rot_salary = sum(r["salary"] for r in rot)
    cheap = sum(r["salary"] for r in rot if r["cap_band"] == "cheap")
    vpd = sorted(r["value_per_m"] for r in rot
                 if r["value_per_m"] is not None)
    return {"rotation_players": len(rot),
            "rotation_salary": rot_salary,
            "cheap_rotation_salary": cheap,
            "cheap_rotation_share": round(cheap / rot_salary, 4)
            if rot_salary else None,
            "median_value_per_m": vpd[len(vpd) // 2] if vpd else None,
            "bargains": sum(1 for r in rot if r["value_flag"] == "bargain"),
            "overpaid": sum(1 for r in rot if r["value_flag"] == "overpaid")}


@tool(description="Value-contract depth audit. Ranks rosters by "
    "production per cap dollar: salary, cap share, pinned value score "
    "(PTS + 1.2REB + 1.5AST + 2STL + 2BLK - 1.5TOV per game), value per $1M, "
    "and cheap/expensive depth flags (Presti rule: rotation players under "
    "~10% of cap). Omit 'team' for the league-wide audit in ONE call - "
    "never fan this tool out team by team to locate a player or compare "
    "across teams. 'benchmark_team' adds the same audit for a comparison "
    "roster plus summary deltas.")
def get_value_contracts(team: str = "", season: str | None = None,
                        benchmark_team: str = "") -> dict[str, Any]:
    raw_team = str(team or "").strip()
    team = (_resolve_team_abbr(canonical_team_abbr(raw_team)) or "").upper()
    if not team and raw_team:
        return {"tool": "get_value_contracts", "ok": False,
                "error": team_error_message(raw_team)}
    raw_bench = str(benchmark_team or "").strip()
    bench = (_resolve_team_abbr(canonical_team_abbr(raw_bench)) or "").upper() \
        if raw_bench else ""
    with _owned_connection(None, read_only=True) as con:
        if not season:
            try:
                season = con.execute(
                    "SELECT MAX(_season) FROM silver_leaders_pts").fetchone()[0]
            except Exception:
                season = _pkg().resolve_season(None)
        season = str(season)
        prod, have, err = _prod_rows(con, season)
        if err:
            return {"tool": "get_value_contracts", "ok": False,
                    "error": err}
        if not prod:
            return {"tool": "get_value_contracts", "ok": False,
                    "error": season_rows_error(con, "silver_leaders_pts",
                                               season)}
        from shared.contracts import salary_records
        wanted = ({team, bench} - {""}) if team else set()
        cap = [r for r in salary_records(con)
               if not wanted or canonical_team_abbr(r.get("TEAM")) in wanted]
        if team and not any(canonical_team_abbr(r.get("TEAM")) == team
                            for r in cap):
            return {"tool": "get_value_contracts", "ok": False,
                    "error": season_rows_error(con, "silver_salaries",
                                               season, team)}
        salary_date = _salary_date(con)
        source = _payroll_source(con)
    missing = [c for c in _PROD_WEIGHTS if c not in have]
    use_w = {c: (0.0 if c in missing else w)
             for c, w in _PROD_WEIGHTS.items()}
    if team:
        rows = _team_rows(team, prod, [c for c in cap
                                       if canonical_team_abbr(c.get("TEAM")) == team],
                          have, use_w)
    else:
        rows = []
        for t in sorted({canonical_team_abbr(c.get("TEAM")) for c in cap
                         if str(c.get("TEAM") or "").strip()}):
            rows.extend(_team_rows(t, prod, [c for c in cap
                                             if canonical_team_abbr(c.get("TEAM")) == t],
                                   have, use_w))
    checks = [
        {"rule": "value proxy", "checked": True,
         "note": "score = PTS + 1.2REB + 1.5AST + 2STL + 2BLK - 1.5TOV "
                 "on per-game rates - a proxy, not an impact metric"
                 + (f"; missing columns zero-weighted: {missing}"
                    if missing else "")},
        {"rule": "rotation role", "checked": True,
         "note": f"GP>={_ROTATION_MIN_GP} and MPG>={_ROTATION_MPG} proxy; "
                 "silver_stints stint-share not seeded in this warehouse"},
        {"rule": "depth bands", "checked": True,
         "note": f"cheap <{int(_CHEAP_CAP_SHARE * 100)}% of cap, "
                 f"expensive >{int(_EXPENSIVE_CAP_SHARE * 100)}% of cap; "
                 f"bargain/overpaid vs team median value-per-$1M at "
                 f"{_BARGAIN_RATIO}x/{_OVERPAID_RATIO}x"},
        {"rule": "salary vintage", "checked": True,
         "note": "salaries from the latest silver_salaries sheet; "
                 "production season may lag the salary sheet - "
                 "production_team marks moved players"},
    ]
    out = {"tool": "get_value_contracts", "ok": True,
           "rows": rows, "summary": _summary(rows),
           "checks": checks, "salary_date": salary_date,
           "meta": {"source": source, "season": season,
                    "scope": team or "league-wide",
                    "salary_date": salary_date,
                    "formula": "score = PTS + 1.2REB + 1.5AST + 2STL + "
                               "2BLK - 1.5TOV per game; value_per_m = "
                               "score / salary_millions",
                    "weights": _PROD_WEIGHTS,
                    "missing_columns_zero_weight": missing,
                    "cap": CAP["cap"],
                    "disclaimer": "Value proxy only - box-score production "
                    "per dollar, not impact-adjusted. Use for depth "
                    "screening, not a verdict on a player."}}
    if bench:
        brows = _team_rows(bench, prod,
                           [c for c in cap
                            if canonical_team_abbr(c.get("TEAM")) == bench],
                           have, use_w)
        if not brows:
            out["benchmark"] = {"team": bench,
                                "error": f"no salary rows for {bench}"}
        else:
            out["benchmark"] = {"team": bench, "rows": brows,
                                "summary": _summary(brows)}
            a, b = out["summary"], out["benchmark"]["summary"]
            out["comparison"] = {
                "cheap_rotation_share_delta":
                    (a["cheap_rotation_share"] or 0)
                    - (b["cheap_rotation_share"] or 0),
                "median_value_per_m_delta":
                    (a["median_value_per_m"] or 0)
                    - (b["median_value_per_m"] or 0),
                "bargain_count_delta":
                    a["bargains"] - b["bargains"]}
    return declare_money(out, ["salary"])
