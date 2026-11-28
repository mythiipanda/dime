import re as _re
from typing import Any

from ..cap_rules import (
    CAP,
    CAP_GROWTH_ASSUMPTION,
    active_hard_cap_failure,
    apron_state,
    cba_restrictions,
    hard_cap_consequences,
    matching_band,
    matching_election,
    operative_match_rule,
    payroll_proxy_meta,
    roster_issues,
    scenario_trace,
    used_expanded_matching,
)
from ..signing_rules import (
    SIGNING_PROXY_DISCLOSURE,
    SIGNING_VALIDATION_VERSION,
    consume_signing_exception,
    initial_exception_state,
    normalize_exception_state_input,
    validate_signing,
)
from ..cap_sheet import option_column, season_column, unroll_team_sheet
from .._core import warehouse_identity_meta
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
                            "apron1": int(row[3] or 0), "apron2": int(row[4] or 0)}, True
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
                     **warehouse_identity_meta(),
                     "source": _payroll_source(con), "salary_date": _salary_date(con),
                     "season": season,
                     "cap_hold_derivation": (hold_payloads.get(season) or {}).get("meta", {}),
                     **payroll_proxy_meta()}}


def _move_delta(move: dict[str, Any]) -> int:
    amount = int(move.get("amount") or 0)
    return -amount if move.get("kind") in ("trade_out", "waive") else amount


def _hold_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {normalize_name(row.get("player") or row.get("PLAYER_NAME")): row
            for row in rows if row.get("player") or row.get("PLAYER_NAME")}


def _match_hold(index: dict[str, dict[str, Any]], name: object) -> dict[str, Any] | None:
    return index.get(normalize_name(name))


def _option_dependency_error(hold: dict[str, Any] | None, declined: set[str],
                             action: str) -> str | None:
    if hold is None:
        return None
    key = normalize_name(hold.get("player"))
    if (hold.get("scenario_dependency") == "option_decision_required"
            and key not in declined):
        return (f"{action} {hold.get('player')} requires a prior option decision decline; "
                "the option salary is still committed")
    return None


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
    included = [row for row in detailed if row["included_in_team_salary"]]
    return detailed, total, _positive_hold_count(included)


def _charge_players(room_inputs: dict[str, Any], roster_count: int) -> int:
    value = room_inputs.get("players_under_contract")
    return int(value) if value is not None else int(roster_count)


def _money_state(sequence: dict[str, Any], committed: int, roster_delta: int,
                 declined: set[str], extinguished: set[str]) -> dict[str, Any]:
    details, holds, hold_count = _hold_inclusion(
        sequence["hold_rows"], declined, extinguished)
    players = int(sequence["charge_players_before"]) + int(roster_delta)
    if sequence["charge_inputs"].get("available"):
        charges = _roster_charge(
            players, hold_count, int(sequence["charge_inputs"]["minimum"]))
    else:
        charges = 0
    return {"committed_payroll": int(committed), "cap_holds": holds,
            "roster_charges": charges, "hold_count": hold_count,
            "charge_players": players, "details": details,
            "team_salary": int(committed) + holds + charges}


def _sequence_money_state(sequence: dict[str, Any]) -> dict[str, Any]:
    return _money_state(sequence, int(sequence["running_payroll"]),
                        int(sequence["roster_delta"]),
                        sequence["declined_holds"],
                        sequence["extinguished_holds"])


def _signing_validation_team_salary(sequence: dict[str, Any],
                                    money_before: dict[str, Any],
                                    hold_match: dict[str, Any] | None) -> int:
    validation_team_salary = int(money_before["team_salary"])
    hold_count_after = int(money_before["hold_count"])
    if hold_match is not None:
        key = normalize_name(hold_match.get("player"))
        detail = next((row for row in money_before["details"]
                       if normalize_name(row.get("player")) == key), None)
        if detail is not None and detail.get("included_in_team_salary"):
            validation_team_salary -= int(detail.get("included_amount") or 0)
            if hold_amount(detail) > 0:
                hold_count_after -= 1
    if sequence["charge_inputs"].get("available"):
        minimum = int(sequence["charge_inputs"]["minimum"])
        players_before = int(money_before["charge_players"])
        charge_before = _roster_charge(
            players_before, int(money_before["hold_count"]), minimum)
        charge_after = _roster_charge(
            players_before + 1, hold_count_after, minimum)
        validation_team_salary += charge_after - charge_before
    return validation_team_salary


def _baseline_money_state(sequence: dict[str, Any], pay_before: int) -> dict[str, Any]:
    return _money_state(sequence, int(pay_before), 0, set(), set())


def _merge_hard_cap_labels(*values: str) -> str:
    merged: list[str] = []
    for value in values:
        for part in str(value or "").split("+"):
            if part and part not in merged:
                merged.append(part)
    return "+".join(merged)


def _exception_override_errors(declared: Any, current: dict[str, Any],
                               adopt_initial: bool) -> tuple[dict[str, Any] | None, list[str], bool]:
    normalized, errors = normalize_exception_state_input(declared)
    if errors:
        return None, [error if "override rejected" in error else
                      f"{error}; exception_state override rejected"
                      for error in errors], True
    if normalized is None or adopt_initial:
        return normalized, [], False
    conflicts: list[str] = []
    for key in declared:
        if key in normalized and normalized[key] != current.get(key):
            conflicts.append(
                f"exception_state.{key} is fixed at scenario start: declared "
                f"{normalized[key]!r} but cumulative state is {current.get(key)!r}; "
                "override rejected")
    return normalized, conflicts, False


def _record_hard_cap_trigger(sequence: dict[str, Any], transaction: str,
                             move_index: int, hard_cap: str, active: bool) -> None:
    for apron in str(hard_cap or "").split("+"):
        if apron:
            sequence["hard_cap_trigger_events"].append({
                "transaction": transaction, "move_index": move_index,
                "apron": apron, "status": "active" if active else "prohibited"})


def _validated_signing_move(raw: dict[str, Any], move_index: int, team: str,
                            payroll_before: int, lines: dict[str, Any],
                            exception_state: dict[str, Any],
                            active_hard_caps: list[str], season: str,
                            team_salary_before: int
                            ) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
    validation_input = {key: value for key, value in raw.items()
                        if key != "exception_state"}
    validation = validate_signing(
        validation_input, team=team, payroll_before=payroll_before, lines=lines,
        exception_state=exception_state, active_hard_caps=active_hard_caps,
        season=season, team_salary_before=team_salary_before)
    validation["move_index"] = move_index
    if validation["input_errors"]:
        return None, validation, "; ".join(validation["input_errors"])
    display = str(raw.get("label") or raw.get("player")
                  or f"${validation['amount'] / 1_000_000:g}M signing")
    move = {"kind": "signing", "detail": f"sign {display}",
            "amount": validation["amount"], "validation": validation}
    if raw.get("player"):
        move["player"] = str(raw.get("player"))
    return move, validation, None


def _initial_sequence_state(payload: dict[str, Any], pay_before: int,
                            errors: list[dict[str, str]],
                            hold_rows: list[dict[str, Any]],
                            charge_inputs: dict[str, Any],
                            roster_count: int) -> dict[str, Any]:
    exception_state = initial_exception_state()
    exception_state_seeded = False
    if "exception_state" in payload:
        normalized, state_errors = normalize_exception_state_input(
            payload.get("exception_state"))
        if state_errors:
            for error in state_errors:
                errors.append({"move": "scenario", "error": error})
        elif normalized is not None:
            exception_state = normalized
            exception_state_seeded = True
    return {
        "moves": [],
        "errors": list(errors),
        "running_payroll": int(pay_before),
        "roster_delta": 0,
        "hold_rows": list(hold_rows),
        "hold_index": _hold_index(list(hold_rows)),
        "declined_holds": set(),
        "extinguished_holds": set(),
        "cap_hold_events": [],
        "charge_inputs": dict(charge_inputs),
        "charge_players_before": _charge_players(charge_inputs, roster_count),
        "exception_state": exception_state,
        "exception_state_open": True,
        "exception_state_seeded": exception_state_seeded,
        "active_hard_caps": [],
        "hard_cap_trigger_events": [],
        "issues": [],
        "signing_validations": [],
        "signing_blocking": [],
        "signing_advisory": [],
        "signed_players": set(),
        "illegal_move_indices": [],
        "unvalidated_move_indices": [],
        "matching": None,
        "trade_group": None,
    }


def _add_move_error(sequence: dict[str, Any], move_index: int, error: str) -> None:
    sequence["errors"].append({"move": str(move_index), "error": error})


def _ensure_trade_group(sequence: dict[str, Any], move_index: int,
                        lines: dict[str, Any]) -> dict[str, Any]:
    group = sequence.get("trade_group")
    if group is None:
        team_salary = int(_sequence_money_state(sequence)["team_salary"])
        group = {
            "start_index": move_index,
            "end_index": move_index,
            "payroll_before": int(sequence["running_payroll"]),
            "payroll_after": int(sequence["running_payroll"]),
            "team_salary_before": team_salary,
            "cap_room_before": int(lines["cap"]) - team_salary,
            "in_names": [], "out_names": [],
            "in_total": 0, "out_total": 0,
        }
        sequence["trade_group"] = group
    return group


def _activate_hard_caps(sequence: dict[str, Any], hard_cap: str) -> None:
    for apron in str(hard_cap or "").split("+"):
        if apron and apron not in sequence["active_hard_caps"]:
            sequence["active_hard_caps"].append(apron)


def _trade_matching_verdict(team: str, group: dict[str, Any],
                            lines: dict[str, Any]) -> tuple[dict[str, Any], list[str], bool, dict[str, Any]]:
    in_total = int(group["in_total"])
    out_total = int(group["out_total"])
    payroll_after = int(group["payroll_after"])
    payroll_before = int(group["payroll_before"])
    post_state = apron_state(payroll_after, lines)
    room_before = max(0, int(group.get("cap_room_before", lines["cap"] - payroll_before)))
    aggregates = len(group["out_names"]) > 1
    cushion = 0 if post_state["over_apron1"] else 250_000
    expanded_matching = used_expanded_matching(
        in_total, out_total, room_before, cushion=cushion)
    election = matching_election(
        in_total, out_total, room_before, cushion,
        len(group["out_names"]), expanded_matching)
    issues: list[str] = []
    if post_state["over_apron2"] and aggregates:
        issues.append("cannot aggregate salaries above the second apron")
        matching = {"incoming": in_total, "outgoing": out_total, "legal": False,
                    "match_rule": "no aggregation (above the second apron)",
                    "allowed_incoming": 0, **election}
    else:
        band = matching_band(out_total, bool(post_state["over_apron1"]), room_before)
        rule = operative_match_rule(band["match_rule"], election)
        matching = {"incoming": in_total, "outgoing": out_total,
                    "allowed_incoming": band["allowed_incoming"],
                    "match_rule": rule,
                    "legal": in_total <= band["allowed_incoming"], **election}
        if not matching["legal"]:
            issues.append(f"{team} takes back too much "
                          f"(${in_total:,} vs {band['allowed_incoming']:,} "
                          f"allowed under {rule})")
    return matching, issues, expanded_matching, post_state


def _close_trade_group(sequence: dict[str, Any], team: str,
                       lines: dict[str, Any]) -> None:
    group = sequence.get("trade_group")
    if group is None:
        return
    sequence["trade_group"] = None
    if not group["out_names"] or not group["in_names"]:
        return
    matching, matching_issues, expanded_matching, _post_state = _trade_matching_verdict(
        team, group, lines)
    matching["evaluation_move_index"] = group["end_index"]
    matching["post_trade_payroll"] = int(group["payroll_after"])
    consequence = hard_cap_consequences(
        team, int(group["payroll_after"]), aggregates=len(group["out_names"]) > 1,
        expanded_matching=expanded_matching, lines=lines)
    issues: list[str] = []
    active_failure = active_hard_cap_failure(
        int(group["payroll_after"]), sequence["active_hard_caps"], lines,
        transaction="trade")
    if active_failure:
        issues.append(f"{team} cannot complete the trade because {active_failure}; "
                      "the transaction is prohibited")
    issues.extend(consequence["issues"])
    issues.extend(matching_issues)
    sequence["issues"].extend(issues)
    sequence["matching"] = matching
    if active_failure or consequence["violations"] or not matching.get("legal"):
        sequence["illegal_move_indices"].extend(
            range(int(group["start_index"]), int(group["end_index"]) + 1))
    activated = bool(consequence["hard_cap"] and not consequence["violations"]
                     and not active_failure and matching.get("legal"))
    _record_hard_cap_trigger(sequence, "trade", int(group["end_index"]),
                             str(consequence["hard_cap"]), activated)
    if activated:
        _activate_hard_caps(sequence, consequence["hard_cap"])


def _prepare_signing_exception_state(raw: dict[str, Any], move_index: int,
                                     sequence: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if "exception_state" not in raw:
        sequence["exception_state_open"] = False
        return raw, False
    declared = raw.get("exception_state")
    adopt_initial = bool(sequence["exception_state_open"]
                         and not sequence["exception_state_seeded"])
    normalized, override_errors, normalization_failed = _exception_override_errors(
        declared, sequence["exception_state"], adopt_initial)
    if override_errors:
        for error in override_errors:
            _add_move_error(sequence, move_index, error)
    elif normalized is not None and adopt_initial and isinstance(declared, dict):
        seed = dict(sequence["exception_state"])
        for key in declared:
            if key in normalized:
                seed[key] = normalized[key]
        sequence["exception_state"] = initial_exception_state(seed)
        sequence["exception_state_seeded"] = True
    sequence["exception_state_open"] = False
    stripped = {key: value for key, value in raw.items() if key != "exception_state"}
    return stripped, normalization_failed


def _extinguish_hold(hold: dict[str, Any], sequence: dict[str, Any],
                     kind: str) -> None:
    key = normalize_name(hold.get("player"))
    sequence["extinguished_holds"].add(key)
    event = {"kind": kind, "player": hold.get("player"),
             "amount": hold.get("cap_hold"),
             "money_unit": "usd_dollars"}
    if kind == "renounced":
        event["scenario_dependency"] = hold.get("scenario_dependency")
    sequence["cap_hold_events"].append(event)


def _process_signing(raw: dict[str, Any], move_index: int, team: str,
                     season: str, lines: dict[str, Any],
                     sequence: dict[str, Any]) -> None:
    hold_match = _match_hold(
        sequence["hold_index"], raw.get("player") or raw.get("label"))
    option_error = _option_dependency_error(
        hold_match, sequence["declined_holds"], "signing")
    if option_error is not None:
        _add_move_error(sequence, move_index, option_error)
        return
    money_before = _sequence_money_state(sequence)
    validation_team_salary = _signing_validation_team_salary(
        sequence, money_before, hold_match)
    validation_raw, exception_state_invalid = _prepare_signing_exception_state(
        raw, move_index, sequence)
    if exception_state_invalid:
        validation = validate_signing(
            raw, team=team, payroll_before=int(sequence["running_payroll"]),
            lines=lines, active_hard_caps=sequence["active_hard_caps"],
            season=season,
            team_salary_before=validation_team_salary)
        validation["move_index"] = move_index
        sequence["signing_validations"].append(validation)
        return
    move, validation, error = _validated_signing_move(
        validation_raw, move_index, team, int(sequence["running_payroll"]), lines,
        sequence["exception_state"], sequence["active_hard_caps"], season,
        validation_team_salary)
    if error:
        _add_move_error(sequence, move_index, str(error))
        return
    sequence["moves"].append(move)
    sequence["signing_validations"].append(validation)
    player = str(validation.get("player") or "signing")
    sequence["signed_players"].add(normalize_name(player))
    if validation["outcome"] == "illegal":
        sequence["illegal_move_indices"].append(move_index)
    elif not validation["legal"]:
        sequence["unvalidated_move_indices"].append(move_index)
    blocking = [f"{player}: {issue}" for issue in validation["blocking_issues"]]
    sequence["signing_blocking"].extend(blocking)
    sequence["issues"].extend(blocking)
    sequence["signing_advisory"].extend(
        f"{player}: {issue}" for issue in validation["advisory_issues"])
    _record_hard_cap_trigger(sequence, "signing", move_index,
                             str(validation["hard_cap_trigger"]),
                             bool(validation["legal"]))
    if validation["legal"]:
        sequence["exception_state"] = consume_signing_exception(
            sequence["exception_state"], validation)
        _activate_hard_caps(sequence, validation["hard_cap_trigger"])
    sequence["running_payroll"] += int(move["amount"])
    sequence["roster_delta"] += 1
    if hold_match is not None:
        _extinguish_hold(hold_match, sequence, "signed")


def _process_trade_out(con, raw: dict[str, Any], move_index: int, team: str,
                       season: str, lines: dict[str, Any],
                       roster: list[dict[str, Any]],
                       sequence: dict[str, Any]) -> None:
    player = str(raw.get("player") or "").strip()
    if not player:
        _add_move_error(sequence, move_index, "trade_out needs a player")
        return
    if normalize_name(player) in sequence["signed_players"]:
        _add_move_error(
            sequence, move_index,
            f"trade_out of {player} after a same-scenario signing is unsupported "
            "sign-and-trade sequencing; atomic sign-and-trade, BYC, and coupled "
            "hard-cap treatment are outside cap scenario validation v1")
        return
    _total, matched, unknown = _match_trade_players(team, player, con, season)
    if unknown or not matched:
        _add_move_error(sequence, move_index, f"could not match {player} on {team}")
        return
    hit = next((p for p in roster if p["player"] == matched[0]), None)
    amount = int((hit or {}).get("salary") or 0)
    move = {"kind": "trade_out", "detail": f"out {matched[0]}",
            "amount": amount}
    group = _ensure_trade_group(sequence, move_index, lines)
    sequence["moves"].append(move)
    sequence["running_payroll"] += _move_delta(move)
    sequence["roster_delta"] -= 1
    group["end_index"] = move_index
    group["payroll_after"] = int(sequence["running_payroll"])
    group["out_names"].append(matched[0])
    group["out_total"] += amount


def _process_trade_in(con, raw: dict[str, Any], move_index: int, team: str,
                      season: str, lines: dict[str, Any],
                      sequence: dict[str, Any]) -> None:
    player = str(raw.get("player") or "").strip()
    if not player:
        _add_move_error(sequence, move_index, "trade_in needs a player")
        return
    found = _locate_player_team(player, con, season)
    if found is None:
        _add_move_error(sequence, move_index, f"could not locate {player}")
        return
    cname, cteam, csal = found
    if str(cteam).upper() == team:
        _add_move_error(sequence, move_index, f"{cname} is already on {team}")
        return
    salary = int(csal or 0)
    move = {"kind": "trade_in",
            "detail": f"in {cname} (from {cteam})", "amount": salary}
    group = _ensure_trade_group(sequence, move_index, lines)
    sequence["moves"].append(move)
    sequence["running_payroll"] += _move_delta(move)
    sequence["roster_delta"] += 1
    group["end_index"] = move_index
    group["payroll_after"] = int(sequence["running_payroll"])
    group["in_names"].append(cname)
    group["in_total"] += salary


def _process_waiver(con, raw: dict[str, Any], move_index: int, team: str,
                    season: str, roster: list[dict[str, Any]],
                    waiver_timing: dict[str, Any],
                    sequence: dict[str, Any]) -> None:
    player = str(raw.get("player") or "").strip()
    stretch = bool(raw.get("stretch"))
    _total, matched, unknown = _match_trade_players(team, player, con, season)
    if unknown or not matched:
        _add_move_error(sequence, move_index, f"could not match {player} on {team}")
        return
    hit = next((p for p in roster if p["player"] == matched[0]), None)
    amount = int((hit or {}).get("salary") or 0)
    move = waiver_move(con, team, matched[0], amount, season, stretch,
                       timing=waiver_timing)
    sequence["moves"].append(move)
    sequence["running_payroll"] += _move_delta(move)
    sequence["roster_delta"] -= 1


def _process_option(con, raw: dict[str, Any], move_index: int, team: str,
                    season: str, rejected_options: dict[int, str],
                    sequence: dict[str, Any]) -> None:
    player = str(raw.get("player") or "").strip()
    exercise = bool(raw.get("exercise", True))
    move_season = str(raw.get("season") or season).strip() or season
    if move_index in rejected_options:
        return
    if move_season != season:
        _add_move_error(
            sequence, move_index,
            f"option decision for {move_season} is outside scenario season {season}; evaluate one season at a time")
        return
    if exercise:
        return
    move, error = _option_decline_move(con, team, season, player)
    if error:
        _add_move_error(sequence, move_index, error)
        return
    sequence["moves"].append(move)
    sequence["running_payroll"] += _move_delta(move)
    sequence["roster_delta"] -= 1
    hold_match = _match_hold(sequence["hold_index"], move.get("player"))
    if hold_match is not None:
        key = normalize_name(hold_match.get("player"))
        if key not in sequence["declined_holds"]:
            sequence["declined_holds"].add(key)
            sequence["cap_hold_events"].append({
                "kind": "option_declined", "player": hold_match.get("player"),
                "amount": hold_match.get("cap_hold"),
                "money_unit": "usd_dollars"})


def _process_renounce(raw: dict[str, Any], move_index: int, team: str,
                      sequence: dict[str, Any]) -> None:
    player = str(raw.get("player") or raw.get("label") or "").strip()
    if not player:
        _add_move_error(sequence, move_index, "renounce needs a player")
        return
    hold_match = _match_hold(sequence["hold_index"], player)
    if hold_match is None:
        _add_move_error(sequence, move_index,
                        f"no {team} free-agent cap hold found for {player}")
        return
    option_error = _option_dependency_error(
        hold_match, sequence["declined_holds"], "renouncing")
    if option_error is not None:
        _add_move_error(sequence, move_index, option_error)
        return
    _extinguish_hold(hold_match, sequence, "renounced")


def _process_scenario_move(con, raw: Any, move_index: int, team: str,
                           season: str, lines: dict[str, Any],
                           roster: list[dict[str, Any]],
                           waiver_timing: dict[str, Any],
                           rejected_options: dict[int, str],
                           sequence: dict[str, Any]) -> None:
    if not isinstance(raw, dict):
        _add_move_error(sequence, move_index, "move must be an object")
        return
    kind = str(raw.get("kind") or "").strip()
    if kind not in ("trade_out", "trade_in"):
        _close_trade_group(sequence, team, lines)
    if kind == "signing":
        _process_signing(raw, move_index, team, season, lines, sequence)
    elif kind == "trade_out":
        _process_trade_out(con, raw, move_index, team, season, lines,
                           roster, sequence)
    elif kind == "trade_in":
        _process_trade_in(con, raw, move_index, team, season, lines, sequence)
    elif kind == "waive":
        _process_waiver(con, raw, move_index, team, season, roster,
                        waiver_timing, sequence)
    elif kind == "option_decision":
        _process_option(con, raw, move_index, team, season,
                        rejected_options, sequence)
    elif kind == "renounce":
        _process_renounce(raw, move_index, team, sequence)
    else:
        _add_move_error(sequence, move_index, f"unknown move kind '{kind}'")


def _scenario_result(con, team: str, season: str, requested_season: str,
                     pay_before: int, roster: list[dict[str, Any]],
                     lines: dict[str, Any], lines_projected: bool,
                     waiver_timing: dict[str, Any],
                     sequence: dict[str, Any]) -> dict[str, Any]:
    trace = scenario_trace(pay_before, sequence["moves"], f"{team} committed payroll")
    pay_after = int(trace["pay_after"])
    money_before = _baseline_money_state(sequence, pay_before)
    money_after = _sequence_money_state(sequence)
    team_salary_before = int(money_before["team_salary"])
    team_salary_after = int(money_after["team_salary"])
    cap_room_before = int(lines["cap"]) - team_salary_before
    cap_room_after = int(lines["cap"]) - team_salary_after
    state = apron_state(pay_after, lines)
    if any(row.get("mechanism_selected") == "tmle" and row.get("legal")
           for row in sequence["signing_validations"]):
        sequence["signing_advisory"].append(
            "post-TMLE row A-F cross-move enforcement is incomplete in signing validation v1")
    roster_after = len(roster) + int(sequence["roster_delta"])
    roster_issue_list = roster_issues(roster_after)
    issues = list(roster_issue_list) + list(sequence["issues"])
    illegal_move_indices = sorted(set(sequence["illegal_move_indices"]))
    unvalidated_move_indices = sorted(set(sequence["unvalidated_move_indices"]))
    includes_illegal_moves = bool(illegal_move_indices)
    includes_unvalidated_moves = bool(unvalidated_move_indices)
    hard_cap = _merge_hard_cap_labels(*sequence["active_hard_caps"])
    trigger_events = [dict(event) for event in sequence["hard_cap_trigger_events"]]
    would_be_triggers = [dict(event) for event in trigger_events
                         if event["status"] != "active"]
    state_with_room = {**state, "cap_room": cap_room_after}
    restrictions = cba_restrictions(state_with_room, season)
    state["room_under_apron2"] = state["room_apron2"]
    before_by_name = {normalize_name(row.get("player")): row
                      for row in money_before["details"]}
    cap_hold_details = []
    for row in money_after["details"]:
        before = before_by_name.get(normalize_name(row.get("player"))) or {}
        cap_hold_details.append({
            **row,
            "included_in_team_salary_before": before.get("included_in_team_salary", False),
            "included_amount_before": before.get("included_amount", 0),
            "included_in_team_salary_after": row.get("included_in_team_salary", False),
            "included_amount_after": row.get("included_amount", 0)})
    return {"ok": True, "team": team, "season": season,
            "salary_basis": payroll_proxy_meta()["salary_basis"],
            "ats_exact": False,
            "steps": trace["steps"], "pay_after": pay_after,
            "pay_before": int(pay_before),
            "team_salary_before": team_salary_before,
            "team_salary_after": team_salary_after,
            "cap_room_before": cap_room_before,
            "cap_room_after": cap_room_after,
            "team_salary_unit": "usd_dollars",
            "cap_room_unit": "usd_dollars",
            "cap_holds_before": int(money_before["cap_holds"]),
            "cap_holds_after": int(money_after["cap_holds"]),
            "cap_hold_money_unit": "usd_dollars",
            "roster_charges_before": int(money_before["roster_charges"]),
            "roster_charges_after": int(money_after["roster_charges"]),
            "roster_charge_money_unit": "usd_dollars",
            "cap_hold_details": cap_hold_details,
            "cap_hold_events": [dict(event) for event in sequence["cap_hold_events"]],
            "state": state,
            "lines": lines, "lines_projected": lines_projected,
            "restrictions": restrictions,
            "roster_before": len(roster), "roster_after": roster_after,
            "roster_issues": roster_issue_list,
            "includes_illegal_moves": includes_illegal_moves,
            "illegal_move_indices": illegal_move_indices,
            "includes_unvalidated_moves": includes_unvalidated_moves,
            "unvalidated_move_indices": unvalidated_move_indices,
            "hard_cap": hard_cap,
            "active_hard_caps": list(sequence["active_hard_caps"]),
            "hard_cap_triggers": trigger_events,
            "would_be_hard_cap_triggers": would_be_triggers,
            "issues": issues,
            "errors": sequence["errors"],
            "matching": sequence["matching"],
            "signing_validations": sequence["signing_validations"],
            "signing_exception_state": sequence["exception_state"],
            "blocking_issues": sequence["signing_blocking"],
            "advisory_issues": sequence["signing_advisory"],
            "meta": {"source": _payroll_source(con), "salary_date": _salary_date(con),
                     "requested_season": requested_season,
                     "signing_validation_version": SIGNING_VALIDATION_VERSION,
                     "signing_proxy_disclosure": SIGNING_PROXY_DISCLOSURE,
                     "hard_cap_state_basis": "caller-order scenario sequence",
                     "cap_hold_derivation": sequence.get("cap_hold_meta") or {},
                     "illegal_move_state_disclosure": "payroll, roster, cap-hold, team-salary, and cap-room state chronologically applies syntactically valid moves even when validation rejects them as illegal, cannot establish their legality, or a trade is prohibited; includes_illegal_moves/illegal_move_indices and includes_unvalidated_moves/unvalidated_move_indices disclose that state contamination, while input errors are rejected before mutation",
                     "sign_and_trade_scope": "a signing followed by trade_out of that player in the same scenario is explicitly rejected as unsupported sign-and-trade sequencing; atomic sign-and-trade, BYC, and coupled hard-cap treatment are outside validation v1",
                     "team_salary_note": "team_salary and cap_room include active cap holds plus dynamic incomplete-roster charges; pay_before/pay_after remain committed payroll proxies used for tax/apron comparisons",
                     "roster_charge_note": "positive included cap holds count as occupied roster spots; renouncing or signing a hold opens a spot and increases the incomplete-roster charge, while declining an option can activate its disclosed potential hold",
                     "roster_charge_minimum_source": sequence["charge_inputs"].get("minimum_source"),
                     **payroll_proxy_meta(),
                     **({"waiver_basis": WAIVER_BASIS,
                         "waiver_timing": waiver_timing}
                        if any(move.get("kind") == "waive" for move in sequence["moves"]) else {})}}


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
        pay_before, roster, _dead = _payroll(team, con, season)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}
    hold_payload = _cap_hold_payload(con, team, season)
    charge_inputs = _cap_room_charge_inputs(con, team, season)
    initial_errors: list[dict[str, str]] = [
        {"move": str(i), "error": error}
        for i, error in sorted(rejected_options.items())]
    sequence = _initial_sequence_state(
        payload, pay_before, initial_errors,
        list(hold_payload.get("rows") or []), charge_inputs, len(roster))
    sequence["cap_hold_meta"] = hold_payload.get("meta") or {}
    for move_index, raw in enumerate(moves_in):
        _process_scenario_move(
            con, raw, move_index, team, season, lines, roster,
            waiver_timing, rejected_options, sequence)
    _close_trade_group(sequence, team, lines)
    return _scenario_result(
        con, team, season, requested_season, pay_before, roster,
        lines, lines_projected, waiver_timing, sequence)
