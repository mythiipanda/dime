import re as _re
from typing import Any

from ..cap_rules import (
    CAP,
    CAP_GROWTH_ASSUMPTION,
    apron_state,
    cba_restrictions,
    matching_band,
    matching_election,
    operative_match_rule,
    payroll_proxy_meta,
    roster_issues,
    scenario_trace,
    used_expanded_matching,
)
from ..cap_sheet import option_column, season_column, unroll_team_sheet
from ...contracts import normalize_name
from .cap_hold_derivation import derive_cap_holds, hold_amount
from .cba_cap import (
    _locate_player_team,
    _match_trade_players,
    _payroll,
    _payroll_source,
    _salary_date,
)
from .waivers import WAIVER_BASIS, resolve_waiver_timing, waiver_move

_SEASON_LABEL_RE = _re.compile(r"\d{4}-\d{2}")


def _valid_season_label(season: str) -> bool:
    return bool(_SEASON_LABEL_RE.fullmatch(str(season or "")))


def _option_only_moves(moves_in: list[Any]) -> bool:
    return all(isinstance(raw, dict) and str(raw.get("kind") or "") == "option_decision"
               for raw in moves_in)


def _scenario_season(requested: str, moves_in: list[Any]) -> tuple[str, dict[int, str]]:
    entries: list[tuple[int, str]] = []
    rejected: dict[int, str] = {}
    implicit_requested = False
    for i, raw in enumerate(moves_in):
        if not isinstance(raw, dict) or str(raw.get("kind") or "") != "option_decision":
            continue
        move_season = str(raw.get("season") or "").strip()
        if not move_season:
            implicit_requested = True
            continue
        if not _valid_season_label(move_season):
            rejected[i] = (f"option decision season '{move_season}' is invalid; "
                           "use YYYY-YY")
            continue
        entries.append((i, move_season))
    distinct = sorted({season for _, season in entries})
    if implicit_requested:
        for i, move_season in entries:
            if move_season != requested:
                rejected[i] = (f"option decision for {move_season} cannot be combined "
                               f"with moves evaluated in {requested}; evaluate one season "
                               "at a time")
        return requested, rejected
    if len(distinct) == 1:
        target = distinct[0]
        if target == requested:
            return requested, rejected
        if _option_only_moves(moves_in):
            return target, rejected
        for i, move_season in entries:
            rejected[i] = (f"option decision for {move_season} cannot be combined "
                           f"with moves evaluated in {requested}; evaluate one season "
                           "at a time")
        return requested, rejected
    if len(distinct) > 1:
        for i, move_season in entries:
            if move_season != requested or requested not in distinct:
                rejected[i] = (f"option decision for {move_season} is outside scenario "
                               f"season {requested}; evaluate one season at a time")
    return requested, rejected


def _player_option_year(con, player: str, team: str, season: str) -> dict[str, Any]:
    if not _valid_season_label(season):
        return {"ok": False, "error": f"option season '{season}' is invalid; use YYYY-YY"}
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "silver_salaries" not in tables:
        return {"ok": False, "error": "silver_salaries not in warehouse"}
    cols = {r[1] for r in con.execute("PRAGMA table_info(silver_salaries)").fetchall()}
    salary_col = season_column(season)
    option_col = option_column(season)
    missing = [name for name in (salary_col, option_col) if name not in cols]
    if missing:
        return {"ok": False,
                "error": f"per-year option data unavailable for {season}; cannot evaluate without guessing"}
    try:
        row = con.execute(
            f"SELECT {salary_col}, {option_col} FROM silver_salaries "
            "WHERE UPPER(TEAM) = UPPER(?) AND LOWER(PLAYER_NAME) = LOWER(?) LIMIT 1",
            [team, player]).fetchone()
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}
    if not row:
        return {"ok": False, "error": f"could not match {player} on {team}"}
    salary, option = row
    return {"ok": True,
            "salary": int(salary) if salary is not None else None,
            "option": str(option).lower() if option else None}


def _option_decline_move(con, team: str, season: str, player: str) -> tuple[dict[str, Any] | None, str | None]:
    _total, matched, unknown = _match_trade_players(team, player, con, season)
    if unknown or not matched:
        return None, f"could not match {player} on {team}"
    year = _player_option_year(con, matched[0], team, season)
    if not year.get("ok"):
        return None, str(year.get("error") or "option year unavailable")
    if year.get("option") not in ("player", "team"):
        return None, f"{matched[0]} has no player or team option scheduled for {season}"
    amount = year.get("salary")
    if not isinstance(amount, int) or amount <= 0:
        return None, f"{matched[0]} has no salary scheduled for {season}"
    detail = f"decline {matched[0]} {year['option']} option ({season})"
    return {"kind": "trade_out", "detail": detail, "amount": amount,
            "player": matched[0]}, None




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


def _cap_hold_payload(con, team: str, season: str) -> dict[str, Any]:
    match = _re.match(r"(\d{4})-\d{2}$", str(season or ""))
    if not match:
        return {"rows": [], "total": 0, "active_total": 0, "unknown_count": 0,
                "money_unit": "usd_dollars", "meta": {}}
    try:
        return derive_cap_holds(con, int(match.group(1)), team)
    except Exception as exc:
        return {"rows": [], "total": 0, "active_total": 0, "unknown_count": 0,
                "money_unit": "usd_dollars",
                "meta": {"derivation_status": "error", "error": str(exc)[:200]}}


def _positive_hold_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if hold_amount(row) > 0)


def _cap_room_charge_inputs(con, team: str, season: str) -> dict[str, Any]:
    fallback = {"players_under_contract": None, "minimum": 1_493_539,
                "minimum_source": "unavailable", "stored_charges": 0,
                "available": False}
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    except Exception:
        return fallback
    if "silver_cap_room" not in tables:
        return fallback
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(silver_cap_room)").fetchall()}
        wanted = ["PLAYERS_UNDER_CONTRACT", "ROSTER_CHARGE_MINIMUM",
                  "INCOMPLETE_ROSTER_CHARGES"]
        pick = [c for c in wanted if c in cols]
        if not pick:
            return fallback
        row = con.execute(
            "SELECT " + ", ".join(pick) + " FROM silver_cap_room "
            "WHERE UPPER(TEAM) = UPPER(?) AND CAP_SEASON = ? LIMIT 1",
            [team, season]).fetchone()
    except Exception:
        return fallback
    if not row:
        return fallback
    data = dict(zip(pick, row))
    minimum = data.get("ROSTER_CHARGE_MINIMUM")
    return {"players_under_contract": data.get("PLAYERS_UNDER_CONTRACT"),
            "minimum": int(minimum) if minimum else 1_493_539,
            "minimum_source": "warehouse" if minimum else "legacy_approximation",
            "stored_charges": int(data.get("INCOMPLETE_ROSTER_CHARGES") or 0),
            "available": True}


def _roster_charge(players: int, hold_count: int, minimum: int) -> int:
    return max(0, 12 - int(players) - int(hold_count)) * int(minimum)


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
    holds_note = ("cap_holds are active expired-contract holds; option-dependent "
                  "potential holds are detailed but excluded until an explicit "
                  "option decline, and incomplete_roster_charges count positive "
                  "active holds as occupied roster spots")
    hold_payloads: dict[str, dict[str, Any]] = {}
    if "silver_cap_room" in tables:
        try:
            holds = con.execute(
                "SELECT CAP_SEASON, FA_HOLDS_EST, INCOMPLETE_ROSTER_CHARGES "
                "FROM silver_cap_room WHERE UPPER(TEAM) = UPPER(?)", [team]).fetchall()
            for r in holds:
                label = str(r[0])
                if label not in totals:
                    continue
                payload = _cap_hold_payload(con, team, label)
                hold_payloads[label] = payload
                rows_for_label = list(payload.get("rows") or [])
                if rows_for_label or payload.get("meta", {}).get("derivation_status"):
                    totals[label]["cap_holds"] = int(payload.get("active_total") or 0)
                else:
                    totals[label]["cap_holds"] = int(r[1] or 0)
                charge_inputs = _cap_room_charge_inputs(con, team, label)
                players = charge_inputs.get("players_under_contract")
                active_rows = [item for item in rows_for_label
                               if item.get("active_in_baseline")]
                if players is not None:
                    totals[label]["incomplete_roster_charges"] = _roster_charge(
                        int(players), _positive_hold_count(active_rows),
                        int(charge_inputs["minimum"]))
                else:
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
            "cap_hold_details": (hold_payloads.get(season) or {}).get("rows", []),
            "cap_hold_money_unit": "usd_dollars",
            "state": state,
            "meta": {"holds_note": holds_note, "season_columns": sheet["seasons"],
                     "unrolling": "shared.tools.cap_sheet",
                     "source": _payroll_source(con), "salary_date": _salary_date(con),
                     "season": season,
                     "cap_hold_derivation": (hold_payloads.get(season) or {}).get("meta", {}),
                     **payroll_proxy_meta()}}


def _hold_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {normalize_name(row.get("player") or row.get("PLAYER_NAME")): row
            for row in rows if row.get("player") or row.get("PLAYER_NAME")}


def _match_hold(index: dict[str, dict[str, Any]], name: object) -> dict[str, Any] | None:
    return index.get(normalize_name(name))


def _hold_inclusion(rows: list[dict[str, Any]], declined: set[str],
                    extinguished: set[str]) -> tuple[list[dict[str, Any]], int, int]:
    detailed = []
    total = 0
    for row in rows:
        key = normalize_name(row.get("player") or row.get("PLAYER_NAME"))
        active = bool(row.get("active_in_baseline"))
        include = ((active or key in declined) and key not in extinguished
                   and row.get("cap_hold") is not None)
        amount = hold_amount(row) if include else 0
        total += amount
        detailed.append({**row, "included_in_team_salary": include,
                         "included_amount": amount,
                         "included_money_unit": "usd_dollars"})
    return detailed, total, _positive_hold_count([r for r in detailed if r["included_in_team_salary"]])


def _charge_players(room_inputs: dict[str, Any], roster_count: int) -> int:
    value = room_inputs.get("players_under_contract")
    return int(value) if value is not None else int(roster_count)


def evaluate_cap_scenario(con, payload: dict[str, Any]) -> dict[str, Any]:
    team = str(payload.get("team") or "").strip().upper()
    requested_season = str(payload.get("season") or "").strip() or "2026-27"
    moves_in = payload.get("moves")
    if not team:
        return {"ok": False, "error": "team needed"}
    if not isinstance(moves_in, list) or not moves_in:
        return {"ok": False, "error": "moves must be a non-empty list"}
    season, rejected_options = _scenario_season(requested_season, moves_in)
    waiver_timing, waiver_timing_error = resolve_waiver_timing(
        payload.get("waiver_date"), season)
    if waiver_timing_error:
        return {"ok": False, "error": waiver_timing_error}
    lines, lines_projected = cap_lines_for_season(con, season)
    try:
        pay_before, roster = _payroll(team, con, season)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}
    hold_payload = _cap_hold_payload(con, team, season)
    hold_rows = list(hold_payload.get("rows") or [])
    hold_index = _hold_index(hold_rows)
    declined_holds: set[str] = set()
    extinguished_holds: set[str] = set()
    cap_hold_events: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = [
        {"move": str(i), "error": error}
        for i, error in sorted(rejected_options.items())]
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
            hold_match = _match_hold(hold_index, raw.get("player") or label)
            if hold_match is not None:
                key = normalize_name(hold_match.get("player"))
                extinguished_holds.add(key)
                cap_hold_events.append({"kind": "signed", "player": hold_match.get("player"),
                                        "amount": hold_match.get("cap_hold"),
                                        "money_unit": "usd_dollars"})
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
            moves.append(waiver_move(con, team, matched[0], amount, season, stretch,
                                     timing=waiver_timing))
            roster_delta -= 1
        elif kind == "renounce":
            player = str(raw.get("player") or raw.get("label") or "").strip()
            if not player:
                errors.append({"move": str(i), "error": "renounce needs a player"})
                continue
            hold_match = _match_hold(hold_index, player)
            if hold_match is None:
                errors.append({"move": str(i),
                               "error": f"no {team} free-agent cap hold found for {player}"})
                continue
            key = normalize_name(hold_match.get("player"))
            extinguished_holds.add(key)
            cap_hold_events.append({"kind": "renounced", "player": hold_match.get("player"),
                                    "amount": hold_match.get("cap_hold"),
                                    "money_unit": "usd_dollars",
                                    "scenario_dependency": hold_match.get("scenario_dependency")})
        elif kind == "option_decision":
            player = str(raw.get("player") or "").strip()
            exercise = bool(raw.get("exercise", True))
            move_season = str(raw.get("season") or season).strip() or season
            if i in rejected_options:
                continue
            if move_season != season:
                errors.append({"move": str(i),
                               "error": f"option decision for {move_season} is outside scenario season {season}; evaluate one season at a time"})
                continue
            if exercise:
                continue
            move, error = _option_decline_move(con, team, season, player)
            if error:
                errors.append({"move": str(i), "error": error})
                continue
            moves.append(move)
            hold_match = _match_hold(hold_index, move.get("player"))
            if hold_match is not None:
                key = normalize_name(hold_match.get("player"))
                declined_holds.add(key)
                cap_hold_events.append({"kind": "option_declined",
                                        "player": hold_match.get("player"),
                                        "amount": hold_match.get("cap_hold"),
                                        "money_unit": "usd_dollars"})
            roster_delta -= 1
        else:
            errors.append({"move": str(i), "error": f"unknown move kind '{kind}'"})
    trace = scenario_trace(pay_before, moves, f"{team} committed payroll")
    pay_after = int(trace["pay_after"])
    state = apron_state(pay_after, lines)
    holds_before_detail, cap_holds_before, hold_count_before = _hold_inclusion(
        hold_rows, set(), set())
    holds_after_detail, cap_holds_after, hold_count_after = _hold_inclusion(
        hold_rows, declined_holds, extinguished_holds)
    charge_inputs = _cap_room_charge_inputs(con, team, season)
    players_charge_before = _charge_players(charge_inputs, len(roster))
    players_charge_after = players_charge_before + roster_delta
    if charge_inputs.get("available"):
        roster_charges_before = _roster_charge(
            players_charge_before, hold_count_before, int(charge_inputs["minimum"]))
        roster_charges_after = _roster_charge(
            players_charge_after, hold_count_after, int(charge_inputs["minimum"]))
    else:
        roster_charges_before = 0
        roster_charges_after = 0
    team_salary_before = int(pay_before) + cap_holds_before + roster_charges_before
    team_salary_after = pay_after + cap_holds_after + roster_charges_after
    cap_room_before = lines["cap"] - team_salary_before
    cap_room_after = lines["cap"] - team_salary_after
    issues: list[str] = []
    matching: dict[str, Any] | None = None
    hard_cap = ""
    room_before = max(0, cap_room_before)
    if out_names and in_names:
        aggregates = len(out_names) > 1
        cushion = 0 if state["over_apron1"] else 250_000
        expanded_matching = used_expanded_matching(
            in_total, out_total, room_before, cushion=cushion)
        election = matching_election(
            in_total, out_total, room_before, cushion,
            len(out_names), expanded_matching)
        if expanded_matching:
            hard_cap = "first apron"
            if pay_after > lines["apron1"]:
                issues.append(
                    f"{team} cannot use the Expanded Traded Player Exception "
                    f"because post-trade payroll proxy (${pay_after:,}) would "
                    f"exceed the first apron (${lines['apron1']:,}); the "
                    "transaction is prohibited")
        if state["over_apron2"] and aggregates:
            issues.append("cannot aggregate salaries above the second apron")
            matching = {"incoming": in_total, "outgoing": out_total, "legal": False,
                        "match_rule": "no aggregation (above the second apron)",
                        "allowed_incoming": 0, **election}
        else:
            band = matching_band(out_total, bool(state["over_apron1"]), room_before)
            rule = operative_match_rule(band["match_rule"], election)
            matching = {"incoming": in_total, "outgoing": out_total,
                        "allowed_incoming": band["allowed_incoming"],
                        "match_rule": rule,
                        "legal": in_total <= band["allowed_incoming"], **election}
            if not matching["legal"]:
                issues.append(f"{team} takes back too much "
                              f"(${in_total:,} vs {band['allowed_incoming']:,} "
                              f"allowed under {rule})")
        if aggregates and pay_after > lines["apron2"]:
            issues.append("aggregation would hard-cap the team at the second apron")
    roster_after = len(roster) + roster_delta
    roster_issue_list = roster_issues(roster_after)
    issues.extend(roster_issue_list)
    state_with_room = {**state, "cap_room": cap_room_after}
    restrictions = cba_restrictions(state_with_room, season)
    state["room_under_apron2"] = state["room_apron2"]
    before_by_name = {normalize_name(row.get("player")): row
                      for row in holds_before_detail}
    cap_hold_details = []
    for row in holds_after_detail:
        before = before_by_name.get(normalize_name(row.get("player"))) or {}
        cap_hold_details.append({
            **row,
            "included_in_team_salary_before": before.get("included_in_team_salary", False),
            "included_amount_before": before.get("included_amount", 0),
            "included_in_team_salary_after": row.get("included_in_team_salary", False),
            "included_amount_after": row.get("included_amount", 0)})
    return {"ok": True, "team": team, "season": season,
            "steps": trace["steps"], "pay_after": pay_after,
            "pay_before": int(pay_before),
            "team_salary_before": team_salary_before,
            "team_salary_after": team_salary_after,
            "cap_room_before": cap_room_before,
            "cap_room_after": cap_room_after,
            "team_salary_unit": "usd_dollars",
            "cap_room_unit": "usd_dollars",
            "cap_holds_before": cap_holds_before,
            "cap_holds_after": cap_holds_after,
            "cap_hold_money_unit": "usd_dollars",
            "roster_charges_before": roster_charges_before,
            "roster_charges_after": roster_charges_after,
            "roster_charge_money_unit": "usd_dollars",
            "cap_hold_details": cap_hold_details,
            "cap_hold_events": cap_hold_events,
            "state": state,
            "lines": lines, "lines_projected": lines_projected,
            "restrictions": restrictions,
            "roster_before": len(roster), "roster_after": roster_after,
            "roster_issues": roster_issue_list,
            "hard_cap": hard_cap, "issues": issues, "errors": errors,
            "matching": matching,
            "meta": {"source": _payroll_source(con), "salary_date": _salary_date(con),
                     "requested_season": requested_season,
                     "cap_hold_derivation": hold_payload.get("meta") or {},
                     "team_salary_note": "team_salary and cap_room include active cap holds plus dynamic incomplete-roster charges; pay_before/pay_after remain committed payroll proxies used for tax/apron comparisons",
                     "roster_charge_note": "positive included cap holds count as occupied roster spots; renouncing or signing a hold opens a spot and increases the incomplete-roster charge, while declining an option can activate its disclosed potential hold",
                     "roster_charge_minimum_source": charge_inputs.get("minimum_source"),
                     **payroll_proxy_meta(),
                     **({"waiver_basis": WAIVER_BASIS,
                         "waiver_timing": waiver_timing}
                        if any(move.get("kind") == "waive" for move in moves) else {})}}
