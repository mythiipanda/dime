from fractions import Fraction
from typing import Any, Mapping

EXACTNESS_OFFICIAL = "official_exact"
EXACTNESS_ESTIMATED = "estimated"
EXACTNESS_APPROXIMATE = "approximate"
EXACTNESS_UNKNOWN = "unknown"

HOLD_EXACT_OFFICIAL_INPUTS = "exact_formula_official_inputs"
HOLD_EXACT_PROJECTED_INPUTS = "exact_formula_projected_inputs"
HOLD_APPROXIMATE = "approximate"
HOLD_UNKNOWN = "unknown"

RIGHTS_QUALIFYING = "qualifying"
RIGHTS_EARLY_QUALIFYING = "early_qualifying"
RIGHTS_NON_QUALIFYING = "non_qualifying"
RIGHTS_UNKNOWN = "unknown"

ROOKIE_SCALE_NONE = "not_rookie_scale"
ROOKIE_SCALE_COMPLETED_SECOND_OPTION_YEAR = "completed_after_second_option_year"
ROOKIE_SCALE_OPTION_DECLINED = "option_declined_after_second_or_third_year"

ROUND_EXACT = "exact"
ROUND_HALF_UP = "half_up"
ROUND_FLOOR = "floor"
ROUND_CEILING = "ceiling"

_EXACTNESS_VALUES = {
    EXACTNESS_OFFICIAL,
    EXACTNESS_ESTIMATED,
    EXACTNESS_APPROXIMATE,
    EXACTNESS_UNKNOWN,
}
_RIGHTS_VALUES = {
    RIGHTS_QUALIFYING,
    RIGHTS_EARLY_QUALIFYING,
    RIGHTS_NON_QUALIFYING,
    RIGHTS_UNKNOWN,
}
_ROOKIE_SCALE_VALUES = {
    ROOKIE_SCALE_NONE,
    ROOKIE_SCALE_COMPLETED_SECOND_OPTION_YEAR,
    ROOKIE_SCALE_OPTION_DECLINED,
}
_ROUNDING_VALUES = {ROUND_EXACT, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING}
_MAX_TIERS = {25, 30, 35}

CAP_HOLD_FACT_INPUTS = (
    "years_of_service",
    "rights_classification",
    "rookie_scale_status",
    "max_player_tier",
    "completed_two_way_contract",
    "restricted_free_agent",
)
CAP_HOLD_REQUIRED_AMOUNT_INPUTS = (
    "prior_salary",
    "final_prior_contract_salary",
    "target_salary_cap",
    "prior_year_eaps",
    "applicable_minimum",
    "target_unreimbursed_minimum",
)
CAP_HOLD_TWO_WAY_AMOUNT_INPUTS = (
    "target_zero_yos_minimum",
)
CAP_HOLD_DECLINED_OPTION_AMOUNT_INPUTS = (
    "declined_option_amount",
)
CAP_HOLD_RFA_AMOUNT_INPUTS = (
    "qualifying_offer",
    "maximum_qualifying_offer",
    "first_refusal_exercise_notice",
)
CAP_HOLD_DYNAMIC_AMOUNT_INPUTS = (
    *CAP_HOLD_TWO_WAY_AMOUNT_INPUTS,
    *CAP_HOLD_DECLINED_OPTION_AMOUNT_INPUTS,
    *CAP_HOLD_RFA_AMOUNT_INPUTS,
)
CAP_HOLD_METADATA_INPUTS = (
    "input_exactness",
    "provenance",
)
CAP_HOLD_CONTROL_INPUTS = (
    "integer_rounding",
)


def _require_amounts(values: Mapping[str, int | None],
                     optional_names: tuple[str, ...] = ()) -> None:
    optional = set(optional_names)
    missing = [name for name, value in values.items()
               if value is None and name not in optional]
    if missing:
        raise ValueError("required amount inputs cannot be null: " + ", ".join(missing))
    bad = [name for name, value in values.items()
           if value is not None
           and (not isinstance(value, int) or isinstance(value, bool) or value < 0)]
    if bad:
        raise ValueError("amount inputs must be non-negative integer dollars: " + ", ".join(bad))


def _validate_core(rights_classification: str, rookie_scale_status: str,
                   max_player_tier: int, integer_rounding: str,
                   years_of_service: int) -> None:
    if rights_classification not in _RIGHTS_VALUES:
        raise ValueError(f"unsupported rights_classification: {rights_classification}")
    if rookie_scale_status not in _ROOKIE_SCALE_VALUES:
        raise ValueError(f"unsupported rookie_scale_status: {rookie_scale_status}")
    if max_player_tier not in _MAX_TIERS:
        raise ValueError("max_player_tier must be one of 25, 30, or 35")
    if integer_rounding not in _ROUNDING_VALUES:
        raise ValueError(f"unsupported integer_rounding: {integer_rounding}")
    if not isinstance(years_of_service, int) or years_of_service < 0:
        raise ValueError("years_of_service must be a non-negative integer")


def _validate_boolean_inputs(values: Mapping[str, bool]) -> None:
    bad = [name for name, value in values.items() if not isinstance(value, bool)]
    if bad:
        raise ValueError("boolean inputs must be true or false: " + ", ".join(bad))


def _validate_state(completed_two_way_contract: bool,
                    target_zero_yos_minimum: int | None,
                    declined: bool, declined_option_amount: int | None,
                    restricted_free_agent: bool,
                    rfa_amounts: Mapping[str, int | None]) -> None:
    _validate_boolean_inputs({
        "completed_two_way_contract": completed_two_way_contract,
        "restricted_free_agent": restricted_free_agent,
    })
    if declined and declined_option_amount is None:
        raise ValueError("declined_option_amount is required for a declined rookie-scale option")
    if not declined and declined_option_amount is not None:
        raise ValueError("declined_option_amount requires declined rookie-scale option status")
    if completed_two_way_contract and target_zero_yos_minimum is None:
        raise ValueError("target_zero_yos_minimum is required for a completed two-way contract")
    if not completed_two_way_contract and target_zero_yos_minimum is not None:
        raise ValueError("target_zero_yos_minimum requires completed_two_way_contract=True")
    if not restricted_free_agent and any(value is not None for value in rfa_amounts.values()):
        raise ValueError("restricted free-agent amounts require restricted_free_agent=True")


def _input_names(two_way: bool, declined: bool, rfa_amounts: Mapping[str, int | None]) -> tuple[list[str], list[str]]:
    amounts = list(CAP_HOLD_REQUIRED_AMOUNT_INPUTS)
    facts = list(CAP_HOLD_FACT_INPUTS)
    if two_way:
        amounts.extend(CAP_HOLD_TWO_WAY_AMOUNT_INPUTS)
    if declined:
        amounts.extend(CAP_HOLD_DECLINED_OPTION_AMOUNT_INPUTS)
    amounts.extend(name for name in CAP_HOLD_RFA_AMOUNT_INPUTS if rfa_amounts.get(name) is not None)
    return facts, amounts


def _metadata(input_exactness: Mapping[str, str], provenance: Mapping[str, str],
              fact_names: list[str], amount_names: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    names = fact_names + amount_names
    missing = [name for name in names if name not in input_exactness]
    if missing:
        raise ValueError("missing exactness metadata for: " + ", ".join(missing))
    bad = [name for name in names if input_exactness[name] not in _EXACTNESS_VALUES]
    if bad:
        raise ValueError("unsupported exactness metadata for: " + ", ".join(bad))
    missing_provenance = [name for name in names if not str(provenance.get(name) or "").strip()]
    if missing_provenance:
        raise ValueError("missing provenance for inputs: " + ", ".join(missing_provenance))
    exactness = {name: input_exactness[name] for name in names}
    sources = {name: str(provenance[name]) for name in names}
    return exactness, sources


def _overall_exactness(exactness: Mapping[str, str]) -> str:
    values = set(exactness.values())
    if EXACTNESS_UNKNOWN in values:
        return HOLD_UNKNOWN
    if EXACTNESS_APPROXIMATE in values:
        return HOLD_APPROXIMATE
    if EXACTNESS_ESTIMATED in values:
        return HOLD_EXACT_PROJECTED_INPUTS
    return HOLD_EXACT_OFFICIAL_INPUTS


def _base_percentage(prior_salary: int, prior_year_eaps: int, rights: str,
                     rookie_scale_status: str) -> tuple[Fraction, str, str]:
    band = "at_or_above_eaps" if prior_salary >= prior_year_eaps else "below_eaps"
    above = prior_salary >= prior_year_eaps
    if rights == RIGHTS_QUALIFYING and rookie_scale_status == ROOKIE_SCALE_COMPLETED_SECOND_OPTION_YEAR:
        if above:
            return Fraction(5, 2), "rookie_scale_completion_250_percent", band
        return Fraction(3, 1), "rookie_scale_completion_300_percent", band
    if rights == RIGHTS_QUALIFYING:
        if above:
            return Fraction(3, 2), "qualifying_veteran_150_percent", band
        return Fraction(19, 10), "qualifying_veteran_190_percent", band
    if rights == RIGHTS_EARLY_QUALIFYING:
        return Fraction(13, 10), "early_qualifying_veteran_130_percent", band
    return Fraction(6, 5), "non_qualifying_veteran_120_percent", band


def _raw_hold_amount(prior_salary: int, prior_year_eaps: int,
                     applicable_minimum: int, target_unreimbursed_minimum: int,
                     target_zero_yos_minimum: int | None,
                     completed_two_way_contract: bool, rights: str,
                     rookie_scale_status: str) -> tuple[Fraction, str, str | None, Fraction | None]:
    if completed_two_way_contract:
        return Fraction(target_zero_yos_minimum), "two_way_completion_zero_yos_minimum", None, None
    if prior_salary <= applicable_minimum:
        return Fraction(target_unreimbursed_minimum), "minimum_salary_free_agent", None, None
    percentage, rule, band = _base_percentage(
        prior_salary, prior_year_eaps, rights, rookie_scale_status)
    return Fraction(prior_salary) * percentage, rule, band, percentage


def _integer_amount(value: Fraction, rounding: str) -> int:
    if value.denominator == 1:
        return value.numerator
    if rounding == ROUND_EXACT:
        raise ValueError(f"non-integral dollar amount {value.numerator}/{value.denominator}; choose explicit integer_rounding")
    if rounding == ROUND_HALF_UP:
        shifted = value + Fraction(1, 2)
        return shifted.numerator // shifted.denominator
    if rounding == ROUND_FLOOR:
        return value.numerator // value.denominator
    return -(-value.numerator // value.denominator)


def _exact_output(value: Fraction) -> int | str:
    if value.denominator == 1:
        return value.numerator
    return f"{value.numerator}/{value.denominator}"


def _percentage_output(value: Fraction | None) -> str | None:
    if value is None:
        return None
    return f"{value * 100}%"


def _maximum_salary(target_salary_cap: int, max_player_tier: int,
                    final_prior_contract_salary: int) -> tuple[Fraction, str]:
    cap_amount = Fraction(target_salary_cap * max_player_tier, 100)
    prior_amount = Fraction(final_prior_contract_salary * 105, 100)
    if prior_amount > cap_amount:
        return prior_amount, "105_percent_of_final_prior_contract_salary"
    return cap_amount, f"{max_player_tier}_percent_of_salary_cap"


def _ordinary_max_tier(years_of_service: int) -> int:
    if years_of_service < 7:
        return 25
    if years_of_service < 10:
        return 30
    return 35


def _normal_amount(raw: Fraction, maximum: Fraction, declined: bool,
                   declined_option_amount: int | None,
                   target_unreimbursed_minimum: int,
                   completed_two_way_contract: bool) -> tuple[Fraction, dict[str, Any], list[str]]:
    adjustments: list[str] = []
    after_maximum = min(raw, maximum)
    if after_maximum != raw:
        adjustments.append("maximum_salary_clamp")
    after_declined = after_maximum
    declined_cap = None
    if declined:
        declined_cap = Fraction(declined_option_amount)
        if declined_cap < Fraction(target_unreimbursed_minimum):
            raise ValueError("declined option amount cannot be below the unreimbursed minimum floor")
        after_declined = min(after_declined, declined_cap)
        if after_declined != after_maximum:
            adjustments.append("declined_rookie_option_cap")
    normal = after_declined
    if not completed_two_way_contract:
        normal = max(after_declined, Fraction(target_unreimbursed_minimum))
        if normal != after_declined:
            adjustments.append("unreimbursed_minimum_floor")
    details = {
        "after_maximum_clamp": _exact_output(after_maximum),
        "declined_option_cap": _exact_output(declined_cap) if declined_cap is not None else None,
        "after_declined_option_cap": _exact_output(after_declined),
        "unreimbursed_minimum_floor": target_unreimbursed_minimum,
        "normal_free_agent_amount": _exact_output(normal),
    }
    return normal, details, adjustments


def _restricted_amount(normal: Fraction, restricted_free_agent: bool,
                       rfa_amounts: Mapping[str, int | None]) -> tuple[Fraction, tuple[str, int] | None, list[str]]:
    if not restricted_free_agent:
        return normal, None, []
    present = {name: value for name, value in rfa_amounts.items() if value is not None}
    if not present:
        return normal, None, []
    selected = max(present.items(), key=lambda item: item[1])
    final = max(normal, Fraction(selected[1]))
    adjustments = ["restricted_free_agent_greater_amount"] if final != normal else []
    return final, selected, adjustments


def _unknown_result(rights: str, exactness: dict[str, str], sources: dict[str, str]) -> dict[str, Any]:
    return {
        "amount": None,
        "hold_basis": rights,
        "hold_rule": "unknown_rights_classification",
        "hold_exactness": HOLD_UNKNOWN,
        "input_exactness": exactness,
        "input_provenance": sources,
        "integer_rounding": None,
        "adjustments": [],
        "calculation": {
            "computed": False,
            "reason": "rights classification is unknown; no amount is guessed",
        },
    }


def calculate_cap_hold(*, prior_salary: int, final_prior_contract_salary: int,
                       years_of_service: int, rights_classification: str,
                       rookie_scale_status: str, max_player_tier: int,
                       target_salary_cap: int, prior_year_eaps: int,
                       applicable_minimum: int, target_unreimbursed_minimum: int,
                       input_exactness: Mapping[str, str], provenance: Mapping[str, str],
                       target_zero_yos_minimum: int | None = None,
                       completed_two_way_contract: bool = False,
                       declined_option_amount: int | None = None,
                       restricted_free_agent: bool = False,
                       qualifying_offer: int | None = None,
                       maximum_qualifying_offer: int | None = None,
                       first_refusal_exercise_notice: int | None = None,
                       integer_rounding: str = ROUND_EXACT) -> dict[str, Any]:
    _validate_core(rights_classification, rookie_scale_status, max_player_tier,
                   integer_rounding, years_of_service)
    rfa_amounts = {
        "qualifying_offer": qualifying_offer,
        "maximum_qualifying_offer": maximum_qualifying_offer,
        "first_refusal_exercise_notice": first_refusal_exercise_notice,
    }
    declined = rookie_scale_status == ROOKIE_SCALE_OPTION_DECLINED
    _validate_state(completed_two_way_contract, target_zero_yos_minimum, declined,
                    declined_option_amount, restricted_free_agent, rfa_amounts)
    amounts = {
        "prior_salary": prior_salary,
        "final_prior_contract_salary": final_prior_contract_salary,
        "target_salary_cap": target_salary_cap,
        "prior_year_eaps": prior_year_eaps,
        "applicable_minimum": applicable_minimum,
        "target_unreimbursed_minimum": target_unreimbursed_minimum,
        "target_zero_yos_minimum": target_zero_yos_minimum,
        "declined_option_amount": declined_option_amount,
        **rfa_amounts,
    }
    _require_amounts(amounts, CAP_HOLD_DYNAMIC_AMOUNT_INPUTS)
    fact_names, amount_names = _input_names(completed_two_way_contract, declined, rfa_amounts)
    exactness, sources = _metadata(input_exactness, provenance, fact_names, amount_names)
    if rights_classification == RIGHTS_UNKNOWN and not completed_two_way_contract:
        return _unknown_result(rights_classification, exactness, sources)

    raw, rule, band, percentage = _raw_hold_amount(
        prior_salary, prior_year_eaps, applicable_minimum,
        target_unreimbursed_minimum, target_zero_yos_minimum,
        completed_two_way_contract, rights_classification, rookie_scale_status)
    maximum, maximum_basis = _maximum_salary(
        target_salary_cap, max_player_tier, final_prior_contract_salary)
    normal, normal_details, adjustments = _normal_amount(
        raw, maximum, declined, declined_option_amount,
        target_unreimbursed_minimum, completed_two_way_contract)
    final, rfa_selected, rfa_adjustments = _restricted_amount(
        normal, restricted_free_agent, rfa_amounts)
    adjustments.extend(rfa_adjustments)
    amount = _integer_amount(final, integer_rounding)
    return {
        "amount": amount,
        "hold_basis": rights_classification if not completed_two_way_contract else "two_way_completion",
        "hold_rule": rule,
        "hold_exactness": _overall_exactness(exactness),
        "input_exactness": exactness,
        "input_provenance": sources,
        "integer_rounding": integer_rounding,
        "adjustments": adjustments,
        "calculation": {
            "computed": True,
            "years_of_service": years_of_service,
            "ordinary_max_player_tier": _ordinary_max_tier(years_of_service),
            "prior_salary": prior_salary,
            "eaps_band": band,
            "percentage": _percentage_output(percentage),
            "raw_amount": _exact_output(raw),
            "maximum_salary": _exact_output(maximum),
            "maximum_salary_basis": maximum_basis,
            **normal_details,
            "restricted_free_agent_amount": rfa_selected[1] if rfa_selected else None,
            "restricted_free_agent_amount_basis": rfa_selected[0] if rfa_selected else None,
            "final_amount": _exact_output(final),
        },
    }


def calculate_unsigned_first_round_draft_hold(*, rookie_scale_amount: int,
                                              input_exactness: Mapping[str, str],
                                              provenance: Mapping[str, str],
                                              integer_rounding: str = ROUND_EXACT) -> dict[str, Any]:
    if integer_rounding not in _ROUNDING_VALUES:
        raise ValueError(f"unsupported integer_rounding: {integer_rounding}")
    _require_amounts({"rookie_scale_amount": rookie_scale_amount})
    exactness, sources = _metadata(
        input_exactness, provenance, [], ["rookie_scale_amount"])
    raw = Fraction(rookie_scale_amount * 6, 5)
    amount = _integer_amount(raw, integer_rounding)
    return {
        "amount": amount,
        "hold_basis": "unsigned_first_round_draft_rights",
        "hold_rule": "unsigned_first_round_pick_120_percent_of_rookie_scale",
        "hold_exactness": _overall_exactness(exactness),
        "input_exactness": exactness,
        "input_provenance": sources,
        "integer_rounding": integer_rounding,
        "adjustments": [],
        "calculation": {
            "computed": True,
            "rookie_scale_amount": rookie_scale_amount,
            "percentage": "120%",
            "final_amount": _exact_output(raw),
        },
    }
