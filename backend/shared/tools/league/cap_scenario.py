import re as _re
from typing import Any

from langchain_core.tools import tool

from ...contracts import canonical_team_abbr
from ._helpers import _owned_connection, _pkg
from .cba_cap import (
    CAP,
    SalaryColumnError,
    _allowed_incoming,
    _apron_state,
    _hard_cap_consequences,
    _locate_player_team,
    _match_trade_players,
    _matching_election,
    _operative_match_rule,
    _payroll,
    _payroll_proxy_meta,
    _payroll_source,
    _salary_date,
    _used_expanded_matching,
)
from ..cap_rules import (
    cba_restrictions as _scenario_restrictions,
    roster_issues as _roster_issues,
    scenario_trace,
)
from ..signing_rules import (
    SIGNING_PROXY_DISCLOSURE,
    SIGNING_VALIDATION_VERSION,
    consume_signing_exception,
    initial_exception_state,
    validate_signing,
)
from .._core import coerce_team_id, team_error_message
from .trade_value import _trade_guard_vintage_error, _trade_unknown_message
from .waivers import WAIVER_BASIS, player_contract_tail, resolve_waiver_timing, waiver_move

_AMOUNT_RE = _re.compile(r"^\$?([\d,]+(?:\.\d+)?)\s*([mMkK])?$")
_SPLIT_RE = _re.compile(r"(?<!\d),(?!\d)|(?<=\d),(?=\s*\D)")

def _parse_amount(text: str) -> int | None:
    m = _AMOUNT_RE.fullmatch(str(text).strip())
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    suffix = (m.group(2) or "").lower()
    if suffix == "m":
        value *= 1_000_000
    elif suffix == "k":
        value *= 1_000
    return int(round(value))


def _parse_signings(text: str) -> tuple[list[tuple[str, int]], list[str]]:
    signings: list[tuple[str, int]] = []
    bad: list[str] = []
    for i, item in enumerate(
            [x.strip() for x in _SPLIT_RE.split(str(text or "")) if x.strip()], 1):
        name, amount_text = (item.split("=", 1) + [""])[:2] if "=" in item else ("", item)
        amount = _parse_amount(amount_text)
        if amount is None:
            bad.append(item)
        else:
            signings.append((str(name).strip()
                             or f"${amount / 1_000_000:g}M signing", amount))
    return signings, bad


def _legacy_move_delta(move: dict[str, Any]) -> int:
    amount = int(move.get("amount") or 0)
    return -amount if move.get("kind") in ("trade_out", "waive") else amount


def _merge_cap_labels(*values: str) -> str:
    merged: list[str] = []
    for value in values:
        for part in str(value or "").split("+"):
            if part and part not in merged:
                merged.append(part)
    return "+".join(merged)


def _validate_legacy_signings(team: str, moves: list[dict[str, Any]],
                              pay_before: int) -> dict[str, Any]:
    state = initial_exception_state(None)
    active_hard_caps: list[str] = []
    validations: list[dict[str, Any]] = []
    blocking: list[str] = []
    advisory: list[str] = []
    triggers: list[str] = []
    running = int(pay_before)
    for move_index, move in enumerate(moves):
        if move.get("kind") != "signing":
            running += _legacy_move_delta(move)
            continue
        validation = validate_signing(
            {"kind": "signing", "player": move.get("player"),
             "amount": move.get("amount"), "mechanism": "auto"},
            team=team, payroll_before=running, lines=CAP,
            exception_state=state, active_hard_caps=active_hard_caps)
        validation["move_index"] = move_index
        move["validation"] = validation
        validations.append(validation)
        player = str(validation.get("player") or "signing")
        blocking.extend(f"{player}: {issue}" for issue in validation["blocking_issues"])
        advisory.extend(f"{player}: {issue}" for issue in validation["advisory_issues"])
        if validation["hard_cap_trigger"]:
            triggers.append(validation["hard_cap_trigger"])
        if validation["legal"]:
            state = consume_signing_exception(state, validation)
            if (validation["hard_cap_trigger"]
                    and validation["hard_cap_trigger"] not in active_hard_caps):
                active_hard_caps.append(validation["hard_cap_trigger"])
        running += int(move.get("amount") or 0)
    if validations:
        advisory.append(
            "legacy comma-string signings are grouped compatibility inputs with mechanism auto and one-year terms; caller chronological ordering cannot be represented")
    return {"validations": validations, "state": state, "blocking": blocking,
            "advisory": advisory, "hard_cap": _merge_cap_labels(*triggers)}


@tool(description='Cap-scenario arithmetic for one team. "signings" takes '
    'comma-separated amounts or name=amount pairs like "Player=12M, 3000000"; '
    'this compatibility grammar is validated as mechanism auto with a one-year '
    'term and cannot represent chronological ordering or declared exception state. '
    '"in_players" adds real contracts by name (league-wide lookup). '
    '"trade_out_players" removes roster salary only when those players are '
    'actually traded away. "waive_players" waives roster players; guaranteed '
    'money remains as estimated dead cap. "stretch" uses the CBA '
    'two-times-years-plus-one estimate; player-option years count and '
    'team-option years do not. Optional "waiver_date" (YYYY-MM-DD inside the '
    'scenario league year) selects the timing branch; blank uses the July 1-Aug '
    '31 pre-Sep-1 branch and discloses that default. In the Sep 1-Jun 30 '
    'branch the current-season allocation is unchanged and only future-season '
    'salary is stretched. The retired "out_players" input is '
    'rejected because it hid that distinction. Guarantee data is a '
    'remaining-contract pool, not per-year allocations. Returns the arithmetic '
    'trace, post-move payroll vs cap/tax/first/second apron, the 2023 CBA '
    'restrictions that trigger, and the matching verdict when a trade '
    'portion is present. REACH FOR THIS for any "can X afford/sign Y" or '
    '"what if they waive/trade for Z" ask: "can the Warriors sign Player '
    'for $12M?", "what happens to Phoenix payroll if they waive Beal?", '
    '"does taking back $30M push DEN over the second apron?" It computes '
    'post-move apron status and CBA restrictions directly - do not rebuild '
    'that arithmetic from get_cap_ledger rows.')
def get_cap_scenario(team: str = "", signings: str = "",
                     in_players: str = "", trade_out_players: str = "",
                     waive_players: str = "", season: str | None = None,
                     stretch: bool = False, waiver_date: str = "",
                     out_players: str = "") -> dict[str, Any]:
    team = str(team or "").strip()
    trade_out_players = str(trade_out_players or "").strip()
    waive_players = str(waive_players or "").strip()
    out_players = str(out_players or "").strip()
    if not team:
        return {"tool": "get_cap_scenario", "ok": False, "error": "team needed"}
    if out_players:
        return {"tool": "get_cap_scenario", "ok": False,
                "error": "out_players is retired because it mixed trades and waivers; "
                         "use trade_out_players for salary actually traded away or "
                         "waive_players for a waiver"}
    if not (signings or in_players or trade_out_players or waive_players):
        return {"tool": "get_cap_scenario", "ok": False,
                "error": "no moves given - pass signings, in_players, "
                         "trade_out_players or waive_players"}
    if stretch and not waive_players:
        return {"tool": "get_cap_scenario", "ok": False,
                "error": "stretch requires waive_players"}
    from nba_api.stats.static import teams as _teams
    try:
        team_id = coerce_team_id(team)
        team = next(
            item["abbreviation"] for item in _teams.get_teams()
            if item["id"] == team_id)
    except (ValueError, StopIteration):
        return {"tool": "get_cap_scenario", "ok": False,
                "error": team_error_message(team)}
    season = str(season or "").strip()
    sign_rows, bad_signings = _parse_signings(signings)
    if bad_signings:
        return {"tool": "get_cap_scenario", "ok": False,
                "error": "unparseable signing amounts: "
                         + "; ".join(bad_signings)
                         + " (use amounts like 12000000, 12M or $12M)"}
    with _owned_connection(None, read_only=True) as con:
        if not season:
            cols = {r[1] for r in con.execute(
                "PRAGMA table_info(silver_salaries)").fetchall()}
            explicit = sorted(
                c for c in cols
                if _re.fullmatch(r"SALARY_\d{4}_\d{2}", c))
            season = (explicit[-1][len("SALARY_"):].replace("_", "-")
                      if explicit else
                      (_pkg()._salary_vintage(con)[0]
                       or _pkg().current_season()
                       or _pkg().resolve_season(None)))
        if season:
            guard_error = _trade_guard_vintage_error(con, season)
            if guard_error:
                return {"tool": "get_cap_scenario", "ok": False,
                        "error": guard_error}
        waiver_timing, waiver_timing_error = resolve_waiver_timing(waiver_date, season)
        if waiver_timing_error:
            return {"tool": "get_cap_scenario", "ok": False,
                    "error": waiver_timing_error}
        try:
            pay_before, roster = _payroll(team, con, season)
        except SalaryColumnError as exc:
            return {"tool": "get_cap_scenario", "ok": False,
                    "reason": exc.reason, "error": str(exc)}
        trade_total, trade_names, trade_unknown = _match_trade_players(
            team, trade_out_players, con, season)
        _waive_total, waive_names, waive_unknown = _match_trade_players(
            team, waive_players, con, season)
        overlap = sorted(set(trade_names) & set(waive_names))
        if overlap:
            return {"tool": "get_cap_scenario", "ok": False,
                    "error": "players cannot be both traded out and waived: "
                             + ", ".join(overlap)}
        in_names: list[str] = []
        in_unknown: list[str] = []
        in_total = 0
        in_sides: list[dict[str, Any]] = []
        for raw in [x.strip() for x in str(in_players or "").split(",") if x.strip()]:
            hit = _locate_player_team(raw, con, season)
            if hit is None:
                in_unknown.append(raw)
                continue
            cname, cteam, csal = hit
            if canonical_team_abbr(cteam) == canonical_team_abbr(team):
                in_unknown.append(f"{cname} is already on {team.upper()}")
                continue
            in_names.append(cname)
            in_total += int(csal or 0)
            in_sides.append({"player": cname, "from": cteam, "salary": csal})
        outgoing_unknown = trade_unknown + waive_unknown
        if outgoing_unknown or in_unknown:
            return {"tool": "get_cap_scenario", "ok": False,
                    "error": _trade_unknown_message(
                        team, outgoing_unknown, team, in_unknown, con)}
        waiver_tails = {name: player_contract_tail(con, name, team, season)
                        for name in waive_names}
        moves: list[dict[str, Any]] = []
        for name in trade_names:
            row = next((p for p in roster if p["player"] == name), None)
            amount = int((row or {}).get("salary") or 0)
            moves.append({"kind": "trade_out", "detail": f"out {name}",
                          "amount": amount})
        for name in waive_names:
            row = next((p for p in roster if p["player"] == name), None)
            amount = int((row or {}).get("salary") or 0)
            moves.append(waiver_move(con, team, name, amount, season, stretch,
                                     waiver_tails.get(name), waiver_timing))
        for name, amount in sign_rows:
            moves.append({"kind": "signing", "detail": f"sign {name}",
                          "amount": amount, "player": name})
        for side in in_sides:
            moves.append({"kind": "trade_in",
                          "detail": f"in {side['player']} (from {side['from']})",
                          "amount": int(side["salary"] or 0)})
        salary_date = _salary_date(con)
        source = _payroll_source(con)
    signing_validation = _validate_legacy_signings(team.upper(), moves, pay_before)
    room_before = max(0, CAP["cap"] - pay_before)
    trace = scenario_trace(pay_before, moves,
                           f"{team.upper()} committed payroll")
    rows = trace["steps"]
    step = trace["next_step"]
    pay_after = trace["pay_after"]
    state_after = _apron_state(pay_after)
    issues: list[str] = []
    matching: dict[str, Any] | None = None
    hard_cap = ""
    if trade_names and in_names:
        aggregates = len(trade_names) > 1
        cushion = 0 if state_after["over_apron1"] else 250_000
        expanded_matching = _used_expanded_matching(
            in_total, trade_total, room_before, cushion=cushion)
        election = _matching_election(
            in_total, trade_total, room_before, cushion,
            len(trade_names), expanded_matching)
        consequence = _hard_cap_consequences(
            team.upper(), pay_after, aggregates=aggregates,
            expanded_matching=expanded_matching)
        hard_cap = consequence["hard_cap"]
        issues.extend(consequence["issues"])
        if state_after["over_apron2"] and aggregates:
            issues.append("cannot aggregate salaries above the second apron")
            matching = {"incoming": in_total, "outgoing": trade_total,
                        "legal": False, "match_rule": "no aggregation (above the second apron)",
                        "allowed_incoming": 0, **election}
        else:
            allow, rule = _allowed_incoming(
                trade_total, bool(state_after["over_apron1"]), room_before)
            rule = _operative_match_rule(rule, election)
            matching = {"incoming": in_total, "outgoing": trade_total,
                        "allowed_incoming": allow, "match_rule": rule,
                        "legal": in_total <= allow, **election}
            if not matching["legal"]:
                issues.append(
                    f"{team.upper()} takes back too much "
                    f"(${in_total:,} vs {allow:,} allowed under {rule})")
    hard_cap = _merge_cap_labels(hard_cap, signing_validation["hard_cap"])
    issues.extend(signing_validation["blocking"])
    roster_before = len(roster)
    roster_after = (roster_before - len(trade_names) - len(waive_names)
                    + len(in_names) + len(sign_rows))
    issues.extend(_roster_issues(roster_after))
    rows.append({"step": step, "kind": "post_move",
                 "detail": "post-move payroll", "delta": 0,
                 "payroll": pay_after})
    res = {
        "tool": "get_cap_scenario", "ok": True,
        "salary_basis": _payroll_proxy_meta()["salary_basis"],
        "ats_exact": False,
        "rows": rows,
        "summary": {
            "team": team.upper(), "season": season,
            "payroll_before": pay_before, "payroll_after": pay_after,
            "delta": pay_after - pay_before,
            "cap_room": CAP["cap"] - pay_after,
            "tax_room": CAP["tax"] - pay_after,
            "room_apron1": state_after["room_apron1"],
            "room_apron2": state_after["room_apron2"],
            "over_tax": state_after["over_tax"],
            "over_apron1": state_after["over_apron1"],
            "over_apron2": state_after["over_apron2"],
            "hard_cap": hard_cap,
            "roster_before": roster_before, "roster_after": roster_after,
        },
        "restrictions": _scenario_restrictions({**state_after, "cap_room": CAP["cap"] - pay_after}, season),
        "issues": issues,
        "signing_validations": signing_validation["validations"],
        "signing_exception_state": signing_validation["state"],
        "blocking_issues": signing_validation["blocking"],
        "advisory_issues": signing_validation["advisory"],
        "meta": {"source": source, "rules": "v2-2023cba",
                 "salary_date": salary_date, "season": season,
                 "signing_validation_version": SIGNING_VALIDATION_VERSION,
                 "signing_proxy_disclosure": SIGNING_PROXY_DISCLOSURE,
                 **_payroll_proxy_meta(),
                 "roster_note": "player counts come from the salary sheet and "
                                "may include dead money; confirm against the "
                                "roster table",
                 **{k: v for k, v in CAP.items()}},
    }
    if waive_names:
        res["meta"]["waiver_basis"] = WAIVER_BASIS
        res["meta"]["waiver_timing"] = waiver_timing
    if matching is not None:
        res["matching"] = matching
    return res
