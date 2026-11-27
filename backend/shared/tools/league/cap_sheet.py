import re as _re
from typing import Any

from ..cap_rules import (
    CAP,
    CAP_GROWTH_ASSUMPTION,
    apron_state,
    cba_restrictions,
    matching_band,
    roster_issues,
    scenario_trace,
    used_expanded_matching,
)
from ..cap_sheet import unroll_team_sheet
from ._helpers import _pkg
from .cba_cap import (
    _locate_player_team,
    _match_trade_players,
    _payroll,
    _payroll_source,
    _salary_date,
)

_SALARY_COL_RE = _re.compile(r"SALARY_(\d{4})_(\d{2})$")
_OPTION_COL_RE = _re.compile(r"OPTION_(\d{4})_(\d{2})$")


def _season_label(year: int, suffix: int) -> str:
    return f"{year}-{suffix:02d}"


def _salary_year_columns(con) -> list[tuple[str, str]]:
    cols = [r[1] for r in con.execute("PRAGMA table_info(silver_salaries)").fetchall()]
    out: list[tuple[str, str]] = []
    for col in cols:
        m = _SALARY_COL_RE.fullmatch(col)
        if m:
            out.append((_season_label(int(m.group(1)), int(m.group(2))), col))
    return sorted(out)


def _player_contract_tail(con, player: str, team: str, season: str) -> dict[str, Any] | None:
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "silver_salaries" not in tables:
        return None
    year_cols = [pair for pair in _salary_year_columns(con) if pair[0] >= season]
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
    remaining = [a for a in amounts if a > 0]
    return {"guaranteed": float(data.get("GUARANTEED") or 0),
            "season_salary": float(amounts[0] or 0) if amounts else 0.0,
            "years_remaining": len(remaining)}



def cap_lines_for_season(con, season: str) -> tuple[dict[str, Any], bool]:
    if season == "2026-27":
        return dict(CAP), False
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    except Exception:
        tables = set()
    base = dict(CAP)
    base_year = 2026
    if "silver_cap_room" in tables:
        try:
            rows = con.execute(
                "SELECT CAP_SEASON, PROJECTED_CAP, PROJECTED_TAX, PROJECTED_APRON1, PROJECTED_APRON2 "
                "FROM silver_cap_room").fetchall()
            by_season = {str(r[0]): r for r in rows if r and r[0]}
            if season in by_season:
                row = by_season[season]
                if row[1]:
                    return {"cap": int(row[1]), "tax": int(row[2] or 0),
                            "apron1": int(row[3] or 0), "apron2": int(row[4] or 0)}, False
            latest = sorted(by_season)
            if latest:
                anchor = by_season[latest[-1]]
                anchor_year = int(str(anchor[0])[:4])
                if anchor[1]:
                    base = {"cap": float(anchor[1]), "tax": float(anchor[2] or 0),
                            "apron1": float(anchor[3] or 0), "apron2": float(anchor[4] or 0)}
                    base_year = anchor_year
        except Exception:
            pass
    m = _re.match(r"(\d{4})", str(season or ""))
    want_year = int(m.group(1)) if m else base_year
    steps = max(0, want_year - base_year)
    factor = (1 + CAP_GROWTH_ASSUMPTION) ** steps
    return {k: int(round(v * factor)) for k, v in base.items()}, steps > 0


def cap_sheet_rows(con, team: str, season: str) -> dict[str, Any]:
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "silver_salaries" not in tables:
        return {"ok": False, "error": "silver_salaries not in warehouse"}
    try:
        cur = con.execute(
            "SELECT * FROM silver_salaries WHERE UPPER(TEAM) = UPPER(?)", [team])
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, r)) for r in cur.fetchall()]
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}
    if not rows:
        return {"ok": False, "error": f"no silver_salaries rows for {team}"}
    if "silver_cap_players" in tables:
        try:
            type_rows = con.execute(
                "SELECT player, contract_type FROM silver_cap_players "
                "WHERE UPPER(team) = UPPER(?) AND _season = (SELECT MAX(_season) FROM silver_cap_players)",
                [team]).fetchall()
            types = {str(r[0]).lower(): str(r[1] or "") for r in type_rows}
            for row in rows:
                hit = types.get(str(row.get("PLAYER_NAME") or "").lower())
                if hit:
                    row["contract_type"] = hit
        except Exception:
            pass
    sheet = unroll_team_sheet(rows, season)
    totals: dict[str, dict[str, Any]] = {}
    for label in sheet["seasons"]:
        base = sheet["totals"].get(label, {"committed": 0, "pending_option": 0})
        totals[label] = {"committed": base["committed"],
                         "pending_option": base["pending_option"],
                         "dead_money": 0, "cap_holds": 0,
                         "incomplete_roster_charges": 0}
    holds_note = "cap_holds and incomplete_roster_charges populate only when silver_cap_room covers the season"
    if "silver_cap_room" in tables:
        try:
            holds = con.execute(
                "SELECT CAP_SEASON, FA_HOLDS_EST, INCOMPLETE_ROSTER_CHARGES "
                "FROM silver_cap_room WHERE UPPER(TEAM) = UPPER(?)", [team]).fetchall()
            for r in holds:
                label = str(r[0])
                if label in totals:
                    totals[label]["cap_holds"] = int(r[1] or 0)
                    totals[label]["incomplete_roster_charges"] = int(r[2] or 0)
        except Exception:
            pass
    for label, entry in totals.items():
        entry["payroll"] = (entry["committed"] + entry["dead_money"]
                            + entry["cap_holds"] + entry["incomplete_roster_charges"])
    lines_by_season: dict[str, Any] = {}
    for label in totals:
        llines, lproj = cap_lines_for_season(con, label)
        lines_by_season[label] = {**llines, "projected": lproj}
    lines, projected = cap_lines_for_season(con, season)
    committed_now = totals.get(season, {}).get("payroll", 0)
    state = apron_state(int(committed_now), lines)
    state["room_under_apron2"] = state["room_apron2"]
    return {"ok": True, "team": str(team).upper(), "season": season,
            "lines": lines_by_season, "lines_projected": projected,
            "players": sheet["players"], "totals": totals,
            "state": state,
            "meta": {"holds_note": holds_note, "season_columns": sheet["seasons"],
                     "unrolling": "shared.tools.cap_sheet",
                     "source": _payroll_source(con), "salary_date": _salary_date(con),
                     "season": season}}


def evaluate_cap_scenario(con, payload: dict[str, Any]) -> dict[str, Any]:
    team = str(payload.get("team") or "").strip().upper()
    season = str(payload.get("season") or "").strip() or "2026-27"
    moves_in = payload.get("moves")
    if not team:
        return {"ok": False, "error": "team needed"}
    if not isinstance(moves_in, list) or not moves_in:
        return {"ok": False, "error": "moves must be a non-empty list"}
    lines, lines_projected = cap_lines_for_season(con, season)
    try:
        pay_before, roster = _payroll(team, con, season)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}
    errors: list[dict[str, str]] = []
    moves: list[dict[str, Any]] = []
    in_names: list[str] = []
    out_names: list[str] = []
    in_total = 0
    out_total = 0
    sign_count = 0
    roster_delta = 0
    for i, raw in enumerate(moves_in):
        if not isinstance(raw, dict):
            errors.append({"move": str(i), "error": "move must be an object"})
            continue
        kind = str(raw.get("kind") or "").strip()
        if kind == "signing":
            amount = raw.get("amount")
            if not isinstance(amount, (int, float)) or amount <= 0:
                errors.append({"move": str(i), "error": "signing needs a positive amount"})
                continue
            label = str(raw.get("label") or f"${amount / 1_000_000:g}M signing")
            moves.append({"kind": "signing", "detail": f"sign {label}",
                          "amount": int(amount)})
            sign_count += 1
            roster_delta += 1
        elif kind == "trade_out":
            player = str(raw.get("player") or "").strip()
            if not player:
                errors.append({"move": str(i), "error": "trade_out needs a player"})
                continue
            total, matched, unknown = _match_trade_players(team, player, con, season)
            if unknown or not matched:
                errors.append({"move": str(i),
                               "error": f"could not match {player} on {team}"})
                continue
            hit = next((p for p in roster if p["player"] == matched[0]), None)
            amount = int((hit or {}).get("salary") or 0)
            moves.append({"kind": "trade_out", "detail": f"out {matched[0]}",
                          "amount": amount})
            out_names.append(matched[0])
            out_total += amount
            roster_delta -= 1
        elif kind == "trade_in":
            player = str(raw.get("player") or "").strip()
            if not player:
                errors.append({"move": str(i), "error": "trade_in needs a player"})
                continue
            found = _locate_player_team(player, con, season)
            if found is None:
                errors.append({"move": str(i), "error": f"could not locate {player}"})
                continue
            cname, cteam, csal = found
            if str(cteam).upper() == team:
                errors.append({"move": str(i),
                               "error": f"{cname} is already on {team}"})
                continue
            salary = int(csal or 0)
            moves.append({"kind": "trade_in",
                          "detail": f"in {cname} (from {cteam})", "amount": salary})
            in_names.append(cname)
            in_total += salary
            roster_delta += 1
        elif kind == "waive":
            player = str(raw.get("player") or "").strip()
            stretch = bool(raw.get("stretch"))
            total, matched, unknown = _match_trade_players(team, player, con, season)
            if unknown or not matched:
                errors.append({"move": str(i),
                               "error": f"could not match {player} on {team}"})
                continue
            hit = next((p for p in roster if p["player"] == matched[0]), None)
            amount = int((hit or {}).get("salary") or 0)
            tail = _player_contract_tail(con, matched[0], team, season)
            guaranteed = float((tail or {}).get("guaranteed") or amount)
            if stretch:
                years = max(1, int((tail or {}).get("years_remaining") or 1))
                spread = int(round(guaranteed / (2 * years + 1)))
                relief = amount - spread
                detail = f"waive {matched[0]} (stretched over {2 * years + 1}y)"
                moves.append({"kind": "trade_out", "detail": detail,
                              "amount": max(0, relief)})
            else:
                relief = max(0, int(round(amount - guaranteed)))
                detail = f"waive {matched[0]} (dead money stays)"
                moves.append({"kind": "trade_out", "detail": detail,
                              "amount": relief})
            roster_delta -= 1
        elif kind == "option_decision":
            player = str(raw.get("player") or "").strip()
            exercise = bool(raw.get("exercise", True))
            if exercise:
                continue
            total, matched, unknown = _match_trade_players(team, player, con, season)
            if unknown or not matched:
                errors.append({"move": str(i),
                               "error": f"could not match {player} on {team}"})
                continue
            hit = next((p for p in roster if p["player"] == matched[0]), None)
            amount = int((hit or {}).get("salary") or 0)
            moves.append({"kind": "trade_out",
                          "detail": f"decline {matched[0]} option", "amount": amount})
            roster_delta -= 1
        else:
            errors.append({"move": str(i), "error": f"unknown move kind '{kind}'"})
    trace = scenario_trace(pay_before, moves, f"{team} committed payroll")
    pay_after = int(trace["pay_after"])
    state = apron_state(pay_after, lines)
    issues: list[str] = []
    matching: dict[str, Any] | None = None
    hard_cap = ""
    room_before = max(0, lines["cap"] - pay_before)
    if out_names and in_names:
        aggregates = len(out_names) > 1
        if used_expanded_matching(in_total, out_total, room_before):
            hard_cap = "first apron"
            if pay_after > lines["apron1"]:
                issues.append(f"{team} is hard-capped at the first apron by "
                              "expanded salary matching")
        if state["over_apron2"] and aggregates:
            issues.append("cannot aggregate salaries above the second apron")
            matching = {"incoming": in_total, "outgoing": out_total, "legal": False,
                        "match_rule": "no aggregation (above the second apron)",
                        "allowed_incoming": 0}
        else:
            band = matching_band(out_total, bool(state["over_apron1"]), room_before)
            matching = {"incoming": in_total, "outgoing": out_total,
                        "allowed_incoming": band["allowed_incoming"],
                        "match_rule": band["match_rule"],
                        "legal": in_total <= band["allowed_incoming"]}
            if not matching["legal"]:
                issues.append(f"{team} takes back too much "
                              f"(${in_total:,} vs {band['allowed_incoming']:,} "
                              f"allowed under {band['match_rule']})")
        if aggregates and pay_after > lines["apron2"]:
            issues.append("aggregation would hard-cap the team at the second apron")
    roster_after = len(roster) + roster_delta
    roster_issue_list = roster_issues(roster_after)
    issues.extend(roster_issue_list)
    state_with_room = {**state, "cap_room": lines["cap"] - pay_after}
    restrictions = cba_restrictions(state_with_room, season)
    state["room_under_apron2"] = state["room_apron2"]
    return {"ok": True, "team": team, "season": season,
            "steps": trace["steps"], "pay_after": pay_after,
            "pay_before": int(pay_before), "state": state,
            "lines": lines, "lines_projected": lines_projected,
            "restrictions": restrictions,
            "roster_before": len(roster), "roster_after": roster_after,
            "roster_issues": roster_issue_list,
            "hard_cap": hard_cap, "issues": issues, "errors": errors,
            "matching": matching,
            "meta": {"source": _payroll_source(con), "salary_date": _salary_date(con)}}
