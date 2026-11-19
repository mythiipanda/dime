import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.dabstep import score_answer, score_task


def test_numeric_boundary_within_tolerance_passes():
    assert score_answer("100.00", "100.009") is True


def test_numeric_boundary_outside_tolerance_fails():
    assert score_answer("100.00", "100.02") is False


def test_dollar_and_commas_normalize():
    assert score_answer("$1,234.56", "1234.56") is True


def test_euro_prefix_normalizes():
    assert score_answer("€50", "50.0") is True


def test_pound_prefix_normalizes():
    assert score_answer("£9.99", "9.99") is True


def test_unequal_numbers_fail():
    assert score_answer("1,000", "1,001") is False


def test_case_insensitive_string_match():
    assert score_answer("Harbor Seals", "harbor seals") is True


def test_punctuation_insensitive_string_match():
    assert score_answer("Marek Voss!", "marek voss") is True


def test_whitespace_collapse_string_match():
    assert score_answer("  marek   voss ", "marek voss") is True


def test_fuzzy_above_threshold_passes():
    predicted = "marek voss recorded eighty seven assists in the postseason"
    truth = "marek voss recorded eighty seven assists in the postseasn"
    assert score_answer(predicted, truth) is True


def test_fuzzy_below_threshold_fails():
    assert score_answer("the harbor seals won", "the harbor seals lost") is False


def test_fuzzy_similar_but_below_threshold_fails():
    predicted = "the harbor seals won the championship"
    truth = "the harbor seals lost the championship"
    assert score_answer(predicted, truth) is False


def test_score_task_passes_on_matching_answer():
    task = {"answer": "87"}
    model_output = {"answer": "$87.0"}
    result = score_task(task, model_output)
    assert result == {"passed": True, "detail": {"matched": True}}


def test_score_task_fails_on_mismatching_answer():
    task = {"answer": "87"}
    model_output = {"answer": "88"}
    result = score_task(task, model_output)
    assert result == {"passed": False, "detail": {"matched": False}}
