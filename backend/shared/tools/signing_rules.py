from datetime import date as _date
from typing import Any

from .cap_rules import CAP, hard_cap_consequences

SIGNING_VALIDATION_VERSION = "v1"
SIGNING_MECHANISMS = (
    "auto", "cap_room", "bird", "early_bird", "non_bird", "ntmle",
    "tmle", "room_exception", "bae", "minimum", "rookie_scale",
    "second_round_pick",
)
SUPPORTED_MECHANISMS = ("minimum", "cap_room", "tmle", "ntmle", "bae")
AUTO_ORDER = ("minimum", "cap_room", "tmle", "ntmle", "bae")
EXCEPTION_RULES = {
    "ntmle": {
        "amount": 15_044_000, "max_years": 4, "used_key": "ntmle_used",
        "apron": "first apron", "label": "non-taxpayer mid-level exception",
        "refs": ["Art. VII §6(e)", "Art. VII §2(e)(2) row B"],
    },
    "tmle": {
        "amount": 6_064_000, "max_years": 2, "used_key": "tmle_used",
        "apron": "second apron", "label": "taxpayer mid-level exception",
        "refs": ["Art. VII §6(f)", "Art. VII §2(e)(2) row K"],
    },
    "bae": {
        "amount": 5_477_000, "max_years": 2, "used_key": "bae_used",
        "apron": "first apron", "label": "bi-annual exception",
        "refs": ["Art. VII §6(d)", "Art. VII §2(e)(2) row A"],
    },
}
MECHANISM_REFS = {
    "cap_room": ["Art. VII §2(b)(2)", "Art. IX §1"],
    "minimum": ["Art. II §6(a)", "Art. VII §6(i)"],
}
MINIMUM_SALARY_SCALE_2026_27 = {
    0: 1_357_763, 1: 2_185_116, 2: 2_449_421, 3: 2_537_526,
    4: 2_625_627, 5: 2_845_883, 6: 3_066_143, 7: 3_286_399,
    8: 3_506_659, 9: 3_524_115, 10: 3_876_529,
}
SIGNING_PROXY_DISCLOSURE = (
    "Approximation, not exact CBA signing legality: this result uses the "
    "warehouse salary ledger of listed player salaries only. It validates "
    "signing mechanism amount, duration, frequency, and hard-cap arithmetic "
    "where inputs are declared, but it does not calculate exact Team Salary "
    "or Apron Team Salary because performance bonuses, cap-hold and "
    "renouncement state, exception inventory and prior use, dead money, "
    "offer-sheet/tender state, contract subtype/timing flags, and official "
    "team-salary reconciliation are missing or estimated. Treat apron, room, "
    "and mechanism conclusions as screening estimates, not a final CBA "
    "legality determination."
)
BASE_MISSING_INPUTS = [
    "exact_apron_team_salary",
    "exception_use_ledger",
    "cap_hold_renouncement_state",
    "performance_bonus_amounts",
    "official_team_salary_reconciliation",
]
UNSUPPORTED_V1_MECHANISMS = {
    "bird": "Bird rights classification and prior-team evidence are outside signing validation v1",
    "early_bird": "Early Bird classification and average-player-salary inputs are outside signing validation v1",
    "non_bird": "non-Bird prior-team and prior-salary evidence are outside signing validation v1",
    "room_exception": "below-cap operating mode and room-exception availability are outside signing validation v1",
    "rookie_scale": "rookie scale and draft-rights inputs are outside signing validation v1",
    "second_round_pick": "second-round pick exception inputs are outside signing validation v1",
}


def _strict_integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def initial_exception_state(seed: dict[str, Any] | None = None) -> dict[str, Any]:
    state = {
        "ntmle_used": 0, "tmle_used": 0, "bae_used": 0, "room_used": 0,
        "bae_used_prior_cap_year": False, "operating_mode": "unknown",
    }
    if not isinstance(seed, dict):
        return state
    for key in ("ntmle_used", "tmle_used", "bae_used", "room_used"):
        value = _strict_integer(seed.get(key, 0))
        if value is not None and value >= 0:
            state[key] = value
    state["bae_used_prior_cap_year"] = bool(seed.get("bae_used_prior_cap_year", False))
    mode = str(seed.get("operating_mode") or "unknown").strip().lower()
    if mode in ("unknown", "over_cap", "below_cap"):
        state["operating_mode"] = mode
    return state


def normalize_signing_input(raw: Any) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(raw, dict):
        return None, ["signing move must be an object"]
    errors: list[str] = []
    amount = _strict_integer(raw.get("amount"))
    if amount is None or amount <= 0:
        errors.append("signing amount must be a positive integer")
        amount = 0
    years_defaulted = "years" not in raw
    years = _strict_integer(raw.get("years", 1))
    if years is None or years <= 0:
        errors.append("signing years must be a positive integer")
        years = 1
    mechanism = str(raw.get("mechanism") or "auto").strip().lower()
    mechanism = mechanism.replace("-", "_").replace(" ", "_")
    if mechanism not in SIGNING_MECHANISMS:
        errors.append(f"unknown signing mechanism '{mechanism}'")
    bonus_declared = "unlikely_bonus" in raw
    unlikely_bonus = _strict_integer(raw.get("unlikely_bonus", 0))
    if unlikely_bonus is None or unlikely_bonus < 0:
        errors.append("unlikely_bonus must be a non-negative integer")
        unlikely_bonus = 0
    yos = None
    if "years_of_service" in raw and raw.get("years_of_service") is not None:
        yos = _strict_integer(raw.get("years_of_service"))
        if yos is None or yos < 0:
            errors.append("years_of_service must be a non-negative integer")
            yos = None
    prior_salary = None
    if "prior_salary" in raw and raw.get("prior_salary") is not None:
        prior_salary = _strict_integer(raw.get("prior_salary"))
        if prior_salary is None or prior_salary <= 0:
            errors.append("prior_salary must be a positive integer")
            prior_salary = None
    player = str(raw.get("player") or raw.get("label") or " signing").strip()
    signing_date = str(raw.get("signing_date") or "")
    inseason_timing = False
    if signing_date:
        try:
            parsed_signing_date = _date.fromisoformat(signing_date)
            inseason_timing = parsed_signing_date.month not in (7, 8, 9)
        except ValueError:
            errors.append("signing_date must be YYYY-MM-DD")
    move = {
        "player": player, "amount": amount or 0, "years": years or 1,
        "mechanism": mechanism, "years_defaulted": years_defaulted,
        "unlikely_bonus": unlikely_bonus or 0,
        "unlikely_bonus_declared": bonus_declared,
        "years_of_service": yos, "prior_salary": prior_salary,
        "signing_date": signing_date,
        "inseason_timing_approximation": inseason_timing,
    }
    return move, errors


def minimum_salary(years_of_service: int, season: str = "2026-27") -> int | None:
    if season != "2026-27":
        return None
    return MINIMUM_SALARY_SCALE_2026_27[min(10, max(0, years_of_service))]


def _maximum_salary(move: dict[str, Any], lines: dict[str, Any]) -> int | None:
    yos = move.get("years_of_service")
    if yos is None:
        return None
    rate = 0.25 if yos < 7 else 0.30 if yos < 10 else 0.35
    tier_max = int(round(lines["cap"] * rate))
    prior = move.get("prior_salary")
    if prior:
        return max(tier_max, int(round(prior * 1.05)))
    return tier_max


def _generic_checks(move: dict[str, Any], lines: dict[str, Any],
                    season: str) -> tuple[dict[str, str], list[str], list[str]]:
    checks: dict[str, str] = {}
    failures: list[str] = []
    missing: list[str] = []
    amount = move["amount"]
    amount_with_bonus = amount + move["unlikely_bonus"]
    if move["years"] > 4:
        checks["term"] = "failed"
        failures.append("new external signing term cannot exceed four seasons")
    else:
        checks["term"] = "passed"
    maximum = _maximum_salary(move, lines)
    if maximum is None:
        checks["maximum_salary"] = "unknown"
        missing.append("years_of_service")
    elif amount_with_bonus > maximum:
        checks["maximum_salary"] = "failed"
        failures.append(
            f"first-year salary plus unlikely bonuses (${amount_with_bonus:,}) "
            f"exceeds the player's approximate Article II maximum (${maximum:,})")
    else:
        checks["maximum_salary"] = "passed"
    yos = move.get("years_of_service")
    minimum = minimum_salary(yos, season) if yos is not None else None
    if yos is None or minimum is None:
        checks["minimum_salary"] = "unknown"
        if "years_of_service" not in missing:
            missing.append("years_of_service")
    elif amount < minimum:
        checks["minimum_salary"] = "failed"
        failures.append(
            f"first-year salary (${amount:,}) is below the applicable minimum "
            f"salary (${minimum:,})")
    else:
        checks["minimum_salary"] = "passed"
    if move["unlikely_bonus_declared"]:
        checks["unlikely_bonus"] = "declared"
    else:
        checks["unlikely_bonus"] = "not_represented"
        missing.append("unlikely_bonus_amount")
    return checks, failures, missing


def _candidate(mechanism: str, ok: bool, reason: str = "", *,
               unknown: bool = False, hard_cap_trigger: str = "",
               exception_remaining: int | None = None,
               violations: list[str] | None = None,
               refs: list[str] | None = None) -> dict[str, Any]:
    return {
        "mechanism": mechanism, "ok": ok, "reason": reason,
        "unknown": unknown, "hard_cap_trigger": hard_cap_trigger,
        "exception_remaining": exception_remaining,
        "violations": list(violations or []), "refs": list(refs or []),
    }


def _cap_room_candidate(move: dict[str, Any], payroll_before: int,
                        lines: dict[str, Any]) -> dict[str, Any]:
    room = max(0, lines["cap"] - payroll_before)
    if move["amount"] > room:
        return _candidate(
            "cap_room", False,
            f"insufficient cap room: first-year salary ${move['amount']:,} "
            f"exceeds available room ${room:,}; team has no cap room for this signing",
            refs=MECHANISM_REFS["cap_room"])
    return _candidate(
        "cap_room", True, refs=MECHANISM_REFS["cap_room"])


def _minimum_candidate(move: dict[str, Any], season: str) -> dict[str, Any]:
    refs = MECHANISM_REFS["minimum"]
    if move["years"] > 2:
        return _candidate(
            "minimum", False,
            "minimum Player Salary Exception contracts may not exceed two seasons",
            refs=refs)
    yos = move.get("years_of_service")
    if yos is None:
        largest = MINIMUM_SALARY_SCALE_2026_27[10]
        if move["amount"] > largest:
            return _candidate(
                "minimum", False,
                f"amount ${move['amount']:,} exceeds the highest 2026-27 minimum "
                f"salary (${largest:,})", refs=refs)
        return _candidate(
            "minimum", False,
            "years_of_service is missing, so exact minimum-salary eligibility cannot be established",
            unknown=True, refs=refs)
    minimum = minimum_salary(yos, season)
    if minimum is None:
        return _candidate(
            "minimum", False,
            f"minimum salary scale is unavailable for {season}", unknown=True,
            refs=refs)
    if move["amount"] != minimum or move["unlikely_bonus"]:
        return _candidate(
            "minimum", False,
            f"minimum exception requires exactly the applicable minimum salary "
            f"(${minimum:,}) with no bonuses", refs=refs)
    return _candidate("minimum", True, refs=refs)


def _exception_candidate(mechanism: str, move: dict[str, Any], team: str,
                         payroll_before: int, lines: dict[str, Any],
                         state: dict[str, Any]) -> dict[str, Any]:
    rule = EXCEPTION_RULES[mechanism]
    refs = list(rule["refs"])
    used_key = str(rule["used_key"])
    use_amount = move["amount"] + move["unlikely_bonus"]
    remaining = int(rule["amount"]) - int(state.get(used_key) or 0)
    if use_amount > remaining:
        return _candidate(
            mechanism, False,
            f"amount ${use_amount:,} exceeds the {rule['label']} ceiling "
            f"(${int(rule['amount']):,}; ${remaining:,} remaining)",
            exception_remaining=max(0, remaining), refs=refs)
    if move["years"] > int(rule["max_years"]):
        seasons = "four seasons" if rule["max_years"] == 4 else "two seasons"
        return _candidate(
            mechanism, False,
            f"{rule['label']} contracts may not exceed {seasons}",
            exception_remaining=remaining, refs=refs)
    if int(state.get("room_used") or 0) > 0:
        return _candidate(
            mechanism, False,
            f"{rule['label']} is unavailable after room exception use in the same cap year",
            exception_remaining=remaining, refs=refs)
    if mechanism == "bae" and state.get("bae_used_prior_cap_year"):
        return _candidate(
            mechanism, False,
            "bi-annual exception may not be used in consecutive Salary Cap Years",
            exception_remaining=remaining, refs=refs)
    post_move = payroll_before + move["amount"]
    if mechanism == "tmle" and post_move <= lines["apron1"]:
        return _candidate(
            mechanism, False,
            "taxpayer mid-level use requires post-signing payroll proxy to exceed the first apron",
            exception_remaining=remaining, refs=refs)
    consequence = hard_cap_consequences(
        team, post_move, used_ntmle=mechanism == "ntmle",
        used_bae=mechanism == "bae", used_tmle=mechanism == "tmle",
        lines=lines)
    trigger = str(rule["apron"])
    if consequence["violations"]:
        apron = consequence["violations"][0]
        line_key = "apron1" if apron == "first apron" else "apron2"
        return _candidate(
            mechanism, False,
            f"{team} cannot use the {rule['label']} because post-signing payroll "
            f"proxy (${post_move:,}) would exceed the {apron} "
            f"(${lines[line_key]:,}); the signing is prohibited",
            hard_cap_trigger=trigger, exception_remaining=remaining,
            violations=list(consequence["violations"]), refs=refs)
    return _candidate(
        mechanism, True, hard_cap_trigger=trigger,
        exception_remaining=remaining - use_amount, refs=refs)


def _active_hard_cap_failure(payroll_after: int, active_hard_caps: list[str],
                             lines: dict[str, Any]) -> str:
    active = set(active_hard_caps or [])
    if "first apron" in active and payroll_after > lines["apron1"]:
        return (f"post-signing payroll proxy (${payroll_after:,}) exceeds the active "
                f"first apron hard cap (${lines['apron1']:,})")
    if "second apron" in active and payroll_after > lines["apron2"]:
        return (f"post-signing payroll proxy (${payroll_after:,}) exceeds the active "
                f"second apron hard cap (${lines['apron2']:,})")
    return ""


def _candidate_map(move: dict[str, Any], team: str, payroll_before: int,
                   lines: dict[str, Any], state: dict[str, Any], season: str,
                   active_hard_caps: list[str]) -> dict[str, dict[str, Any]]:
    post_move = payroll_before + move["amount"]
    active_failure = _active_hard_cap_failure(post_move, active_hard_caps, lines)
    candidates = {
        "minimum": _minimum_candidate(move, season),
        "cap_room": _cap_room_candidate(move, payroll_before, lines),
    }
    for mechanism in ("tmle", "ntmle", "bae"):
        candidates[mechanism] = _exception_candidate(
            mechanism, move, team, payroll_before, lines, state)
    if active_failure:
        for mechanism, candidate in candidates.items():
            if candidate["ok"]:
                candidates[mechanism] = _candidate(
                    mechanism, False, active_failure,
                    hard_cap_trigger=candidate["hard_cap_trigger"],
                    exception_remaining=candidate["exception_remaining"],
                    refs=candidate["refs"])
    return candidates


def _unsupported_candidate(mechanism: str) -> dict[str, Any]:
    return _candidate(
        mechanism, False,
        UNSUPPORTED_V1_MECHANISMS.get(mechanism, "mechanism is outside signing validation v1"),
        unknown=True)


def _result(move: dict[str, Any], *, outcome: str, selected: str | None,
            inference: str, candidates: dict[str, dict[str, Any]],
            evaluation: dict[str, Any] | None, blocking: list[str],
            checks: dict[str, str], missing: list[str],
            payroll_before: int, lines: dict[str, Any],
            input_errors: list[str] | None = None) -> dict[str, Any]:
    evaluation = evaluation or {}
    post_move = payroll_before + move["amount"]
    trigger = str(evaluation.get("hard_cap_trigger") or "")
    apron_key = "apron2" if trigger == "second apron" else "apron1"
    legal = outcome in ("legal_exact", "legal_approximation")
    rejected = [
        {"mechanism": mechanism, "reason": candidate["reason"]}
        for mechanism, candidate in candidates.items()
        if not candidate["ok"] and candidate["reason"] and mechanism != selected
    ]
    missing_inputs = list(dict.fromkeys(BASE_MISSING_INPUTS + missing))
    advisory: list[str] = []
    if not move["unlikely_bonus_declared"]:
        advisory.append("unlikely bonuses are not represented; ceilings use declared salary only")
    if move.get("inseason_timing_approximation"):
        advisory.append("in-season exception decay and minimum-salary proration are not implemented; timing is a full-season approximation")
    if move["years_defaulted"]:
        advisory.append("years omitted; defaulted to 1 for compatibility")
    if selected == "minimum" and move["years"] > 1:
        advisory.append("later-year exact minimum salary amounts are not represented in signing validation v1")
        missing_inputs.append("later_year_minimum_salary_schedule")
    use_amount = move["amount"] + move["unlikely_bonus"]
    exception_use = None
    if legal and selected in EXCEPTION_RULES:
        exception_use = {"mechanism": selected, "amount": use_amount}
    return {
        "kind": "signing", "player": move["player"], "amount": move["amount"],
        "unlikely_bonus": move["unlikely_bonus"], "years": move["years"],
        "years_defaulted": move["years_defaulted"],
        "mechanism_input": move["mechanism"], "mechanism_selected": selected,
        "mechanism_inference": inference, "outcome": outcome, "legal": legal,
        "legality_confidence": "approximation" if legal else "unknown" if outcome == "unknown" else "not_applicable",
        "hard_cap_trigger": trigger,
        "hard_cap_violations": list(evaluation.get("violations") or []),
        "post_move_payroll": post_move,
        "post_move_apron_room": lines[apron_key] - post_move,
        "exception_remaining": evaluation.get("exception_remaining"),
        "exception_use": exception_use,
        "candidate_mechanisms": list(SUPPORTED_MECHANISMS),
        "legal_candidates": [mechanism for mechanism, candidate in candidates.items() if candidate["ok"]],
        "rejected_candidates": rejected,
        "blocking_issues": list(blocking), "advisory_issues": advisory,
        "missing_inputs": list(dict.fromkeys(missing_inputs)),
        "validation_checks": checks,
        "cba_refs": list(evaluation.get("refs") or []),
        "salary_basis": "approximate_salary_ledger_not_exact_apron_team_salary",
        "ats_exact": False,
        "signing_validation_version": SIGNING_VALIDATION_VERSION,
        "signing_proxy_disclosure": SIGNING_PROXY_DISCLOSURE,
        "input_errors": list(input_errors or []),
    }


def _input_error_result(raw: Any, errors: list[str]) -> dict[str, Any]:
    move = {"player": str((raw or {}).get("player") or (raw or {}).get("label") or "signing")
            if isinstance(raw, dict) else "signing",
            "amount": 0, "years": 0, "mechanism": "unknown",
            "years_defaulted": False, "unlikely_bonus": 0,
            "unlikely_bonus_declared": False}
    return _result(
        move, outcome="unknown", selected=None, inference="input_error",
        candidates={}, evaluation=None, blocking=errors, checks={},
        missing=[], payroll_before=0, lines=dict(CAP), input_errors=errors)


def _auto_choice(candidates: dict[str, dict[str, Any]], payroll_before: int,
                 lines: dict[str, Any], state: dict[str, Any]
                 ) -> tuple[str | None, str, list[str], str]:
    no_hard = [mechanism for mechanism in ("minimum", "cap_room")
               if candidates[mechanism]["ok"]]
    if no_hard:
        return no_hard[0], "least_restrictive_legal", [], ""
    if payroll_before < lines["cap"] and state.get("operating_mode") == "unknown":
        return None, "explicit_required", [
            "below-cap operating mode is unknown; auto inference requires an explicit signing mechanism"
        ], ""
    hard = [mechanism for mechanism in ("tmle", "ntmle", "bae")
            if candidates[mechanism]["ok"]]
    if len(hard) == 1:
        return hard[0], "least_restrictive_legal", [], ""
    if "ntmle" in hard and "tmle" not in hard:
        return "ntmle", "least_restrictive_legal", [], (
            "ntmle preferred over bae because both use the first-apron ceiling "
            "but bae carries a consecutive-year frequency restriction")
    if hard:
        return None, "explicit_required", [
            "multiple hard-capped signing mechanisms are legal with different tradeoffs; explicit mechanism required"
        ], ""
    return None, "none", ["no valid signing mechanism under the declared scenario state"], ""


def validate_signing(raw: Any, *, team: str, payroll_before: int,
                     lines: dict[str, Any] | None = None,
                     exception_state: dict[str, Any] | None = None,
                     active_hard_caps: list[str] | None = None,
                     season: str = "2026-27") -> dict[str, Any]:
    lines = dict(lines or CAP)
    move, input_errors = normalize_signing_input(raw)
    if move is None or input_errors:
        return _input_error_result(raw, input_errors)
    state_seed = dict(exception_state or {})
    if isinstance(raw, dict) and isinstance(raw.get("exception_state"), dict):
        state_seed.update(raw["exception_state"])
    state = initial_exception_state(state_seed)
    checks, generic_failures, missing = _generic_checks(move, lines, season)
    candidates = _candidate_map(
        move, team, payroll_before, lines, state, season,
        list(active_hard_caps or []))
    mechanism = move["mechanism"]
    if generic_failures:
        return _result(
            move, outcome="illegal", selected=None, inference="not_applicable",
            candidates={}, evaluation=None, blocking=generic_failures,
            checks=checks, missing=missing, payroll_before=payroll_before,
            lines=lines)
    if mechanism == "auto":
        selected, inference, blocking, _tie_breaker = _auto_choice(
            candidates, payroll_before, lines, state)
        if selected:
            evaluation = candidates[selected]
            return _result(
                move, outcome="legal_approximation", selected=selected,
                inference=inference, candidates=candidates, evaluation=evaluation,
                blocking=[], checks=checks, missing=missing,
                payroll_before=payroll_before, lines=lines)
        outcome = "unknown" if inference == "explicit_required" else "illegal"
        return _result(
            move, outcome=outcome, selected=None, inference=inference,
            candidates=candidates, evaluation=None, blocking=blocking,
            checks=checks, missing=missing, payroll_before=payroll_before,
            lines=lines)
    evaluation = candidates.get(mechanism) or _unsupported_candidate(mechanism)
    candidates.setdefault(mechanism, evaluation)
    if evaluation["ok"]:
        preferred = next((candidate for candidate in AUTO_ORDER
                          if candidates.get(candidate, {}).get("ok")), None)
        result = _result(
            move, outcome="legal_approximation", selected=mechanism,
            inference="explicit", candidates=candidates, evaluation=evaluation,
            blocking=[], checks=checks, missing=missing,
            payroll_before=payroll_before, lines=lines)
        if preferred and preferred != mechanism:
            result["less_restrictive_alternative"] = preferred
        return result
    outcome = "unknown" if evaluation["unknown"] else "illegal"
    return _result(
        move, outcome=outcome, selected=None, inference="explicit",
        candidates=candidates, evaluation=evaluation,
        blocking=[evaluation["reason"]], checks=checks, missing=missing,
        payroll_before=payroll_before, lines=lines)


def consume_signing_exception(state: dict[str, Any], validation: dict[str, Any]
                              ) -> dict[str, Any]:
    out = initial_exception_state(state)
    use = validation.get("exception_use") or {}
    mechanism = use.get("mechanism")
    if validation.get("legal") and mechanism in EXCEPTION_RULES:
        key = str(EXCEPTION_RULES[mechanism]["used_key"])
        out[key] = int(out.get(key) or 0) + int(use.get("amount") or 0)
    return out
