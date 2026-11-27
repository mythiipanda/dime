import re as _re
from typing import Any

CAP = {"cap": 164_961_000, "tax": 200_428_000,
       "apron1": 209_015_000, "apron2": 221_686_000}
CAP_GROWTH_ASSUMPTION = 0.07
EXPANDED_TPE_CUSHION = 9_096_000
EXPANDED_TPE_LOW_MAX = EXPANDED_TPE_CUSHION - 250_000
EXPANDED_TPE_MID_MAX = 4 * EXPANDED_TPE_LOW_MAX
FROZEN_PICK_OFFSET = 7


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
                           cap_room: int = 0) -> bool:
    if outgoing <= 0 or incoming <= outgoing:
        return False
    if cap_room > 0 and incoming <= outgoing + cap_room + 250_000:
        return False
    return True


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
        delta = -amount if move.get("kind") == "trade_out" else amount
        pay += delta
        rows.append({"step": step, "kind": str(move.get("kind") or "move"),
                     "detail": str(move.get("detail") or move.get("label") or ""),
                     "delta": delta, "payroll": pay})
        step += 1
    return {"steps": rows, "pay_after": pay, "next_step": step}
