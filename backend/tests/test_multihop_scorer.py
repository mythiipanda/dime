import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.evals.multihop_scorer import score, score_batch


def test_exact_int_match():
    assert score(27, 27) == 1.0


def test_exact_numeric_strings_match():
    assert score("27.5", "27.5") == 1.0


def test_numeric_whitespace_stripped():
    assert score("  27.5 ", "27.5") == 1.0


def test_numeric_within_tolerance_passes():
    assert score("100.005", "100") == 1.0


def test_numeric_outside_tolerance_fails():
    assert score("100.02", "100") == 0.0


def test_numeric_zero_gold_requires_exact_zero():
    assert score("0", "0") == 1.0
    assert score("0.0", 0) == 1.0
    assert score("0.0001", "0") == 0.0


def test_numeric_zero_gold_outside_tolerance():
    assert score("0.001", "0") == 0.0


def test_numeric_negative_match():
    assert score("-5.5", "-5.5") == 1.0


def test_bool_is_not_number_int_vs_true():
    assert score(1, True) == 0.0


def test_bool_is_not_number_true_vs_one_string():
    assert score(True, "1") == 0.0


def test_string_case_and_whitespace_normalized():
    assert score("  Los Angeles   Lakers ", "los angeles lakers") == 1.0


def test_string_exact_name_match():
    assert score("Jayson Tatum", "jayson tatum") == 1.0


def test_string_mismatch_fails():
    assert score("Lakers", "Celtics") == 0.0


def test_mixed_number_and_text_fails():
    assert score("27.5", "Lakers") == 0.0


def test_mixed_text_and_number_fails():
    assert score("Lakers", "27.5") == 0.0


def test_score_returns_float():
    result = score("Lakers", "Celtics")
    assert isinstance(result, float)
    assert result in (0.0, 1.0)


def test_score_batch_mixed_pairs():
    assert score_batch([("27.5", "27.5"), ("Lakers", "Celtics")]) == [1.0, 0.0]


def test_score_batch_empty():
    assert score_batch([]) == []
