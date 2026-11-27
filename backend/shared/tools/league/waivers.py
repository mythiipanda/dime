import re as _re
from datetime import date as _date, datetime as _dt
from typing import Any

WAIVER_BASIS = (
    "waiver dead money uses the remaining guaranteed pool in salary-sheet year order; "
    "per-year guarantee allocations are unavailable and stretch years count listed "
    "salaried seasons including player-option years while excluding team-option years"
)

_SALARY_COL_RE = _re.compile(r"SALARY_(\d{4})_(\d{2})$")
_SEASON_RE = _re.compile(r"^(\d{4})-(\d{2})$")


def salary_year_columns(con) -> list[tuple[str, str]]:
    cols = [r[1] for r in con.execute("PRAGMA table_info(silver_salaries)").fetchall()]
    out: list[tuple[str, str]] = []
    for col in cols:
        match = _SALARY_COL_RE.fullmatch(col)
        if match:
            out.append((f"{int(match.group(1))}-{int(match.group(2)):02d}", col))
    return sorted(out)


def _parse_waiver_date(text: str) -> _date | None:
    if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return _dt.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def resolve_waiver_timing(raw: object, season: str) -> tuple[dict[str, Any] | None, str | None]:
    text = str(raw or "").strip()
    if not text:
        return {"window": "pre_sep1", "date": None, "defaulted": True}, None
    parsed = _parse_waiver_date(text)
    if parsed is None:
        return None, "waiver_date must be YYYY-MM-DD"
    match = _SEASON_RE.fullmatch(str(season or ""))
    if match:
        start_year = int(match.group(1))
        start = _date(start_year, 7, 1)
        end = _date(start_year + 1, 6, 30)
        if not start <= parsed <= end:
            return None, (f"waiver_date must fall inside the {season} league year "
                          f"({start.isoformat()} through {end.isoformat()})")
    window = "pre_sep1" if parsed.month in (7, 8) else "post_sep1"
    return {"window": window, "date": parsed.isoformat(), "defaulted": False}, None


def player_contract_tail(con, player: str, team: str, season: str) -> dict[str, Any] | None:
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "silver_salaries" not in tables:
        return None
    table_cols = {r[1] for r in con.execute("PRAGMA table_info(silver_salaries)").fetchall()}
    year_cols = [pair for pair in salary_year_columns(con) if pair[0] >= season]
    if not year_cols:
        return None
    option_cols = {
        label: "OPTION_" + label.replace("-", "_")
        for label, _ in year_cols
        if "OPTION_" + label.replace("-", "_") in table_cols
    }
    guaranteed_select = "GUARANTEED" if "GUARANTEED" in table_cols else "NULL AS GUARANTEED"
    select_cols = ", ".join(
        [guaranteed_select]
        + [col for _, col in year_cols]
        + list(option_cols.values())
    )
    sql = ("SELECT " + select_cols +
           " FROM silver_salaries WHERE UPPER(TEAM) = UPPER(?) "
           "AND LOWER(PLAYER_NAME) = LOWER(?) LIMIT 1")
    try:
        cur = con.execute(sql, [team, player])
        names = [d[0] for d in cur.description]
        row = cur.fetchone()
    except Exception:
        return None
    if not row:
        return None
    data = dict(zip(names, row))
    seasons: list[dict[str, Any]] = []
    for label, col in year_cols:
        amount = float(data.get(col) or 0)
        option = str(data.get(option_cols.get(label, "")) or "").strip().lower()
        seasons.append({
            "season": label,
            "salary": amount,
            "option": option or None,
            "counted": amount > 0 and option != "team",
        })
    counted = [entry for entry in seasons if entry["counted"]]
    guaranteed = data.get("GUARANTEED")
    return {
        "guaranteed": None if guaranteed is None else float(guaranteed),
        "season_salary": float(seasons[0]["salary"] or 0) if seasons else 0.0,
        "years_remaining": len(counted),
        "future_years_remaining": len([entry for entry in counted if entry["season"] > season]),
        "team_option_seasons": [entry["season"] for entry in seasons
                                if entry["salary"] > 0 and entry["option"] == "team"],
    }


def waiver_dead_money(salary: int | float, guaranteed: int | float | None,
                      years_remaining: int | None, stretch: bool = False,
                      future_years_remaining: int | None = None,
                      waiver_window: str = "pre_sep1") -> dict[str, Any]:
    salary_amount = max(0, int(round(float(salary or 0))))
    guaranteed_amount = float(salary_amount if guaranteed is None else max(0.0, float(guaranteed)))
    post_september = stretch and waiver_window == "post_sep1"
    years = max(1, int(years_remaining or 1))
    if post_september:
        future_years = max(0, int(future_years_remaining
                                  if future_years_remaining is not None else years - 1))
        stretch_years = 2 * future_years + 1
        current_allocation = min(float(salary_amount), guaranteed_amount)
        stretch_pool = max(0.0, guaranteed_amount - current_allocation)
        installment = stretch_pool / stretch_years
        dead_cap = int(round(current_allocation))
    elif stretch:
        stretch_years = 2 * years + 1
        stretch_pool = guaranteed_amount
        installment = stretch_pool / stretch_years
        dead_cap = min(salary_amount, int(round(installment)))
    else:
        stretch_years = 0
        stretch_pool = 0.0
        installment = 0.0
        dead_cap = min(salary_amount, int(round(guaranteed_amount)))
    return {
        "dead_cap": dead_cap,
        "relief": salary_amount - dead_cap,
        "guaranteed": int(round(guaranteed_amount)),
        "stretch_years": stretch_years,
        "stretch": bool(stretch),
        "stretched_amount": int(round(stretch_pool)),
        "stretched_dead_cap": int(round(installment)),
        "waiver_window": waiver_window,
    }


def waiver_move(con, team: str, player: str, salary: int, season: str,
                stretch: bool = False, tail: dict[str, Any] | None = None,
                timing: dict[str, Any] | None = None) -> dict[str, Any]:
    if tail is None:
        tail = player_contract_tail(con, player, team, season)
    timing = timing or {"window": "pre_sep1", "date": None, "defaulted": True}
    window = str(timing.get("window") or "pre_sep1")
    amounts = waiver_dead_money(
        salary,
        (tail or {}).get("guaranteed"),
        (tail or {}).get("years_remaining"),
        stretch,
        (tail or {}).get("future_years_remaining"),
        window,
    )
    dead_cap = int(amounts["dead_cap"])
    if stretch and window == "post_sep1":
        detail = (f"waive {player} (post-Sep-1 stretch estimate; ${dead_cap:,} "
                  f"current dead cap; ${amounts['stretched_dead_cap']:,}/yr "
                  f"future installments over {amounts['stretch_years']}y)")
        estimate_basis = (f"post-Sep-1 stretch: current-season allocation unchanged; "
                          f"${amounts['stretched_amount']:,} future guaranteed pool "
                          f"over {amounts['stretch_years']}y; player-option years count, "
                          f"team-option years excluded")
    elif stretch:
        detail = (f"waive {player} (pre-Sep-1 stretch estimate over "
                  f"{amounts['stretch_years']}y; ${dead_cap:,} dead cap)")
        timing_label = ("default pre-Sep-1 timing" if timing.get("defaulted")
                        else "pre-Sep-1 timing")
        estimate_basis = (f"{timing_label}: ${amounts['stretched_amount']:,} "
                          f"remaining guaranteed pool over {amounts['stretch_years']}y; "
                          f"player-option years count, team-option years excluded")
    else:
        detail = f"waive {player} (${dead_cap:,} estimated dead cap stays)"
        estimate_basis = ("estimated dead cap uses the remaining guaranteed pool in "
                          "salary-sheet year order; per-year allocations unavailable")
    return {
        "kind": "waive",
        "player": player,
        "detail": detail,
        "amount": int(amounts["relief"]),
        "dead_cap": dead_cap,
        "guaranteed": int(amounts["guaranteed"]),
        "stretch_years": int(amounts["stretch_years"]),
        "stretched_amount": int(amounts["stretched_amount"]),
        "stretched_dead_cap": int(amounts["stretched_dead_cap"]),
        "waiver_window": window,
        "waiver_date": timing.get("date"),
        "waiver_date_defaulted": bool(timing.get("defaulted")),
        "estimate_basis": estimate_basis,
    }
