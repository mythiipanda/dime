from .scoring import groundedness, numeric_acc, tool_f1


def test_last_name_loophole_closed():
    assert numeric_acc(
        {"leader_value": 32.1, "leader_name": "LeBron James"},
        "LeBron James leads the league") == 0.0


def test_numeric_hit_still_works():
    assert numeric_acc(
        {"leader_value": 32.1}, "He averages 32.1 points") == 1.0


def test_season_stripped():
    assert numeric_acc(
        {"rank": 26}, "He ranks 1st in the 2025-26 season") == 0.0


def test_substring_guard():
    assert numeric_acc({"games": 5}, "He played 25 games") == 0.0


def test_sentence_final_period_matches():
    assert numeric_acc(
        {"percentile": 98.7}, "His percentile rank is 98.7.") == 1.0
    assert numeric_acc(
        {"percentile": 98.7}, "His percentile rank is 98.75.") == 0.0


def test_groundedness_season_only():
    assert groundedness(
        "Shai leads in 2025-26", '{"_season": "2025-26"}') == 1.0


def test_groundedness_rounding():
    assert groundedness(
        "He averages 25.5 points", '{"pts": 25.47}') == 1.0


def test_groundedness_catches_fabrication():
    assert groundedness(
        "He averages 99.9 points", '{"pts": 25.47}') == 0.0


def test_tool_f1_lookup_match():
    assert tool_f1(["get_leaders", "resolve_entity"], ["lookup"]) == 1.0


def test_tool_f1_trade_mismatch():
    assert tool_f1(["get_trade_check"], ["lookup"]) == 0.0
