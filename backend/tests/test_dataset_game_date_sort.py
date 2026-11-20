import datetime as _dt
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyst.dataset_engine import _sort_frame_by_game_date


def test_mixed_format_sorts_by_actual_date_with_row_association():
    frame = pl.DataFrame(
        {"GAME_DATE": ["Oct 21, 2025", "2025-11-02", "Nov 10, 2025", "2025-10-25"], "PTS": [1, 2, 3, 4]}
    )
    out = _sort_frame_by_game_date(frame)
    assert out["GAME_DATE"].to_list() == ["Nov 10, 2025", "2025-11-02", "2025-10-25", "Oct 21, 2025"]
    assert out["PTS"].to_list() == [3, 2, 4, 1]
    assert out.columns == frame.columns


def test_homogeneous_iso_sorts_descending():
    frame = pl.DataFrame({"GAME_DATE": ["2025-10-21", "2025-11-02", "2025-10-25"], "PTS": [1, 2, 3]})
    out = _sort_frame_by_game_date(frame)
    assert out["GAME_DATE"].to_list() == ["2025-11-02", "2025-10-25", "2025-10-21"]
    assert out["PTS"].to_list() == [2, 3, 1]


def test_homogeneous_long_sorts_descending():
    frame = pl.DataFrame({"GAME_DATE": ["Oct 21, 2025", "Nov 10, 2025", "Oct 25, 2025"], "PTS": [1, 2, 3]})
    out = _sort_frame_by_game_date(frame)
    assert out["GAME_DATE"].to_list() == ["Nov 10, 2025", "Oct 25, 2025", "Oct 21, 2025"]
    assert out["PTS"].to_list() == [2, 3, 1]


def test_invalid_and_null_dates_sort_last():
    frame = pl.DataFrame({"GAME_DATE": ["Oct 21, 2025", "not-a-date", "2025-11-02", None], "PTS": [1, 2, 3, 4]})
    out = _sort_frame_by_game_date(frame)
    assert out["GAME_DATE"].to_list()[:2] == ["2025-11-02", "Oct 21, 2025"]
    assert out["PTS"].to_list()[:2] == [3, 1]
    tail = out["GAME_DATE"].to_list()[2:]
    assert None in tail or "not-a-date" in tail
    assert out["GAME_DATE"][-1] is None
    assert set(out["PTS"].to_list()[2:]) == {2, 4}


def test_all_invalid_preserves_input_order():
    frame = pl.DataFrame({"GAME_DATE": ["bad", "also-bad", None], "PTS": [7, 8, 9]})
    out = _sort_frame_by_game_date(frame)
    assert out["GAME_DATE"].to_list() == ["bad", "also-bad", None]
    assert out["PTS"].to_list() == [7, 8, 9]
    assert out.columns == frame.columns


def test_date_typed_game_date_is_unchanged():
    frame = pl.DataFrame(
        {"GAME_DATE": [_dt.date(2025, 10, 21), _dt.date(2025, 11, 2)], "PTS": [1, 2]}
    )
    out = _sort_frame_by_game_date(frame)
    assert out["GAME_DATE"].to_list() == [_dt.date(2025, 10, 21), _dt.date(2025, 11, 2)]
    assert out["PTS"].to_list() == [1, 2]
    assert out.columns == frame.columns


def _frame_row(game_id, date, matchup, oreb):
    return {
        "Player_ID": 2544,
        "Game_ID": game_id,
        "GAME_DATE": date,
        "MATCHUP": matchup,
        "WL": "W",
        "MIN": 36.0,
        "OREB": oreb,
        "REB": 5,
        "PTS": 20,
        "AST": 5,
        "_source": "synthetic",
        "_season": "2025-26",
        "_fetched_at": "2025-11-19T08:00:00",
        "_entity": "player",
    }


def test_sorted_frame_dedupe_inherits_most_recent_first():
    from shared.tools.gamelog import dedupe_game_log_frame

    rows = [
        _frame_row("G1", "Oct 21, 2025", "LAL vs. UTA", 1),
        _frame_row("G2", "2025-11-02", "LAL vs. BOS", 2),
        _frame_row("G3", "Nov 10, 2025", "LAL vs. CHI", 3),
    ]
    sorted_frame = _sort_frame_by_game_date(pl.DataFrame(rows))
    assert sorted_frame["GAME_DATE"].to_list() == ["Nov 10, 2025", "2025-11-02", "Oct 21, 2025"]
    out = dedupe_game_log_frame(sorted_frame)
    assert out["GAME_DATE"].to_list() == ["Nov 10, 2025", "2025-11-02", "Oct 21, 2025"]
    assert out["OREB"].to_list() == [3, 2, 1]
