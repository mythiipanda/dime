import inspect

import pytest

from shared.tools.cap_holds import (
    CAP_HOLD_CONTROL_INPUTS,
    CAP_HOLD_DECLINED_OPTION_AMOUNT_INPUTS,
    CAP_HOLD_DYNAMIC_AMOUNT_INPUTS,
    CAP_HOLD_FACT_INPUTS,
    CAP_HOLD_METADATA_INPUTS,
    CAP_HOLD_REQUIRED_AMOUNT_INPUTS,
    CAP_HOLD_RFA_AMOUNT_INPUTS,
    CAP_HOLD_TWO_WAY_AMOUNT_INPUTS,
    EXACTNESS_ESTIMATED,
    EXACTNESS_OFFICIAL,
    EXACTNESS_UNKNOWN,
    HOLD_EXACT_OFFICIAL_INPUTS,
    HOLD_EXACT_PROJECTED_INPUTS,
    HOLD_UNKNOWN,
    RIGHTS_EARLY_QUALIFYING,
    RIGHTS_NON_QUALIFYING,
    RIGHTS_QUALIFYING,
    RIGHTS_UNKNOWN,
    ROOKIE_SCALE_COMPLETED_SECOND_OPTION_YEAR,
    ROOKIE_SCALE_NONE,
    ROOKIE_SCALE_OPTION_DECLINED,
    ROUND_EXACT,
    ROUND_HALF_UP,
    calculate_cap_hold,
    calculate_unsigned_first_round_draft_hold,
)

TARGET_CAP = 181_457_100
PRIOR_EAPS = 12_000_000
ZERO_YOS_MINIMUM = 1_493_539
UNREIMBURSED_TWO_YOS_MINIMUM = 2_694_363

INPUT_SURFACE_SCENARIOS = (
    {},
    {"completed_two_way_contract": True,
     "target_zero_yos_minimum": ZERO_YOS_MINIMUM},
    {"rookie_scale_status": ROOKIE_SCALE_OPTION_DECLINED,
     "declined_option_amount": 10_000_000},
    {"restricted_free_agent": True,
     "qualifying_offer": 5_400_000,
     "maximum_qualifying_offer": 6_000_000,
     "first_refusal_exercise_notice": 6_500_000},
)


def input_exactness():
    return {
        "years_of_service": EXACTNESS_OFFICIAL,
        "rights_classification": EXACTNESS_OFFICIAL,
        "rookie_scale_status": EXACTNESS_OFFICIAL,
        "max_player_tier": EXACTNESS_OFFICIAL,
        "completed_two_way_contract": EXACTNESS_OFFICIAL,
        "restricted_free_agent": EXACTNESS_OFFICIAL,
        "prior_salary": EXACTNESS_OFFICIAL,
        "final_prior_contract_salary": EXACTNESS_OFFICIAL,
        "target_salary_cap": EXACTNESS_ESTIMATED,
        "prior_year_eaps": EXACTNESS_ESTIMATED,
        "applicable_minimum": EXACTNESS_ESTIMATED,
        "target_unreimbursed_minimum": EXACTNESS_ESTIMATED,
        "target_zero_yos_minimum": EXACTNESS_ESTIMATED,
        "declined_option_amount": EXACTNESS_OFFICIAL,
        "qualifying_offer": EXACTNESS_OFFICIAL,
        "maximum_qualifying_offer": EXACTNESS_OFFICIAL,
        "first_refusal_exercise_notice": EXACTNESS_OFFICIAL,
        "rookie_scale_amount": EXACTNESS_ESTIMATED,
    }


def provenance():
    return {
        "years_of_service": "probe player-contract fact input",
        "rights_classification": "probe rights-classification fact input",
        "rookie_scale_status": "probe rookie-scale fact input",
        "max_player_tier": "probe max-tier fact input",
        "completed_two_way_contract": "probe contract-type fact input",
        "restricted_free_agent": "probe free-agent-classification fact input",
        "prior_salary": "probe numeric vector",
        "final_prior_contract_salary": "probe numeric vector",
        "target_salary_cap": "probe shared projected-input assumption",
        "prior_year_eaps": "probe shared projected-input assumption",
        "applicable_minimum": "probe shared projected-input assumption",
        "target_unreimbursed_minimum": "probe shared projected-input assumption",
        "target_zero_yos_minimum": "probe shared projected-input assumption",
        "declined_option_amount": "probe numeric vector",
        "qualifying_offer": "probe numeric vector",
        "maximum_qualifying_offer": "probe numeric vector",
        "first_refusal_exercise_notice": "probe numeric vector",
        "rookie_scale_amount": "probe shared projected-input assumption",
    }


def base_kwargs(**overrides):
    kwargs = {
        "prior_salary": 20_000_000,
        "final_prior_contract_salary": 20_000_000,
        "years_of_service": 5,
        "rights_classification": RIGHTS_QUALIFYING,
        "rookie_scale_status": ROOKIE_SCALE_NONE,
        "max_player_tier": 25,
        "target_salary_cap": TARGET_CAP,
        "prior_year_eaps": PRIOR_EAPS,
        "applicable_minimum": 1_000_000,
        "target_unreimbursed_minimum": UNREIMBURSED_TWO_YOS_MINIMUM,
        "input_exactness": input_exactness(),
        "provenance": provenance(),
    }
    kwargs.update(overrides)
    return kwargs


def expected_tracked_input_names(kwargs):
    names = set(CAP_HOLD_FACT_INPUTS) | set(CAP_HOLD_REQUIRED_AMOUNT_INPUTS)
    if kwargs.get("completed_two_way_contract", False):
        names.update(CAP_HOLD_TWO_WAY_AMOUNT_INPUTS)
    if kwargs.get("rookie_scale_status") == ROOKIE_SCALE_OPTION_DECLINED:
        names.update(CAP_HOLD_DECLINED_OPTION_AMOUNT_INPUTS)
    names.update(
        name for name in CAP_HOLD_RFA_AMOUNT_INPUTS
        if kwargs.get(name) is not None
    )
    return names


def test_calculator_signature_input_surface_is_fully_classified():
    groups = (
        CAP_HOLD_FACT_INPUTS,
        CAP_HOLD_REQUIRED_AMOUNT_INPUTS,
        CAP_HOLD_DYNAMIC_AMOUNT_INPUTS,
        CAP_HOLD_METADATA_INPUTS,
        CAP_HOLD_CONTROL_INPUTS,
    )
    classified = [name for group in groups for name in group]
    assert len(classified) == len(set(classified))
    assert set(classified) == set(inspect.signature(calculate_cap_hold).parameters)


@pytest.mark.parametrize("overrides", INPUT_SURFACE_SCENARIOS)
def test_output_metadata_covers_exact_calculation_input_surface(overrides):
    kwargs = base_kwargs(**overrides)
    result = calculate_cap_hold(**kwargs)
    expected = expected_tracked_input_names(kwargs)
    assert set(result["input_exactness"]) == expected
    assert set(result["input_provenance"]) == expected


def test_exactness_and_provenance_are_required_for_every_tracked_input():
    for overrides in INPUT_SURFACE_SCENARIOS:
        kwargs = base_kwargs(**overrides)
        for name in expected_tracked_input_names(kwargs):
            exactness = dict(kwargs["input_exactness"])
            del exactness[name]
            with pytest.raises(ValueError, match="missing exactness metadata"):
                calculate_cap_hold(**dict(kwargs, input_exactness=exactness))
            sources = dict(kwargs["provenance"])
            del sources[name]
            with pytest.raises(ValueError, match="missing provenance for inputs"):
                calculate_cap_hold(**dict(kwargs, provenance=sources))


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"prior_salary": 20_000_000, "final_prior_contract_salary": 20_000_000}, 30_000_000),
        ({"prior_salary": 10_000_000, "final_prior_contract_salary": 10_000_000}, 19_000_000),
        ({"prior_salary": 10_000_000, "final_prior_contract_salary": 10_000_000,
          "rookie_scale_status": ROOKIE_SCALE_COMPLETED_SECOND_OPTION_YEAR}, 30_000_000),
        ({"prior_salary": 13_000_000, "final_prior_contract_salary": 13_000_000,
          "rookie_scale_status": ROOKIE_SCALE_COMPLETED_SECOND_OPTION_YEAR}, 32_500_000),
        ({"prior_salary": 13_398_800, "final_prior_contract_salary": 13_398_800,
          "rights_classification": RIGHTS_EARLY_QUALIFYING}, 17_418_440),
        ({"prior_salary": 6_064_000, "final_prior_contract_salary": 6_064_000,
          "rights_classification": RIGHTS_NON_QUALIFYING}, 7_276_800),
        ({"prior_salary": 3_876_529, "final_prior_contract_salary": 3_876_529,
          "years_of_service": 10, "max_player_tier": 35,
          "applicable_minimum": 3_876_529}, 2_694_363),
        ({"prior_salary": 59_033_114, "final_prior_contract_salary": 59_033_114,
          "years_of_service": 10, "max_player_tier": 35}, 63_509_985),
        ({"prior_salary": 8_000_000, "final_prior_contract_salary": 8_000_000,
          "prior_year_eaps": 8_000_000,
          "rookie_scale_status": ROOKIE_SCALE_OPTION_DECLINED,
          "declined_option_amount": 10_000_000}, 10_000_000),
        ({"prior_salary": 4_000_000, "final_prior_contract_salary": 4_000_000,
          "rights_classification": RIGHTS_NON_QUALIFYING,
          "restricted_free_agent": True, "qualifying_offer": 5_400_000}, 5_400_000),
        ({"prior_salary": 1_200_000, "final_prior_contract_salary": 1_200_000,
          "completed_two_way_contract": True,
          "target_zero_yos_minimum": ZERO_YOS_MINIMUM}, 1_493_539),
    ],
)
def test_probe_numeric_vectors(overrides, expected):
    result = calculate_cap_hold(**base_kwargs(**overrides))
    assert result["amount"] == expected


def test_eaps_boundary_uses_higher_band():
    ordinary = calculate_cap_hold(**base_kwargs(
        prior_salary=PRIOR_EAPS, final_prior_contract_salary=PRIOR_EAPS))
    rookie = calculate_cap_hold(**base_kwargs(
        prior_salary=PRIOR_EAPS, final_prior_contract_salary=PRIOR_EAPS,
        rookie_scale_status=ROOKIE_SCALE_COMPLETED_SECOND_OPTION_YEAR))
    assert ordinary["amount"] == 18_000_000
    assert ordinary["calculation"]["eaps_band"] == "at_or_above_eaps"
    assert rookie["amount"] == 30_000_000
    assert rookie["calculation"]["eaps_band"] == "at_or_above_eaps"


def test_jokic_style_max_clamp_records_basis_and_exact_fraction():
    result = calculate_cap_hold(**base_kwargs(
        prior_salary=59_033_114, final_prior_contract_salary=59_033_114,
        years_of_service=10, max_player_tier=35))
    assert result["amount"] == 63_509_985
    assert result["adjustments"] == ["maximum_salary_clamp"]
    assert result["calculation"]["raw_amount"] == 88_549_671
    assert result["calculation"]["maximum_salary_basis"] == "35_percent_of_salary_cap"


def test_anthony_black_style_rookie_scale_completion_uses_300_percent_below_eaps():
    result = calculate_cap_hold(**base_kwargs(
        prior_salary=10_106_316, final_prior_contract_salary=10_106_316,
        rookie_scale_status=ROOKIE_SCALE_COMPLETED_SECOND_OPTION_YEAR))
    assert result["amount"] == 30_318_948
    assert result["calculation"]["raw_amount"] == 30_318_948
    assert result["calculation"]["percentage"] == "300%"


def test_max_clamp_uses_105_percent_when_greater_than_cap_tier():
    result = calculate_cap_hold(**base_kwargs(
        prior_salary=30_000_000, final_prior_contract_salary=30_000_000,
        target_salary_cap=100_000_000))
    assert result["amount"] == 31_500_000
    assert result["calculation"]["maximum_salary_basis"] == "105_percent_of_final_prior_contract_salary"


def test_restricted_free_agent_uses_greatest_outstanding_amount():
    result = calculate_cap_hold(**base_kwargs(
        prior_salary=4_000_000, final_prior_contract_salary=4_000_000,
        rights_classification=RIGHTS_NON_QUALIFYING,
        restricted_free_agent=True, qualifying_offer=5_400_000,
        maximum_qualifying_offer=6_000_000,
        first_refusal_exercise_notice=6_500_000))
    assert result["amount"] == 6_500_000
    assert result["calculation"]["normal_free_agent_amount"] == 4_800_000
    assert result["calculation"]["restricted_free_agent_amount_basis"] == "first_refusal_exercise_notice"
    assert result["adjustments"] == ["restricted_free_agent_greater_amount"]


def test_exactness_metadata_distinguishes_official_and_projected_inputs():
    result = calculate_cap_hold(**base_kwargs())
    assert result["hold_exactness"] == HOLD_EXACT_PROJECTED_INPUTS
    assert result["input_exactness"]["prior_salary"] == EXACTNESS_OFFICIAL
    assert result["input_exactness"]["target_salary_cap"] == EXACTNESS_ESTIMATED
    assert result["input_exactness"]["completed_two_way_contract"] == EXACTNESS_OFFICIAL
    assert result["input_exactness"]["restricted_free_agent"] == EXACTNESS_OFFICIAL
    assert result["input_provenance"]["prior_year_eaps"] == "probe shared projected-input assumption"
    assert result["input_provenance"]["rights_classification"] == "probe rights-classification fact input"


def test_all_official_inputs_produce_official_exactness():
    exactness = input_exactness()
    for key in exactness:
        exactness[key] = EXACTNESS_OFFICIAL
    result = calculate_cap_hold(**base_kwargs(input_exactness=exactness))
    assert result["hold_exactness"] == HOLD_EXACT_OFFICIAL_INPUTS


def test_unknown_rights_classification_returns_no_guessed_amount():
    exactness = input_exactness()
    exactness["rights_classification"] = EXACTNESS_UNKNOWN
    result = calculate_cap_hold(**base_kwargs(
        rights_classification=RIGHTS_UNKNOWN, input_exactness=exactness))
    assert result["amount"] is None
    assert result["hold_exactness"] == HOLD_UNKNOWN
    assert result["calculation"]["computed"] is False


def test_non_integral_exact_amount_requires_explicit_rounding():
    with pytest.raises(ValueError, match="non-integral dollar amount"):
        calculate_cap_hold(**base_kwargs(
            prior_salary=10_000_001, final_prior_contract_salary=10_000_001,
            prior_year_eaps=10_000_000))
    result = calculate_cap_hold(**base_kwargs(
        prior_salary=10_000_001, final_prior_contract_salary=10_000_001,
        prior_year_eaps=10_000_000, integer_rounding=ROUND_HALF_UP))
    assert result["amount"] == 15_000_002
    assert result["calculation"]["final_amount"] == "30000003/2"


def test_amount_provenance_is_required():
    sources = provenance()
    del sources["target_salary_cap"]
    with pytest.raises(ValueError, match="missing provenance"):
        calculate_cap_hold(**base_kwargs(provenance=sources))


def test_fact_provenance_is_required():
    sources = provenance()
    del sources["rights_classification"]
    with pytest.raises(ValueError, match="missing provenance for inputs: rights_classification"):
        calculate_cap_hold(**base_kwargs(provenance=sources))


@pytest.mark.parametrize("name", ("completed_two_way_contract", "restricted_free_agent"))
def test_state_input_exactness_is_required(name):
    exactness = input_exactness()
    del exactness[name]
    with pytest.raises(ValueError, match="missing exactness metadata"):
        calculate_cap_hold(**base_kwargs(input_exactness=exactness))


@pytest.mark.parametrize("name", ("completed_two_way_contract", "restricted_free_agent"))
def test_state_inputs_must_be_booleans(name):
    with pytest.raises(ValueError, match=f"boolean inputs must be true or false: {name}"):
        calculate_cap_hold(**base_kwargs(**{name: "false"}))


@pytest.mark.parametrize("name", CAP_HOLD_REQUIRED_AMOUNT_INPUTS)
def test_required_amount_null_fails_validation_before_calculation(name):
    with pytest.raises(ValueError, match=f"required amount inputs cannot be null: {name}"):
        calculate_cap_hold(**base_kwargs(**{name: None}))


def test_optional_dynamic_amounts_may_be_null_when_inactive():
    result = calculate_cap_hold(**base_kwargs(
        target_zero_yos_minimum=None,
        declined_option_amount=None,
        qualifying_offer=None,
        maximum_qualifying_offer=None,
        first_refusal_exercise_notice=None))
    assert result["amount"] == 30_000_000


def test_two_way_amount_requires_completed_two_way_status():
    with pytest.raises(ValueError, match="requires completed_two_way_contract=True"):
        calculate_cap_hold(**base_kwargs(target_zero_yos_minimum=ZERO_YOS_MINIMUM))


def test_declined_option_amount_requires_declined_rookie_status():
    with pytest.raises(ValueError, match="requires declined rookie-scale option"):
        calculate_cap_hold(**base_kwargs(declined_option_amount=10_000_000))


def test_unsigned_first_round_amount_null_fails_validation_before_calculation():
    with pytest.raises(ValueError, match="required amount inputs cannot be null: rookie_scale_amount"):
        calculate_unsigned_first_round_draft_hold(
            rookie_scale_amount=None,
            input_exactness=input_exactness(),
            provenance=provenance())


def test_unsigned_first_round_draft_rights_are_separate_120_percent_rule():
    result = calculate_unsigned_first_round_draft_hold(
        rookie_scale_amount=10_000_000,
        input_exactness=input_exactness(),
        provenance=provenance())
    assert result["amount"] == 12_000_000
    assert result["hold_basis"] == "unsigned_first_round_draft_rights"
    assert result["hold_rule"] == "unsigned_first_round_pick_120_percent_of_rookie_scale"
    assert result["hold_exactness"] == HOLD_EXACT_PROJECTED_INPUTS
    assert set(result["input_exactness"]) == {"rookie_scale_amount"}
    assert set(result["input_provenance"]) == {"rookie_scale_amount"}
