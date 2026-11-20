import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import stints


HOME = 1610612759
AWAY = 1610612752
HOME_FLOOR = [1628368, 1630170, 1630577, 1641705, 1642264]
AWAY_FLOOR = [1626157, 1628384, 1628404, 1628969, 1628973]
ALT_HOME = [1628368, 1630170, 1630577, 1641705, 200001]


def _poss(n, period, start_sec, end_sec, offense, points, off, deff):
    row = {
        "possession_number": n,
        "period": period,
        "start_seconds_remaining": start_sec,
        "end_seconds_remaining": end_sec,
        "offense_team_id": offense,
        "points": points,
    }
    for i, pid in enumerate(off, 1):
        row[f"off_player_{i}"] = pid
    for i, pid in enumerate(deff, 1):
        row[f"def_player_{i}"] = pid
    return row


def _game_rows():
    return [
        _poss(1, 1, 720.0, 692.0, AWAY, 0, AWAY_FLOOR, HOME_FLOOR),
        _poss(2, 1, 672.0, 668.0, HOME, 0, HOME_FLOOR, AWAY_FLOOR),
        _poss(3, 1, 645.0, 643.0, AWAY, 0, AWAY_FLOOR, HOME_FLOOR),
        _poss(4, 1, 626.0, 626.0, HOME, 0, HOME_FLOOR, AWAY_FLOOR),
        _poss(5, 1, 626.0, 595.0, AWAY, 0, AWAY_FLOOR, HOME_FLOOR),
        _poss(6, 1, 595.0, 584.0, HOME, 2, HOME_FLOOR, AWAY_FLOOR),
        _poss(7, 1, 570.0, 570.0, AWAY, 3, AWAY_FLOOR, HOME_FLOOR),
        _poss(8, 1, 555.0, 555.0, HOME, 0, HOME_FLOOR, AWAY_FLOOR),
        _poss(9, 1, 538.0, 535.0, AWAY, 0, AWAY_FLOOR, HOME_FLOOR),
        _poss(10, 1, 527.0, 523.0, HOME, 2, HOME_FLOOR, AWAY_FLOOR),
        _poss(11, 1, 501.0, 498.0, AWAY, 0, AWAY_FLOOR, HOME_FLOOR),
        _poss(12, 1, 493.0, 490.0, HOME, 0, HOME_FLOOR, AWAY_FLOOR),
        _poss(13, 1, 488.0, 488.0, AWAY, 2, AWAY_FLOOR, HOME_FLOOR),
        _poss(14, 1, 469.0, 469.0, HOME, 2, HOME_FLOOR, AWAY_FLOOR),
        _poss(15, 1, 449.0, 447.0, AWAY, 0, AWAY_FLOOR, ALT_HOME),
    ]


def _build(rows=None):
    return stints.build_stints(
        "0042500405", rows if rows is not None else _game_rows(),
        HOME, AWAY, "SAS", "NYK")


def test_clock_text_regulation():
    assert stints.clock_text(1, 720.0) == "12:00"
    assert stints.clock_text(1, 469.0) == "7:49"
    assert stints.clock_text(4, 0.0) == "0:00"


def test_clock_text_overtime_base():
    assert stints.clock_text(5, 300.0) == "5:00"
    assert stints.clock_text(5, 270.0) == "4:30"


def test_elapsed_sec_regulation_and_overtime():
    assert stints.elapsed_sec(1, 720.0) == 0.0
    assert stints.elapsed_sec(1, 469.0) == 251.0
    assert stints.elapsed_sec(4, 0.0) == 2880.0
    assert stints.elapsed_sec(5, 270.0) == 2910.0


def test_pilot_stint_one_matches_hand_check():
    rows = _build()
    first = rows[0]
    assert first == {
        "game_id": "0042500405",
        "stint_number": 1,
        "poss_start": 1,
        "poss_end": 14,
        "period_in": 1,
        "clock_in": "12:00",
        "period_out": 1,
        "clock_out": "7:49",
        "clock_in_sec": 720.0,
        "clock_out_sec": 469.0,
        "duration_sec": 251.0,
        "home_team_id": HOME,
        "away_team_id": AWAY,
        "home_abbr": "SAS",
        "away_abbr": "NYK",
        "home_player_1": 1628368,
        "home_player_2": 1630170,
        "home_player_3": 1630577,
        "home_player_4": 1641705,
        "home_player_5": 1642264,
        "away_player_1": 1626157,
        "away_player_2": 1628384,
        "away_player_3": 1628404,
        "away_player_4": 1628969,
        "away_player_5": 1628973,
        "score_home_in": 0,
        "score_away_in": 0,
        "score_home_out": 6,
        "score_away_out": 5,
        "home_swing": 1,
    }


def test_floor_change_opens_new_stint():
    rows = _build()
    assert len(rows) == 2
    assert [r["stint_number"] for r in rows] == [1, 2]
    second = rows[1]
    assert second["poss_start"] == 15
    assert second["poss_end"] == 15
    assert second["clock_in"] == "7:29"
    assert second["score_home_in"] == 6
    assert second["score_away_in"] == 5


def test_empty_possessions_yields_no_stints():
    assert _build([]) == []


def test_null_floor_breaks_run_but_keeps_score():
    rows = _game_rows()
    broken = dict(rows[5])
    broken["off_player_3"] = None
    rows[5] = broken
    out = _build(rows)
    assert [r["stint_number"] for r in out] == [1, 2, 3]
    assert out[0]["poss_end"] == 5
    assert out[1]["poss_start"] == 7
    assert out[-1]["score_home_out"] == 6
    assert out[-1]["score_away_out"] == 5


def test_unordered_input_sorted_by_possession():
    rows = _build(list(reversed(_game_rows())))
    assert rows[0]["poss_start"] == 1
    assert rows[0]["poss_end"] == 14
