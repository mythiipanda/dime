import re as _re
from typing import Any

CAP = {"cap": 164_961_000, "tax": 200_428_000,
       "apron1": 209_015_000, "apron2": 221_686_000}
CAP_GROWTH_ASSUMPTION = 0.07
EXPANDED_TPE_CUSHION = 9_096_000
EXPANDED_TPE_LOW_MAX = EXPANDED_TPE_CUSHION - 250_000
EXPANDED_TPE_MID_MAX = 4 * EXPANDED_TPE_LOW_MAX
FROZEN_PICK_OFFSET = 7
TPE_CUSHION = 250_000
PAYROLL_PROXY_DISCLOSURE = (
    "Approximation, not exact Apron Team Salary: this result uses the "
    "warehouse salary ledger of listed player salaries only. It does not "
    "calculate exact ATS because performance bonuses (including unlikely "
    "bonuses counted for apron purposes), waived/stretched dead money, "
    "retired-player or grievance amounts, minimum-contract apron adjustments, "
    "restricted free-agent/offer-sheet/required-tender amounts, exception "
    "bookkeeping, two-way/conversion status, and offseason next-year "
    "assumptions are missing or estimated. Apron room, hard-cap, and TPE "
    "conclusions are screening estimates and can be wrong near either apron; "
    "do not represent this as a final CBA legality determination.")
ATS_MISSING_INPUTS = [
    "performance_bonus_amounts_and_likelihood",
    "contract_component_and_protection_allocations",
    "actual_dead_money_and_stretch_elections",
    "rfa_offer_sheet_required_tender_and_free_agent_state",
    "exception_inventory_and_usage",
    "contract_subtype_timing_flags",
    "official_team_salary_reconciliation",
]
_TRIGGER_LABELS = {
    "aggregation": "the Aggregated Standard Traded Player Exception",
    "sending cash": "cash in a trade",
    "a sign-and-trade generated exception": "a sign-and-trade-generated Traded Player Exception",
    "the sign-and-trade": "a sign-and-trade acquisition",
    "the prior-year traded player exception": "the prior-year traded player exception",
    "expanded salary matching": "the Expanded Traded Player Exception",
    "the non-taxpayer mid-level exception": "the non-taxpayer mid-level exception",
    "the bi-annual exception": "the bi-annual exception",
    "the taxpayer mid-level exception": "the taxpayer mid-level exception",
    "the high-salary waived-player signing": "the high-salary waived-player signing",
}
_NO_AVAILABLE_MATCH_RULE = ("no available salary-matching structure "
                            "(no outgoing player salary)")


def payroll_proxy_meta() -> dict[str, Any]:
    return {
        "salary_basis": "approximate_salary_ledger_not_exact_apron_team_salary",
        "ats_exact": False,
        "ats_missing_inputs": list(ATS_MISSING_INPUTS),
        "payroll_proxy_disclosure": PAYROLL_PROXY_DISCLOSURE,
    }


def apron_state(payroll: int, lines: dict | None = None) -> dict[str, object]:
    lines = lines or CAP
    return {
        "over_tax": payroll > lines["tax"],
        "over_apron1": payroll > lines["apron1"],
        "over_apron2": payroll > lines["apron2"],
        "room_apron1": lines["apron1"] - payroll,
        "room_apron2": lines["apron2"] - payroll,
    }


def allowed_incoming(outgoing: int, over_apron1: bool,
                     cap_room: int = 0) -> tuple[int, str]:
    if outgoing <= 0 and cap_room <= 0:
        return 0, _NO_AVAILABLE_MATCH_RULE
    if over_apron1:
        return outgoing, "100% (above the first apron)"
    low = outgoing * 2 + 250_000
    middle = outgoing + EXPANDED_TPE_CUSHION
    high = outgoing * 1.25 + 250_000
    matched = int(max(min(low, middle), high))
    if outgoing <= EXPANDED_TPE_LOW_MAX:
        rule = "200% plus $250k (below the first apron)"
    elif outgoing <= EXPANDED_TPE_MID_MAX:
        rule = "outgoing salary plus $9.096M (below the first apron)"
    else:
        rule = "125% plus $250k (below the first apron)"
    if cap_room > 0 and outgoing + cap_room + 250_000 > matched:
        return outgoing + cap_room + 250_000, "cap room plus outgoing salary plus $250k (under the cap)"
    return matched, rule


def used_expanded_matching(incoming: int, outgoing: int,
                           cap_room: int = 0,
                           cushion: int = TPE_CUSHION) -> bool:
    if outgoing <= 0 or incoming <= outgoing:
        return False
    if incoming <= outgoing + cushion:
        return False
    if cap_room > 0 and incoming <= outgoing + cap_room + cushion:
        return False
    return True


def matching_election(incoming: int, outgoing: int, cap_room: int = 0,
                      cushion: int = TPE_CUSHION, outgoing_count: int = 1,
                      expanded_matching: bool = False,
                      uses_declared_tpe: bool = False) -> dict[str, Any]:
    if incoming <= 0:
        base = "no_salary_matching"
    elif expanded_matching:
        base = "expanded"
    elif cap_room > 0 and incoming <= outgoing + cap_room + cushion:
        base = "cap_room"
    elif outgoing > 0 and incoming <= outgoing + cushion:
        base = ("aggregated_standard" if outgoing_count > 1
                else "standard_simultaneous")
    elif uses_declared_tpe and outgoing > 0:
        base = ("aggregated_standard" if outgoing_count > 1
                else "standard_simultaneous")
    elif uses_declared_tpe:
        base = "declared_tpe"
    elif outgoing > 0 and incoming > outgoing + cushion:
        base = "expanded"
    else:
        base = "no_available_structure"
    mechanisms = [base]
    if uses_declared_tpe and base != "declared_tpe":
        mechanisms.append("declared_tpe")
    notes = {
        "standard_simultaneous": (
            "inferred least-restrictive simultaneous structure: standard TPE "
            f"matching covers 100% of outgoing salary plus the applicable "
            f"${cushion:,} cushion; no expanded TPE or first-apron "
            "hard-cap trigger"),
        "aggregated_standard": (
            "inferred least-restrictive simultaneous structure under the "
            "current conservative multiple-outgoing-player treatment: "
            "aggregated standard TPE matching covers 100% of combined "
            f"outgoing salary plus the applicable ${cushion:,} cushion; "
            "aggregation is a second-apron transaction"),
        "cap_room": (
            "inferred structure: cap-room absorption covers the positive "
            "salary surplus under the current room approximation; no "
            "expanded TPE or first-apron hard-cap trigger"),
        "expanded": (
            "inferred least-restrictive simultaneous structure: incoming "
            "salary exceeds the standard TPE 100% plus applicable cushion "
            "band, so expanded TPE matching is required; expanded use is "
            "a first-apron transaction"),
        "declared_tpe": (
            "inferred structure: declared standard TPE use supplies the "
            "matching capacity as a separate non-combined bin"),
        "no_available_structure": (
            "no inferred simultaneous matching structure absorbs the "
            "incoming player salary under the current inputs"),
        "no_salary_matching": (
            "no incoming player salary requires salary matching"),
    }
    note = notes[base]
    if uses_declared_tpe and base != "declared_tpe":
        note += "; declared TPE rows are separate non-combined capacity bins"
    return {"matching_structure": "+".join(mechanisms),
            "matching_mechanisms": mechanisms,
            "expanded_required": bool(expanded_matching),
            "matching_note": note}


def operative_match_rule(rule: str, election: dict[str, Any]) -> str:
    mechanisms = election.get("matching_mechanisms") or []
    selected = str(mechanisms[0] if mechanisms else
                   election.get("matching_structure") or "").split("+", 1)[0]
    if selected == "standard_simultaneous":
        return ("standard TPE matching: 100% of outgoing salary plus "
                "applicable cushion")
    if selected == "aggregated_standard":
        return ("aggregated standard TPE matching: 100% of aggregated "
                "outgoing salary plus applicable cushion")
    if selected == "cap_room":
        return "cap room plus outgoing salary plus $250k (under the cap)"
    if selected == "declared_tpe":
        return "declared TPE capacity: separate non-combined exception bin"
    if selected == "no_salary_matching":
        return "no salary matching required (no incoming player salary)"
    if selected == "no_available_structure":
        return _NO_AVAILABLE_MATCH_RULE
    return rule


def hard_cap_consequences(team: str, payroll_after: int, *,
                          aggregates: bool = False, cash_out: int = 0,
                          prior_tpe: bool = False, snt_tpe: bool = False,
                          is_snt_receiver: bool = False,
                          expanded_matching: bool = False,
                          used_ntmle: bool = False,
                          used_bae: bool = False,
                          used_tmle: bool = False,
                          signed_high_salary_waived_player: bool = False,
                          lines: dict | None = None) -> dict[str, Any]:
    lines = lines or CAP
    triggers: list[tuple[str, str]] = []
    if aggregates:
        triggers.append(("second apron", "aggregation"))
    if cash_out:
        triggers.append(("second apron", "sending cash"))
    if prior_tpe:
        triggers.append(("first apron", "the prior-year traded player exception"))
    if snt_tpe:
        triggers.append(("second apron", "a sign-and-trade generated exception"))
    if is_snt_receiver:
        triggers.append(("first apron", "the sign-and-trade"))
    if expanded_matching:
        triggers.append(("first apron", "expanded salary matching"))
    if used_ntmle:
        triggers.append(("first apron", "the non-taxpayer mid-level exception"))
    if used_bae:
        triggers.append(("first apron", "the bi-annual exception"))
    if used_tmle:
        triggers.append(("second apron", "the taxpayer mid-level exception"))
    if signed_high_salary_waived_player:
        triggers.append(("first apron", "the high-salary waived-player signing"))
    aprons: list[str] = []
    causes: dict[str, list[str]] = {}
    for apron, cause in triggers:
        if apron not in aprons:
            aprons.append(apron)
        causes.setdefault(apron, []).append(cause)
    line_keys = {"first apron": "apron1", "second apron": "apron2"}
    violations = [apron for apron in aprons
                  if payroll_after > lines[line_keys[apron]]]
    issues: list[str] = []
    if "second apron" in violations:
        second_order = ("aggregation", "sending cash",
                        "a sign-and-trade generated exception",
                        "the taxpayer mid-level exception")
        second_causes = causes.get("second apron", [])
        second_cause = next((cause for cause in second_order
                             if cause in second_causes), "this deal")
        second_label = _TRIGGER_LABELS.get(second_cause, second_cause)
        issues.append(
            f"{team} cannot use {second_label} because post-trade payroll "
            f"proxy (${payroll_after:,}) would exceed the second apron "
            f"(${lines['apron2']:,}); the transaction is prohibited")
    if "first apron" in violations:
        first_order = ("the sign-and-trade",
                       "the prior-year traded player exception",
                       "expanded salary matching",
                       "the non-taxpayer mid-level exception",
                       "the bi-annual exception",
                       "the high-salary waived-player signing")
        first_causes = causes.get("first apron", [])
        first_cause = next((cause for cause in first_order
                            if cause in first_causes), "this deal")
        first_label = _TRIGGER_LABELS.get(first_cause, first_cause)
        issues.append(
            f"{team} cannot use {first_label} because post-trade payroll "
            f"proxy (${payroll_after:,}) would exceed the first apron "
            f"(${lines['apron1']:,}); the transaction is prohibited")
    return {"hard_cap": "+".join(aprons), "aprons": aprons,
            "causes": causes, "violations": violations, "issues": issues}


def active_hard_cap_failure(payroll_after: int, active_hard_caps: list[str],
                            lines: dict | None = None,
                            transaction: str = "move") -> str:
    lines = lines or CAP
    active = set(active_hard_caps or [])
    if "first apron" in active and payroll_after > lines["apron1"]:
        return (f"post-{transaction} payroll proxy (${payroll_after:,}) exceeds "
                f"the active first apron hard cap (${lines['apron1']:,})")
    if "second apron" in active and payroll_after > lines["apron2"]:
        return (f"post-{transaction} payroll proxy (${payroll_after:,}) exceeds "
                f"the active second apron hard cap (${lines['apron2']:,})")
    return ""


def matching_band(outgoing: int, over_apron1: bool,
                  cap_room: int = 0) -> dict[str, Any]:
    amount, rule = allowed_incoming(outgoing, over_apron1, cap_room)
    return {"allowed_incoming": amount, "match_rule": rule}


def frozen_pick_year(season: str) -> int | None:
    m = _re.match(r"(\d{4})", str(season or ""))
    return int(m.group(1)) + FROZEN_PICK_OFFSET + 1 if m else None


def cba_restrictions(state: dict[str, Any], season: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if state["over_apron2"]:
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "trade take-back limited to 100% of outgoing salary"})
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "cannot aggregate player salaries in a trade"})
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "cannot send cash in a trade"})
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "cannot use a traded player exception"})
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "no mid-level or bi-annual exception; veteran minimums only"})
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "cannot sign a player waived during the season whose "
                            "pre-waiver salary exceeded the non-taxpayer mid-level"})
        pick = frozen_pick_year(season)
        if pick:
            out.append({"threshold": "second apron", "status": "active",
                        "rule": f"{pick} first-round pick is frozen and cannot be traded"})
    elif state["over_apron1"]:
        out.append({"threshold": "first apron", "status": "active",
                    "rule": "trade take-back limited to 100% of outgoing salary"})
        out.append({"threshold": "first apron", "status": "active",
                    "rule": "cannot sign a player waived during the season whose "
                            "pre-waiver salary exceeded the non-taxpayer mid-level"})
    if state["over_tax"]:
        out.append({"threshold": "tax", "status": "active",
                    "rule": "luxury tax payer; taxpayer mid-level only "
                            "(no non-taxpayer MLE, no bi-annual)"})
    if not state["over_apron2"]:
        out.append({"threshold": "second apron", "status": "trigger",
                    "rule": "aggregating salaries, sending cash, or using a "
                            "sign-and-trade generated exception in a deal "
                            "hard-caps the team at the second apron"})
    if not state["over_apron1"]:
        out.append({"threshold": "first apron", "status": "trigger",
                    "rule": "acquiring a sign-and-traded player, using expanded "
                            "salary matching, or using the non-taxpayer mid-level "
                            "or bi-annual exception hard-caps the team at the "
                            "first apron"})
    if state["cap_room"] > 0:
        out.append({"threshold": "cap", "status": "active",
                    "rule": "operating with cap room; exceptions unavailable "
                            "until room is used"})
    return out


def roster_issues(roster_count: int) -> list[str]:
    if roster_count > 15:
        return [f"roster would be {roster_count} players - must trim to 15"]
    if roster_count < 14:
        return [f"roster would be {roster_count} players - must be at 14 "
                "within two weeks"]
    return []


def scenario_trace(pay_before: int, moves: list[dict[str, Any]],
                   start_detail: str = "committed payroll") -> dict[str, Any]:
    rows = [{"step": 0, "kind": "payroll", "detail": start_detail,
             "delta": 0, "payroll": pay_before}]
    pay = pay_before
    step = 1
    for move in moves:
        amount = int(move.get("amount") or 0)
        delta = -amount if move.get("kind") in ("trade_out", "waive") else amount
        pay += delta
        row = {"step": step, "kind": str(move.get("kind") or "move"),
               "detail": str(move.get("detail") or move.get("label") or ""),
               "delta": delta, "payroll": pay}
        for key in ("player", "dead_cap", "guaranteed", "stretch_years",
                    "stretched_amount", "stretched_dead_cap", "waiver_window",
                    "waiver_date", "waiver_date_defaulted", "estimate_basis",
                    "validation"):
            if key in move:
                row[key] = move[key]
        rows.append(row)
        step += 1
    return {"steps": rows, "pay_after": pay, "next_step": step}
