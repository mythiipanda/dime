import re
from typing import Any

from langchain_core.tools import tool

from .._core import InvalidSeasonError, resolve_season
from ._helpers import _owned_connection, _warehouse_tables, declare_money

_TABLE = "silver_hist_salaries"
_CAP_TABLE = "silver_cap_history"


def _err(msg: str) -> dict[str, Any]:
    return {"tool": "get_salary_history", "ok": False, "rows": [],
            "columns": [], "error": msg}


def _norm_season(season: str) -> str:
    s = str(resolve_season(season) or "").strip()
    if re.fullmatch(r"(19|20)\d\d", s):
        return f"{int(s) - 1}-{s[2:]}"
    m = re.fullmatch(r"((?:19|20)\d\d)-(\d\d)", s)
    if m and int(m.group(2)) == (int(m.group(1)) + 1) % 100:
        return s
    raise InvalidSeasonError(
        f"could not match {s!r} to a season (use 2003-04 or 2004)")


def _cap_row(con, end_year: int) -> dict:
    if _CAP_TABLE not in _warehouse_tables(con):
        return {}
    rows = con.execute(
        f"SELECT season_label, salary_cap, luxury_tax, apron_1, apron_2 "
        f"FROM {_CAP_TABLE} WHERE season = ?", [end_year]).fetchall()
    if not rows:
        return {}
    r = rows[0]
    return {"cap_season": r[0], "salary_cap": r[1], "luxury_tax": r[2],
            "apron_1": r[3], "apron_2": r[4]}


def _cap_fields(r: dict) -> dict:
    out = dict(r)
    cap = r.get("salary_cap")
    if cap:
        out["share_of_cap"] = round(float(r["salary"]) / float(cap), 4)
    return out


@tool(description='Historical player salaries (1984-85 through 2020-21) with league salary-cap, luxury-tax and apron context. One of: a player name (career salary by season), a team abbreviation plus a season (payroll vs cap, ranked in the league), or a season alone (cap figures plus the top individual salaries). For current contracts and cap sheets use get_cap_ledger or get_cap_table; for contract efficiency use get_contract_value or get_value_contracts. REACH FOR THIS for any salary-before-2022 or cap-history ask: "what did LeBron earn in 2016?", "how did GSW payroll rank in 2019?", "what was the 2017 cap?"')
def get_salary_history(
    player: str = "", team: str = "", season: str = "", top: int = 10,
) -> dict[str, Any]:
    player = (player or "").strip()
    team = (team or "").strip().upper()
    season = (season or "").strip()
    if player and team:
        return _err("pass a player OR a team, not both")
    with _owned_connection(None) as con:
        if _TABLE not in _warehouse_tables(con):
            return _err("salary history is not seeded in this warehouse")
        try:
            money = ["salary", "salary_cap", "min_salary", "median_salary",
                     "max_salary", "total_salary", "luxury_tax", "apron_1",
                     "apron_2", "payroll", "cap_room", "room_under_cap"]
            if player:
                return declare_money(_player_mode(con, player, season), money)
            if team:
                if not season:
                    return _err("team payroll mode needs a season")
                return declare_money(_team_mode(con, team, _norm_season(season), top), money)
            if season:
                return declare_money(_league_mode(con, _norm_season(season), top), money)
            return declare_money(_cap_table_mode(con), money)
        except InvalidSeasonError as exc:
            return _err(str(exc))


def _player_mode(con, player: str, season: str) -> dict[str, Any]:
    try:
        where = "WHERE lower(PLAYER_NAME) LIKE lower(?)"
        params = [f"%{player}%"]
        if season:
            where += " AND SEASON = ?"
            params.append(_norm_season(season))
        rows = con.execute(
            f"SELECT PLAYER_NAME, SEASON, TEAM_ABBREVIATION, SALARY, "
            f"SEASON_YEAR FROM {_TABLE} {where} ORDER BY SEASON_YEAR, "
            f"SALARY DESC LIMIT 200", params).fetchall()
    except Exception as exc:
        return _err(f"salary query failed: {exc}")
    if not rows:
        return _err(f"no salary rows for '{player}'"
                    + (f" in {season}" if season else ""))
    if len({r[0] for r in rows}) > 1:
        names = sorted({r[0] for r in rows})[:8]
        return _err(f"'{player}' matched several players "
                    f"({', '.join(names)}); use an exact name")
    out_rows = []
    for name, szn, tm, sal, yr in rows:
        out_rows.append(_cap_fields({
            "PLAYER_NAME": name, "SEASON": szn, "TEAM": tm,
            "salary": sal, **_cap_row(con, yr + 1)}))
    return {"tool": "get_salary_history", "ok": True, "rows": out_rows,
            "columns": ["PLAYER_NAME", "SEASON", "TEAM", "salary",
                        "cap_season", "salary_cap", "luxury_tax",
                        "apron_1", "apron_2", "share_of_cap"],
            "meta": {"source": "silver_hist_salaries+silver_cap_history",
                     "coverage": "1984-85 through 2020-21"}}


def _team_mode(con, team: str, season: str, top: int) -> dict[str, Any]:
    yr = int(season[:4])
    try:
        rows = con.execute(
            f"SELECT PLAYER_NAME, TEAM_ABBREVIATION, SALARY FROM {_TABLE} "
            f"WHERE SEASON = ? AND TEAM_ABBREVIATION = ? "
            f"ORDER BY SALARY DESC", [season, team]).fetchall()
        payrolls = con.execute(
            f"SELECT TEAM_ABBREVIATION, SUM(SALARY) FROM {_TABLE} "
            f"WHERE SEASON = ? GROUP BY TEAM_ABBREVIATION "
            f"ORDER BY 2 DESC", [season]).fetchall()
    except Exception as exc:
        return _err(f"payroll query failed: {exc}")
    if not rows:
        return _err(f"no salary rows for {team} in {season}")
    payroll = sum(int(r[2] or 0) for r in rows)
    rank = next((i + 1 for i, (t, _) in enumerate(payrolls) if t == team),
                None)
    cap = _cap_row(con, yr + 1)
    summary = {"team": team, "season": season, "payroll": payroll,
               "payroll_rank": rank, "teams_ranked": len(payrolls), **cap}
    if cap.get("salary_cap"):
        summary["payroll_vs_cap"] = round(float(payroll) / cap["salary_cap"], 4)
        summary["room_under_cap"] = int(cap["salary_cap"] - payroll)
    if cap.get("luxury_tax"):
        summary["over_tax"] = payroll > cap["luxury_tax"]
    for k in ("apron_1", "apron_2"):
        if cap.get(k):
            summary[f"over_{k}"] = payroll > cap[k]
    return {"tool": "get_salary_history", "ok": True,
            "rows": [{"PLAYER_NAME": r[0], "TEAM": r[1], "salary": r[2]}
                     for r in rows[:max(1, int(top))]],
            "columns": ["PLAYER_NAME", "TEAM", "salary"],
            "summary": summary,
            "meta": {"source": "silver_hist_salaries+silver_cap_history",
                     "coverage": "1984-85 through 2020-21"}}


def _league_mode(con, season: str, top: int) -> dict[str, Any]:
    yr = int(season[:4])
    try:
        rows = con.execute(
            f"SELECT PLAYER_NAME, TEAM_ABBREVIATION, SALARY FROM {_TABLE} "
            f"WHERE SEASON = ? ORDER BY SALARY DESC LIMIT ?",
            [season, max(1, int(top))]).fetchall()
        agg = con.execute(
            f"SELECT COUNT(DISTINCT PLAYER_NAME), MIN(SALARY), "
            f"MEDIAN(SALARY), MAX(SALARY), SUM(SALARY) FROM {_TABLE} "
            f"WHERE SEASON = ?", [season]).fetchone()
    except Exception as exc:
        return _err(f"salary query failed: {exc}")
    if not rows:
        return _err(f"no salary rows for {season}")
    cap = _cap_row(con, yr + 1)
    summary = {"season": season, "players": agg[0], "min_salary": agg[1],
               "median_salary": agg[2], "max_salary": agg[3],
               "total_salary": agg[4], **cap}
    return {"tool": "get_salary_history", "ok": True,
            "rows": [_cap_fields({"PLAYER_NAME": r[0], "TEAM": r[1],
                                  "salary": r[2], **cap}) for r in rows],
            "columns": ["PLAYER_NAME", "TEAM", "salary", "salary_cap",
                        "share_of_cap"],
            "summary": summary,
            "meta": {"source": "silver_hist_salaries+silver_cap_history",
                     "coverage": "1984-85 through 2020-21"}}


def _cap_table_mode(con) -> dict[str, Any]:
    if _CAP_TABLE not in _warehouse_tables(con):
        return _err("cap history is not seeded in this warehouse")
    rows = con.execute(
        f"SELECT season_label, salary_cap, luxury_tax, apron_1, apron_2 "
        f"FROM {_CAP_TABLE} ORDER BY season").fetchall()
    if not rows:
        return _err("cap history is not seeded in this warehouse")
    return {"tool": "get_salary_history", "ok": True,
            "rows": [{"season": r[0], "salary_cap": r[1],
                      "luxury_tax": r[2], "apron_1": r[3], "apron_2": r[4]}
                     for r in rows],
            "columns": ["season", "salary_cap", "luxury_tax", "apron_1",
                        "apron_2"],
            "meta": {"source": "silver_cap_history",
                     "coverage": "1984-85 through 2025-26"}}
