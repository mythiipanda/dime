from .driver import _observed_pred_args
from .scoring import groundedness, numeric_acc, season_consistency, tool_f1


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


def test_half_up_boundary_negative():
    # -3.15 as a float is really -3.1499999..., so f"{v:.1f}" yields
    # "-3.1"; a correct half-up answer of "-3.2" must still match.
    assert numeric_acc({"net": -3.15}, "Net rating is -3.2") == 1.0


def test_half_up_boundary_positive():
    assert numeric_acc({"value": 2.25}, "The value is 2.3") == 1.0


def test_half_up_boundary_does_not_broaden():
    # 2.24 is not on a .x5 boundary, so "2.3" must not be emitted.
    assert numeric_acc({"value": 2.24}, "The value is 2.3") == 0.0


def test_groundedness_season_only():
    assert groundedness(
        "Shai leads in 2025-26", '{"_season": "2025-26"}') == 1.0


def test_groundedness_rounding():
    assert groundedness(
        "He averages 25.5 points", '{"pts": 25.47}') == 1.0


def test_groundedness_catches_fabrication():
    assert groundedness(
        "He averages 99.9 points", '{"pts": 25.47}') == 0.0


def test_season_consistency_wrong_season_zero():
    # Instinct QA 2026-09-27 repro: the RIGHT number with WRONG-season
    # phrasing scored 1.0 because numeric_acc stripped season strings.
    assert season_consistency(
        {"ts_pct": 58.8, "season": "2024-25"},
        "The Celtics posted 58.8% TS in the 2025-26 regular season.",
    ) == 0.0


def test_season_consistency_right_season_one():
    assert season_consistency(
        {"ts_pct": 58.8, "season": "2024-25"},
        "Boston's true shooting percentage was 58.8% in 2024-25.",
    ) == 1.0


def test_season_consistency_no_mention_no_penalty():
    assert season_consistency(
        {"ts_pct": 58.8, "season": "2024-25"},
        "The Celtics posted 58.8% TS.",
    ) == 1.0


def test_season_consistency_long_and_dash_forms():
    assert season_consistency(
        {"wins": 68, "season": "2024-25"},
        "OKC won 68 games in the 2024-2025 season.",
    ) == 1.0
    assert season_consistency(
        {"wins": 68, "season": "2024-25"},
        "OKC won 68 games in 2024\u201325.",
    ) == 1.0


def test_season_consistency_no_season_fact():
    assert season_consistency({}, "in 2025-26") == 1.0


def test_numeric_acc_gates_wrong_season_attribution():
    assert numeric_acc(
        {"ts_pct": 58.8, "season": "2024-25"},
        "The Celtics posted a 58.8% true shooting mark in 2025-26.",
    ) == 0.0
    assert numeric_acc(
        {"ts_pct": 58.8, "season": "2024-25"},
        "Boston's true shooting percentage was 58.8% in 2024-25.",
    ) == 1.0
    assert numeric_acc(
        {"ts_pct": 58.8, "season": "2024-25"},
        "The Celtics posted 58.8% TS.",
    ) == 1.0


def test_tool_f1_lookup_match():
    assert tool_f1(["get_leaders", "resolve_entity"], ["lookup"]) == 1.0


def test_tool_f1_trade_mismatch():
    assert tool_f1(["get_trade_check"], ["lookup"]) == 0.0


def test_observed_pred_args_abbrs():
    calls = [{"name": "get_game_prediction",
              "args": {"summary": "a=LAL, b=BOS"}}]
    assert _observed_pred_args(calls) == ("LAL", "BOS")


def test_observed_pred_args_last_call_wins():
    calls = [{"name": "get_game_prediction",
              "args": {"summary": "a=NYK, b=CHI"}},
             {"name": "get_game_prediction",
              "args": {"summary": "a=LAL, b=BOS"}}]
    assert _observed_pred_args(calls) == ("LAL", "BOS")


def test_observed_pred_args_full_names():
    calls = [{"name": "get_game_prediction",
              "args": {"summary": "a=Los Angeles Lakers, b=Boston Celtics"}}]
    assert _observed_pred_args(calls) == ("LAL", "BOS")


def test_observed_pred_args_none():
    assert _observed_pred_args(
        [{"name": "get_leaders",
          "args": {"summary": "cat=PTS"}}]) is None
    assert _observed_pred_args(
        [{"name": "get_game_prediction",
          "args": {"summary": "get_game_prediction"}}]) is None
    assert _observed_pred_args(
        [{"name": "get_game_prediction",
          "args": {"summary": "a=ZZZ, b=BOS"}}]) is None
