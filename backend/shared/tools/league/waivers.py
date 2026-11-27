import re as _re
from typing import Any

WAIVER_BASIS = (
    "waiver dead money uses the remaining guaranteed pool in salary-sheet year order; "
    "per-year guarantee allocations are unavailable and stretch years count listed "
    "salaried seasons"
)

_SALARY_COL_RE = _re.compile(r"SALARY_(\d{4})_(\d{2})$")


def salary_year_columns(con) -> list[tuple[str, str]]:
    cols = [r[1] for r in con.execute("PRAGMA table_info(silver_salaries)").fetchall()]
    out: list[tuple[str, str]] = []
    for col in cols:
        match = _SALARY_COL_RE.fullmatch(col)
        if match:
            out.append((f"{int(match.group(1))}-{int(match.group(2)):02d}", col))
    return sorted(out)


def player_contract_tail(con, player: str, team: str, season: str) -> dict[str, Any] | None:
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "silver_salaries" not in tables:
        return None
    year_cols = [pair for pair in salary_year_columns(con) if pair[0] >= season]
    if not year_cols:
        return None
    select_cols = ", ".join(c for _, c in year_cols)
    sql = ("SELECT GUARANTEED, " + select_cols +
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
    amounts = [float(data.get(col) or 0) for _, col in year_cols]
    remaining = [amount for amount in amounts if amount > 0]
    guaranteed = data.get("GUARANTEED")
    return {
        "guaranteed": None if guaranteed is None else float(guaranteed),
        "season_salary": float(amounts[0] or 0) if amounts else 0.0,
        "years_remaining": len(remaining),
    }


def waiver_dead_money(salary: int | float, guaranteed: int | float | None,
                      years_remaining: int | None, stretch: bool = False) -> dict[str, int | bool]:
    salary_amount = max(0, int(round(float(salary or 0))))
    guaranteed_amount = float(salary_amount if guaranteed is None else max(0.0, float(guaranteed)))
    years = max(1, int(years_remaining or 1))
    stretch_years = 2 * years + 1 if stretch else 0
    raw_dead = guaranteed_amount / stretch_years if stretch else guaranteed_amount
    dead_cap = min(salary_amount, int(round(raw_dead)))
    return {
        "dead_cap": dead_cap,
        "relief": salary_amount - dead_cap,
        "guaranteed": int(round(guaranteed_amount)),
        "stretch_years": stretch_years,
        "stretch": bool(stretch),
    }


def waiver_move(con, team: str, player: str, salary: int, season: str,
                stretch: bool = False, tail: dict[str, Any] | None = None) -> dict[str, Any]:
    if tail is None:
        tail = player_contract_tail(con, player, team, season)
    amounts = waiver_dead_money(
        salary,
        (tail or {}).get("guaranteed"),
        (tail or {}).get("years_remaining"),
        stretch,
    )
    dead_cap = int(amounts["dead_cap"])
    if stretch:
        detail = (f"waive {player} (pre-Sep-1 stretch estimate over "
                  f"{amounts['stretch_years']}y; ${dead_cap:,} dead cap)")
    else:
        detail = f"waive {player} (${dead_cap:,} estimated dead cap stays)"
    return {
        "kind": "waive",
        "detail": detail,
        "amount": int(amounts["relief"]),
        "dead_cap": dead_cap,
        "guaranteed": int(amounts["guaranteed"]),
    }
