from datetime import date as _date
from fractions import Fraction
from typing import Any

from .cap_rules import (
    CAP,
    CAP_GROWTH_ASSUMPTION,
    active_hard_cap_failure,
    hard_cap_consequences,
)

SIGNING_VALIDATION_VERSION = "v1"
SIGNING_MECHANISMS = (
    "auto", "cap_room", "bird", "early_bird", "non_bird", "ntmle",
    "tmle", "room_exception", "bae", "minimum", "rookie_scale",
    "second_round_pick",
)
SUPPORTED_MECHANISMS = ("minimum", "cap_room", "room_exception", "tmle", "ntmle", "bae")
AUTO_ORDER = ("minimum", "cap_room", "room_exception", "tmle", "ntmle", "bae")
EXCEPTION_RULES = {
    "room_exception": {
        "amount": 9_366_000, "max_years": 3, "used_key": "room_used",
        "apron": "", "label": "mid-level exception for room teams",
        "cap_percentage": 0.05678,
        "refs": ["Art. VII §6(g)"],
    },
    "ntmle": {
        "amount": 15_044_000, "max_years": 4, "used_key": "ntmle_used",
        "apron": "first apron", "label": "non-taxpayer mid-level exception",
        "cap_percentage": 0.0912,
        "refs": ["Art. VII §6(e)", "Art. VII §2(e)(2) row B"],
    },
    "tmle": {
        "amount": 6_064_000, "max_years": 2, "used_key": "tmle_used",
        "apron": "second apron", "label": "taxpayer mid-level exception",
        "cap_percentage": None,
        "refs": ["Art. VII §6(f)", "Art. VII §2(e)(2) row K"],
    },
    "bae": {
        "amount": 5_477_000, "max_years": 2, "used_key": "bae_used",
        "apron": "first apron", "label": "bi-annual exception",
        "cap_percentage": 0.0332,
        "refs": ["Art. VII §6(d)", "Art. VII §2(e)(2) row A"],
    },
}
WAREHOUSE_EXCEPTION_AMOUNT_BASIS = (
    "warehouse silver_cap_room projected estimate; not official cba amounts")
FALLBACK_EXCEPTION_AMOUNT_BASIS = (
    "warehouse-style exact cap-growth projection; not official cba amounts")
OFFICIAL_EXCEPTION_AMOUNT_BASIS = "2026-27 official cba amounts"
MECHANISM_REFS = {
    "cap_room": ["Art. VII §2(b)(2)", "Art. IX §1"],
    "minimum": ["Art. II §6(a)", "Art. VII §6(i)"],
}
MINIMUM_SALARY_SCALE_2023_24 = {
    0: 1_119_563, 1: 1_801_769, 2: 2_019_706, 3: 2_092_354,
    4: 2_165_000, 5: 2_346_614, 6: 2_528_233, 7: 2_709_849,
    8: 2_891_467, 9: 2_905_861, 10: 3_196_448,
}
MINIMUM_SECOND_YEAR_SCALE_2023_24 = {
    1: 1_891_857, 2: 2_120_693, 3: 2_196_970, 4: 2_273_252,
    5: 2_463_946, 6: 2_654_644, 7: 2_845_342, 8: 3_036_040,
    9: 3_051_153, 10: 3_356_271,
}
MINIMUM_CAP_BY_START_YEAR = {
    2023: 136_021_000, 2024: 140_588_000,
    2025: 154_647_000, 2026: int(CAP["cap"]),
}
MINIMUM_PROJECTED_CAP_2027 = 181_457_100
MINIMUM_PROJECTED_CAP_GROWTH = 1 + Fraction(str(CAP_GROWTH_ASSUMPTION))
INPUT_ERROR_EXCEPTION_AMOUNT_BASIS = (
    "unknown; input validation failed before exception amount resolution")
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


def _positive_fraction(value: Any) -> Fraction | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, Fraction):
        out = value
    elif isinstance(value, int):
        out = Fraction(value, 1)
    elif isinstance(value, float):
        out = Fraction(str(value))
    else:
        return None
    return out if out > 0 else None


def _scaled_whole_dollars(base_amount: int, cap_amount: Any,
                          base_cap: Any, rounding: str) -> int | None:
    base = _positive_fraction(base_amount)
    cap = _positive_fraction(cap_amount)
    anchor = _positive_fraction(base_cap)
    if base is None or cap is None or anchor is None:
        return None
    scaled = base * cap / anchor
    if rounding == "nearest_half_up":
        return int(scaled + Fraction(1, 2))
    return int(scaled)


def scaled_exception_rules(lines: dict[str, Any], season: str = "2026-27",
                           exception_amounts: dict[str, int] | None = None,
                           exception_amounts_source: str = "supplied season exception amounts"
                           ) -> dict[str, dict[str, Any]]:
    cap_amount = lines["cap"]
    overrides = exception_amounts or {}
    override_basis = exception_amounts_source
    scaled: dict[str, dict[str, Any]] = {}
    for mechanism, base in EXCEPTION_RULES.items():
        rule = dict(base)
        if season == "2026-27":
            rule["amount"] = int(base["amount"])
            rule["amount_basis"] = OFFICIAL_EXCEPTION_AMOUNT_BASIS
        elif mechanism in overrides:
            rule["amount"] = int(overrides[mechanism])
            rule["amount_basis"] = override_basis
        else:
            amount = _scaled_whole_dollars(
                int(base["amount"]), cap_amount, int(CAP["cap"]), "floor")
            rule["amount"] = amount if amount is not None else int(base["amount"])
            rule["amount_basis"] = FALLBACK_EXCEPTION_AMOUNT_BASIS
        scaled[mechanism] = rule
    return scaled


def normalize_exception_amounts_input(raw: Any) -> tuple[dict[str, int] | None, list[str]]:
    if raw is None:
        return {}, []
    if not isinstance(raw, dict):
        return None, ["exception_amounts must be an object"]
    errors: list[str] = []
    amounts: dict[str, int] = {}
    for key, value in raw.items():
        if key not in EXCEPTION_RULES:
            errors.append(f"unknown exception_amounts key '{key}'")
            continue
        parsed = _strict_integer(value)
        if parsed is None or parsed <= 0:
            errors.append(f"exception_amounts.{key} must be a positive integer")
        else:
            amounts[key] = parsed
    return (None if errors else amounts), errors


def _normalize_salary_schedule(raw: Any, amount: int, years: int) -> tuple[list[int] | None, list[str]]:
    if raw is None:
        return None, []
    if not isinstance(raw, (list, tuple)):
        return None, ["salary_schedule must be a list of positive integer salaries"]
    errors: list[str] = []
    schedule: list[int] = []
    for value in raw:
        parsed = _strict_integer(value)
        if parsed is None or parsed <= 0:
            errors.append("salary_schedule entries must be positive integers")
            continue
        schedule.append(parsed)
    if errors:
        return schedule, errors
    if len(schedule) != years:
        errors.append("salary_schedule length must equal signing years")
    if schedule and amount and schedule[0] != amount:
        errors.append("salary_schedule first year must equal signing amount")
    return schedule, errors


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


EXCEPTION_STATE_NUMERIC_KEYS = ("ntmle_used", "tmle_used", "bae_used", "room_used")
EXCEPTION_STATE_KEYS = EXCEPTION_STATE_NUMERIC_KEYS + (
    "bae_used_prior_cap_year", "operating_mode")


def normalize_exception_state_input(raw: Any) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(raw, dict):
        return None, ["exception_state must be an object"]
    errors: list[str] = []
    state = initial_exception_state()
    for key in raw:
        if key not in EXCEPTION_STATE_KEYS:
            errors.append(f"unknown exception_state key '{key}'")
    for key in EXCEPTION_STATE_NUMERIC_KEYS:
        if key not in raw:
            continue
        value = _strict_integer(raw.get(key))
        if value is None or value < 0:
            errors.append(f"exception_state.{key} must be a non-negative integer")
        else:
            state[key] = value
    if "bae_used_prior_cap_year" in raw:
        if isinstance(raw.get("bae_used_prior_cap_year"), bool):
            state["bae_used_prior_cap_year"] = bool(raw["bae_used_prior_cap_year"])
        else:
            errors.append("exception_state.bae_used_prior_cap_year must be a boolean")
    if "operating_mode" in raw:
        mode = str(raw.get("operating_mode") or "").strip().lower()
        if mode in ("unknown", "over_cap", "below_cap"):
            state["operating_mode"] = mode
        else:
            errors.append("exception_state.operating_mode must be unknown, over_cap, or below_cap")
    return (None if errors else state), errors


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
    salary_schedule, schedule_errors = _normalize_salary_schedule(
        raw.get("salary_schedule"), amount, years)
    errors.extend(schedule_errors)
    if salary_schedule is not None and mechanism != "minimum":
        errors.append("salary_schedule exact annual shape validation is supported only for mechanism=minimum in signing validation v1")
    if raw.get("prior_team") not in (None, ""):
        errors.append("prior_team cannot be consumed by signing validation v1; omit it or use a supported mechanism input")
    status = str(raw.get("free_agent_status") or "").strip().lower()
    if status and status != "unknown":
        errors.append("free_agent_status cannot be consumed by signing validation v1 because Bird-family validation is unsupported")
    if bool(raw.get("replaces_cap_hold")):
        errors.append("replaces_cap_hold requires exact cap-hold ledger state and is unsupported in signing validation v1")
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
        "salary_schedule": salary_schedule,
        "signing_date": signing_date,
        "inseason_timing_approximation": inseason_timing,
    }
    return move, errors


def _season_start_year(season: str) -> int | None:
    try:
        return int(str(season)[:4])
    except ValueError:
        return None


def _projected_minimum_cap(start_year: int) -> int:
    cap = MINIMUM_PROJECTED_CAP_2027
    for _ in range(2028, start_year + 1):
        cap = int(Fraction(cap) * MINIMUM_PROJECTED_CAP_GROWTH + Fraction(1, 2))
    return cap


def _minimum_cap_path(season: str, lines: dict[str, Any] | None
                      ) -> list[Fraction] | None:
    target_year = _season_start_year(season)
    if target_year is None or target_year < 2023:
        return None
    target_cap = _positive_fraction((lines or {}).get("cap"))
    path: list[Fraction] = []
    for year in range(2023, target_year + 1):
        actual = MINIMUM_CAP_BY_START_YEAR.get(year)
        if actual is not None:
            cap = Fraction(actual, 1)
        elif year == target_year:
            if target_cap is None:
                return None
            cap = target_cap
        elif year >= 2027:
            cap = Fraction(_projected_minimum_cap(year), 1)
        else:
            return None
        path.append(cap)
    return path


def _chained_minimum_scale(base_scale: dict[int, int],
                           cap_path: list[Fraction]) -> dict[int, int] | None:
    scale = dict(base_scale)
    for previous_cap, cap in zip(cap_path, cap_path[1:]):
        chained: dict[int, int] = {}
        for yos, amount in scale.items():
            scaled = _scaled_whole_dollars(
                amount, cap, previous_cap, "nearest_half_up")
            if scaled is None:
                return None
            chained[yos] = scaled
        scale = chained
    return scale


def _minimum_scale_for_season(base_scale: dict[int, int], season: str,
                              lines: dict[str, Any] | None) -> dict[int, int] | None:
    cap_path = _minimum_cap_path(season, lines)
    if cap_path is None:
        return None
    return _chained_minimum_scale(base_scale, cap_path)


def minimum_salary(years_of_service: int, season: str = "2026-27",
                   lines: dict[str, Any] | None = None) -> int | None:
    scale = _minimum_scale_for_season(
        MINIMUM_SALARY_SCALE_2023_24, season, lines)
    if scale is None:
        return None
    return scale[min(10, max(0, years_of_service))]


def second_year_minimum_salary(years_of_service: int, season: str,
                               lines: dict[str, Any]) -> int | None:
    scale = _minimum_scale_for_season(
        MINIMUM_SECOND_YEAR_SCALE_2023_24, season, lines)
    if scale is None:
        return None
    return scale[min(10, max(1, years_of_service + 1))]


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
    minimum = minimum_salary(yos, season, lines) if yos is not None else None
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
               refs: list[str] | None = None,
               mode_dependent: bool = False,
               exception_amount: int | None = None) -> dict[str, Any]:
    return {
        "mechanism": mechanism, "ok": ok, "reason": reason,
        "unknown": unknown, "hard_cap_trigger": hard_cap_trigger,
        "exception_remaining": exception_remaining,
        "violations": list(violations or []), "refs": list(refs or []),
        "mode_dependent": mode_dependent,
        "exception_amount": exception_amount,
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


def _minimum_schedule_failure(move: dict[str, Any], season: str,
                              lines: dict[str, Any]) -> str:
    schedule = move.get("salary_schedule")
    if move["years"] != 2 or not schedule:
        return ""
    expected = second_year_minimum_salary(
        int(move["years_of_service"]), season, lines)
    if expected is None:
        return f"second-year minimum salary scale is unavailable for {season}"
    if schedule[1] != expected:
        return (f"minimum exception requires the second-year salary to be exactly "
                f"the applicable minimum (${expected:,}); salary_schedule provides "
                f"${schedule[1]:,}")
    return ""


def _minimum_candidate(move: dict[str, Any], season: str,
                       lines: dict[str, Any]) -> dict[str, Any]:
    refs = MECHANISM_REFS["minimum"]
    if move["years"] > 2:
        return _candidate(
            "minimum", False,
            "minimum Player Salary Exception contracts may not exceed two seasons",
            refs=refs)
    yos = move.get("years_of_service")
    if yos is None:
        largest = minimum_salary(10, season, lines)
        if largest is not None and move["amount"] > largest:
            return _candidate(
                "minimum", False,
                f"amount ${move['amount']:,} exceeds the highest {season} minimum "
                f"salary (${largest:,})", refs=refs)
        return _candidate(
            "minimum", False,
            "years_of_service is missing, so exact minimum-salary eligibility cannot be established",
            unknown=True, refs=refs)
    minimum = minimum_salary(yos, season, lines)
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
    schedule_failure = _minimum_schedule_failure(move, season, lines)
    if schedule_failure:
        return _candidate("minimum", False, schedule_failure, refs=refs)
    return _candidate("minimum", True, refs=refs)


def _mode_failure(mechanism: str, rule: dict[str, Any], payroll_before: int,
                  lines: dict[str, Any], state: dict[str, Any],
                  remaining: int) -> dict[str, Any] | None:
    mode = str(state.get("operating_mode") or "unknown")
    refs = list(rule["refs"])
    if mechanism == "room_exception":
        if mode == "below_cap":
            return None
        reason = "mid-level exception for room teams is available only in a declared below-cap operating mode"
        return _candidate(
            mechanism, False, reason, unknown=mode == "unknown",
            exception_remaining=remaining, refs=refs,
            mode_dependent=mode == "unknown",
            exception_amount=int(rule["amount"]))
    if mode == "below_cap":
        return _candidate(
            mechanism, False,
            f"{rule['label']} is unavailable because the declared below-cap operating mode uses room rather than over-cap exceptions",
            exception_remaining=remaining, refs=refs,
            exception_amount=int(rule["amount"]))
    if mode == "unknown" and payroll_before < lines["cap"]:
        return _candidate(
            mechanism, False,
            f"below-cap operating mode is unknown, so {rule['label']} availability cannot be established",
            unknown=True, exception_remaining=remaining, refs=refs,
            mode_dependent=True, exception_amount=int(rule["amount"]))
    return None


def _exception_candidate(mechanism: str, move: dict[str, Any], team: str,
                         payroll_before: int, lines: dict[str, Any],
                         state: dict[str, Any], season: str,
                         exception_amounts: dict[str, int],
                         team_salary_before: int | None = None) -> dict[str, Any]:
    rule = scaled_exception_rules(
        lines, season=season, exception_amounts=exception_amounts)[mechanism]
    refs = list(rule["refs"])
    used_key = str(rule["used_key"])
    use_amount = move["amount"] + move["unlikely_bonus"]
    remaining = int(rule["amount"]) - int(state.get(used_key) or 0)
    capacity = int(rule["amount"])
    if use_amount > remaining:
        return _candidate(
            mechanism, False,
            f"amount ${use_amount:,} exceeds the {rule['label']} ceiling "
            f"(${capacity:,}; ${remaining:,} remaining)",
            exception_remaining=max(0, remaining), refs=refs,
            exception_amount=capacity)
    if move["years"] > int(rule["max_years"]):
        season_words = {2: "two seasons", 3: "three seasons", 4: "four seasons"}
        seasons = season_words.get(int(rule["max_years"]), f"{rule['max_years']} seasons")
        return _candidate(
            mechanism, False,
            f"{rule['label']} contracts may not exceed {seasons}",
            exception_remaining=remaining, refs=refs,
            exception_amount=capacity)
    if mechanism == "room_exception" and any(
            int(state.get(key) or 0) > 0 for key in ("ntmle_used", "tmle_used", "bae_used")):
        return _candidate(
            mechanism, False,
            "mid-level exception for room teams is unavailable after BAE, NTMLE, or TMLE use in the same cap year",
            exception_remaining=remaining, refs=refs,
            exception_amount=capacity)
    if mechanism != "room_exception" and int(state.get("room_used") or 0) > 0:
        return _candidate(
            mechanism, False,
            f"{rule['label']} is unavailable after room exception use in the same cap year",
            exception_remaining=remaining, refs=refs,
            exception_amount=capacity)
    if mechanism == "bae" and state.get("bae_used_prior_cap_year"):
        return _candidate(
            mechanism, False,
            "bi-annual exception may not be used in consecutive Salary Cap Years",
            exception_remaining=remaining, refs=refs,
            exception_amount=capacity)
    post_move = payroll_before + move["amount"]
    if mechanism == "tmle" and post_move <= lines["apron1"]:
        return _candidate(
            mechanism, False,
            "taxpayer mid-level use requires post-signing payroll proxy to exceed the first apron",
            exception_remaining=remaining, refs=refs,
            exception_amount=capacity)
    room_basis = payroll_before if team_salary_before is None else int(team_salary_before)
    mode_failure = _mode_failure(
        mechanism, rule, room_basis, lines, state, remaining)
    if mode_failure is not None:
        return mode_failure
    trigger = str(rule["apron"])
    if not trigger:
        return _candidate(
            mechanism, True, exception_remaining=remaining - use_amount,
            refs=refs, exception_amount=capacity)
    consequence = hard_cap_consequences(
        team, post_move, used_ntmle=mechanism == "ntmle",
        used_bae=mechanism == "bae", used_tmle=mechanism == "tmle",
        lines=lines)
    if consequence["violations"]:
        apron = consequence["violations"][0]
        line_key = "apron1" if apron == "first apron" else "apron2"
        return _candidate(
            mechanism, False,
            f"{team} cannot use the {rule['label']} because post-signing payroll "
            f"proxy (${post_move:,}) would exceed the {apron} "
            f"(${lines[line_key]:,}); the signing is prohibited",
            hard_cap_trigger=trigger, exception_remaining=remaining,
            violations=list(consequence["violations"]), refs=refs,
            exception_amount=capacity)
    return _candidate(
        mechanism, True, hard_cap_trigger=trigger,
        exception_remaining=remaining - use_amount, refs=refs,
        exception_amount=capacity)


def _candidate_map(move: dict[str, Any], team: str, payroll_before: int,
                   lines: dict[str, Any], state: dict[str, Any], season: str,
                   active_hard_caps: list[str],
                   exception_amounts: dict[str, int],
                   team_salary_before: int | None = None) -> dict[str, dict[str, Any]]:
    post_move = payroll_before + move["amount"]
    room_basis = payroll_before if team_salary_before is None else int(team_salary_before)
    active_failure = active_hard_cap_failure(
        post_move, active_hard_caps, lines, transaction="signing")
    candidates = {
        "minimum": _minimum_candidate(move, season, lines),
        "cap_room": _cap_room_candidate(move, room_basis, lines),
    }
    for mechanism in ("room_exception", "tmle", "ntmle", "bae"):
        candidates[mechanism] = _exception_candidate(
            mechanism, move, team, payroll_before, lines, state, season,
            exception_amounts, team_salary_before=room_basis)
    if active_failure:
        for mechanism, candidate in candidates.items():
            if candidate["ok"]:
                candidates[mechanism] = _candidate(
                    mechanism, False, active_failure,
                    hard_cap_trigger=candidate["hard_cap_trigger"],
                    exception_remaining=candidate["exception_remaining"],
                    refs=candidate["refs"],
                    exception_amount=candidate["exception_amount"])
    return candidates


def _unsupported_candidate(mechanism: str) -> dict[str, Any]:
    return _candidate(
        mechanism, False,
        UNSUPPORTED_V1_MECHANISMS.get(mechanism, "mechanism is outside signing validation v1"),
        unknown=True)


def _exception_basis(lines: dict[str, Any], move: dict[str, Any],
                     selected: str | None, season: str,
                     exception_amounts: dict[str, int],
                     exception_amounts_source: str) -> str:
    mechanism = selected if selected in EXCEPTION_RULES else move.get("mechanism")
    if mechanism not in EXCEPTION_RULES:
        mechanism = "ntmle"
    rule = scaled_exception_rules(
        lines, season=season, exception_amounts=exception_amounts,
        exception_amounts_source=exception_amounts_source).get(str(mechanism), {})
    return str(rule.get("amount_basis") or FALLBACK_EXCEPTION_AMOUNT_BASIS)


def _result(move: dict[str, Any], *, outcome: str, selected: str | None,
            inference: str, candidates: dict[str, dict[str, Any]],
            evaluation: dict[str, Any] | None, blocking: list[str],
            checks: dict[str, str], missing: list[str],
            payroll_before: int, lines: dict[str, Any],
            input_errors: list[str] | None = None,
            tie_breaker: str = "", season: str = "2026-27",
            exception_amounts: dict[str, int] | None = None,
            exception_amounts_source: str = "supplied season exception amounts"
            ) -> dict[str, Any]:
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
    if selected == "minimum" and move["years"] > 1 and not move.get("salary_schedule"):
        advisory.append("later-year exact minimum salary amounts are not represented in signing validation v1")
        missing_inputs.append("later_year_minimum_salary_schedule")
    if season != "2026-27" and move.get("years_of_service") is not None:
        advisory.append("future minimum salaries use chained year-over-year cap-ratio scaling rounded half-up to whole dollars; intermediate future caps use Dime's disclosed projection path, not league-official values")
    use_amount = move["amount"] + move["unlikely_bonus"]
    exception_use = None
    if legal and selected in EXCEPTION_RULES:
        exception_use = {"mechanism": selected, "amount": use_amount}
    return {
        "kind": "signing", "player": move["player"], "amount": move["amount"],
        "unlikely_bonus": move["unlikely_bonus"], "years": move["years"],
        "years_defaulted": move["years_defaulted"],
        "salary_schedule": list(move.get("salary_schedule") or []),
        "mechanism_input": move["mechanism"], "mechanism_selected": selected,
        "mechanism_inference": inference, "selection_tie_breaker": tie_breaker,
        "outcome": outcome, "legal": legal,
        "legality_confidence": "approximation" if legal else "unknown" if outcome == "unknown" else "not_applicable",
        "hard_cap_trigger": trigger,
        "hard_cap_violations": list(evaluation.get("violations") or []),
        "post_move_payroll": post_move,
        "post_move_apron_room": lines[apron_key] - post_move,
        "exception_remaining": evaluation.get("exception_remaining"),
        "exception_amount": evaluation.get("exception_amount"),
        "exception_use": exception_use,
        "candidate_mechanisms": list(SUPPORTED_MECHANISMS),
        "legal_candidates": [mechanism for mechanism, candidate in candidates.items() if candidate["ok"]],
        "rejected_candidates": rejected,
        "blocking_issues": list(blocking), "advisory_issues": advisory,
        "missing_inputs": list(dict.fromkeys(missing_inputs)),
        "validation_checks": checks,
        "cba_refs": list(evaluation.get("refs") or []),
        "salary_basis": "approximate_salary_ledger_not_exact_apron_team_salary",
        "exception_amount_basis": _exception_basis(
            lines, move, selected, season, exception_amounts or {},
            exception_amounts_source),
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
    result = _result(
        move, outcome="unknown", selected=None, inference="input_error",
        candidates={}, evaluation=None, blocking=errors, checks={},
        missing=[], payroll_before=0, lines=dict(CAP), input_errors=errors)
    result["exception_amount_basis"] = INPUT_ERROR_EXCEPTION_AMOUNT_BASIS
    return result


def _auto_choice(candidates: dict[str, dict[str, Any]], payroll_before: int,
                 lines: dict[str, Any], state: dict[str, Any],
                 team_salary_before: int | None = None
                 ) -> tuple[str | None, str, list[str], str]:
    no_hard = [mechanism for mechanism in ("minimum", "cap_room", "room_exception")
               if candidates[mechanism]["ok"]]
    if no_hard:
        return no_hard[0], "least_restrictive_legal", [], ""
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
    mode_dependent = any(
        candidate.get("mode_dependent") for candidate in candidates.values())
    if not mode_dependent:
        return None, "none", ["no valid signing mechanism under the declared scenario state"], ""
    room_basis = payroll_before if team_salary_before is None else int(team_salary_before)
    if room_basis < lines["cap"] and state.get("operating_mode") == "unknown":
        return None, "explicit_required", [
            "below-cap operating mode is unknown; auto inference requires an explicit signing mechanism"
        ], ""
    return None, "none", ["no valid signing mechanism under the declared scenario state"], ""


def validate_signing(raw: Any, *, team: str, payroll_before: int,
                     lines: dict[str, Any] | None = None,
                     exception_state: dict[str, Any] | None = None,
                     active_hard_caps: list[str] | None = None,
                     season: str = "2026-27",
                     team_salary_before: int | None = None,
                     exception_amounts: dict[str, Any] | None = None,
                     exception_amounts_source: str = "supplied season exception amounts"
                     ) -> dict[str, Any]:
    if lines is None and season != "2026-27":
        return _input_error_result(
            raw, [f"season-specific cap lines are required for {season}; 2026-27 exception constants cannot be applied"])
    normalized_amounts, amount_errors = normalize_exception_amounts_input(
        exception_amounts)
    if amount_errors or normalized_amounts is None:
        return _input_error_result(raw, amount_errors)
    if lines is None:
        lines = dict(CAP)
    else:
        lines = dict(lines)
    move, input_errors = normalize_signing_input(raw)
    if move is None or input_errors:
        return _input_error_result(raw, input_errors)
    if exception_state is not None:
        state_seed = exception_state
    elif isinstance(raw, dict) and "exception_state" in raw:
        state_seed = raw.get("exception_state")
    else:
        state_seed = None
    if state_seed is None:
        state = initial_exception_state()
    else:
        normalized_state, state_errors = normalize_exception_state_input(state_seed)
        if state_errors or normalized_state is None:
            return _input_error_result(raw, state_errors)
        state = normalized_state
    checks, generic_failures, missing = _generic_checks(move, lines, season)
    candidates = _candidate_map(
        move, team, payroll_before, lines, state, season,
        list(active_hard_caps or []), normalized_amounts,
        team_salary_before=team_salary_before)
    mechanism = move["mechanism"]
    if generic_failures:
        return _result(
            move, outcome="illegal", selected=None, inference="not_applicable",
            candidates={}, evaluation=None, blocking=generic_failures,
            checks=checks, missing=missing, payroll_before=payroll_before,
            lines=lines, season=season, exception_amounts=normalized_amounts,
            exception_amounts_source=exception_amounts_source)
    if mechanism == "auto":
        selected, inference, blocking, tie_breaker = _auto_choice(
            candidates, payroll_before, lines, state,
            team_salary_before=team_salary_before)
        if selected:
            evaluation = candidates[selected]
            return _result(
                move, outcome="legal_approximation", selected=selected,
                inference=inference, candidates=candidates, evaluation=evaluation,
                blocking=[], checks=checks, missing=missing,
                payroll_before=payroll_before, lines=lines,
                tie_breaker=tie_breaker, season=season,
                exception_amounts=normalized_amounts,
                exception_amounts_source=exception_amounts_source)
        outcome = "unknown" if inference == "explicit_required" else "illegal"
        return _result(
            move, outcome=outcome, selected=None, inference=inference,
            candidates=candidates, evaluation=None, blocking=blocking,
            checks=checks, missing=missing, payroll_before=payroll_before,
            lines=lines, season=season, exception_amounts=normalized_amounts,
            exception_amounts_source=exception_amounts_source)
    evaluation = candidates.get(mechanism) or _unsupported_candidate(mechanism)
    candidates.setdefault(mechanism, evaluation)
    if evaluation["ok"]:
        preferred = next((candidate for candidate in AUTO_ORDER
                          if candidates.get(candidate, {}).get("ok")), None)
        result = _result(
            move, outcome="legal_approximation", selected=mechanism,
            inference="explicit", candidates=candidates, evaluation=evaluation,
            blocking=[], checks=checks, missing=missing,
            payroll_before=payroll_before, lines=lines, season=season,
            exception_amounts=normalized_amounts,
            exception_amounts_source=exception_amounts_source)
        if preferred and preferred != mechanism:
            result["less_restrictive_alternative"] = preferred
        return result
    outcome = "unknown" if evaluation["unknown"] else "illegal"
    return _result(
        move, outcome=outcome, selected=None, inference="explicit",
        candidates=candidates, evaluation=evaluation,
        blocking=[evaluation["reason"]], checks=checks, missing=missing,
        payroll_before=payroll_before, lines=lines, season=season,
        exception_amounts=normalized_amounts,
        exception_amounts_source=exception_amounts_source)


def consume_signing_exception(state: dict[str, Any], validation: dict[str, Any]
                              ) -> dict[str, Any]:
    out = initial_exception_state(state)
    use = validation.get("exception_use") or {}
    mechanism = use.get("mechanism")
    if validation.get("legal") and mechanism in EXCEPTION_RULES:
        key = str(EXCEPTION_RULES[mechanism]["used_key"])
        out[key] = int(out.get(key) or 0) + int(use.get("amount") or 0)
    return out
