"""Near-duplicate cross-seed game-row resolution.

Instinct QA (2026-09-27): exact-dupe dedupe shipped, but near-dupes with
differing stats across seeds still show twice (same player/date/matchup,
OREB 2 vs 3). Decision: collapse to one canonical row -- the most
recently fetched line wins (stat corrections land after the game), then
the most complete stat line, then first occurrence -- and flag the
winner with stat_conflict=True when the seeds genuinely disagreed.

Pure-helper tests are hermetic. No warehouse, no LLM, no network.
"""

import datetime as _dt
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.gamelog import (  # noqa: E402
    _dedupe_games,
    _row_out,
    dedupe_game_log_frame,
)


def _row(game_id="0022500087", date="2025-11-18", matchup="LAL vs. UTA",
         pid=2544, reb=5.0, stl=1.0, fetched_at=None, **kw):
    d = _dt.date.fromisoformat(date)
    row = {
        "player_id": pid, "game_id": game_id, "date": d, "matchup": matchup,
        "opponent": "UTA", "home": True, "wl": "W", "min": 36.0,
        "pts": 20.0, "reb": reb, "ast": 5.0, "stl": stl, "blk": 1.0,
        "tov": 2.0, "pf": 2.0, "fgm": 8.0, "fga": 16.0, "fg3m": 2.0,
        "fg3a": 6.0, "plus_minus": 4.0, "_fetched_at": fetched_at,
    }
    row.update(kw)
    return row


def test_exact_dupes_still_collapse_silently():
    rows = [_row(), _row(game_id="202511180LAL")]  # cross-seed Game_IDs
    out = _dedupe_games(rows)
    assert len(out) == 1
    assert out[0] is rows[0]
    assert "stat_conflict" not in out[0]


def test_near_dupe_latest_fetch_wins_and_flags():
    old = _row(reb=5.0, fetched_at="2025-11-19T08:00:00")
    new = _row(reb=6.0, fetched_at="2025-11-20T08:00:00")  # stat correction
    out = _dedupe_games([old, new])
    assert len(out) == 1
    assert out[0]["reb"] == 6.0
    assert out[0]["stat_conflict"] is True
    # input rows are not mutated
    assert "stat_conflict" not in old and "stat_conflict" not in new


def test_near_dupe_order_independent_latest_fetch_wins():
    old = _row(reb=5.0, fetched_at="2025-11-19T08:00:00")
    new = _row(reb=6.0, fetched_at="2025-11-20T08:00:00")
    out = _dedupe_games([new, old])
    assert len(out) == 1
    assert out[0]["reb"] == 6.0


def test_near_dupe_no_provenance_most_complete_wins():
    sparse = _row(reb=5.0, stl=None)          # seed missing STL
    full = _row(reb=6.0, stl=2.0)             # conflicting REB, but complete
    out = _dedupe_games([sparse, full])
    assert len(out) == 1
    assert out[0]["stl"] == 2.0
    assert out[0]["stat_conflict"] is True


def test_near_dupe_full_tie_first_occurrence_wins():
    a = _row(reb=5.0)
    b = _row(reb=6.0)
    out = _dedupe_games([a, b])
    assert len(out) == 1
    assert out[0] is not None and out[0]["stat_conflict"] is True
    # stable: first occurrence kept when nothing distinguishes them
    assert out[0]["reb"] == 5.0


def test_distinct_games_same_day_kept():
    rows = [_row(matchup="LAL vs. UTA"), _row(matchup="LAL vs. BOS")]
    out = _dedupe_games(rows)
    assert len(out) == 2


def test_distinct_players_same_game_kept():
    rows = [_row(pid=2544), _row(pid=203999)]
    out = _dedupe_games(rows)
    assert len(out) == 2


def test_row_out_surfaces_conflict_flag():
    out = _dedupe_games([_row(reb=5.0), _row(reb=6.0)])
    rendered = _row_out(out[0])
    assert rendered["stat_conflict"] is True
    clean = _row_out(_dedupe_games([_row(), _row()])[0])
    assert "stat_conflict" not in clean


def _frame_row(game_id="0022500087", date="NOV 18, 2025", matchup="LAL vs. UTA",
               pid=2544, oreb=2, fetched_at="2025-11-19T08:00:00"):
    return {
        "Player_ID": pid, "Game_ID": game_id, "GAME_DATE": date,
        "MATCHUP": matchup, "WL": "W", "MIN": 36.0, "OREB": oreb,
        "REB": 5, "PTS": 20, "AST": 5,
        "_source": "sportsdataverse", "_season": "2025-26",
        "_fetched_at": fetched_at, "_entity": "player",
    }


def test_frame_exact_dupes_collapse_keep_first():
    frame = pl.DataFrame([_frame_row(), _frame_row(game_id="202511180LAL")])
    out = dedupe_game_log_frame(frame)
    assert out.height == 1
    assert out.columns == frame.columns  # no columns added or removed


def test_frame_near_dupe_latest_fetch_wins():
    old = _frame_row(oreb=2, fetched_at="2025-11-19T08:00:00")
    new = _frame_row(oreb=3, fetched_at="2025-11-20T08:00:00",
                     game_id="202511180LAL")
    out = dedupe_game_log_frame(pl.DataFrame([old, new]))
    assert out.height == 1
    assert out["OREB"][0] == 3
    assert out.columns == pl.DataFrame([old]).columns


def test_frame_near_dupe_mixed_date_formats_group_together():
    old = _frame_row(date="NOV 18, 2025", oreb=2,
                     fetched_at="2025-11-19T08:00:00")
    new = _frame_row(date="2025-11-18", oreb=3,
                     fetched_at="2025-11-20T08:00:00")
    out = dedupe_game_log_frame(pl.DataFrame([old, new]))
    assert out.height == 1
    assert out["OREB"][0] == 3


def test_frame_preserves_row_order():
    a1 = _frame_row(date="NOV 20, 2025", matchup="LAL vs. BOS")
    b1 = _frame_row(date="NOV 18, 2025", matchup="LAL vs. UTA", oreb=2,
                    fetched_at="2025-11-19T08:00:00")
    b2 = _frame_row(date="NOV 18, 2025", matchup="LAL vs. UTA", oreb=3,
                    fetched_at="2025-11-20T08:00:00")
    out = dedupe_game_log_frame(pl.DataFrame([a1, b1, b2]))
    assert out.height == 2
    assert out["MATCHUP"].to_list() == ["LAL vs. BOS", "LAL vs. UTA"]
    assert out["OREB"].to_list() == [2, 3]


def test_frame_team_games_entity_key():
    r1 = _frame_row(oreb=2, fetched_at="2025-11-19T08:00:00")
    r2 = _frame_row(oreb=3, fetched_at="2025-11-20T08:00:00")
    for r in (r1, r2):
        r["Team_ID"] = 14
        del r["Player_ID"]
    out = dedupe_game_log_frame(pl.DataFrame([r1, r2]))
    assert out.height == 1
    assert out["OREB"][0] == 3


def test_frame_without_matchup_falls_back_to_exact_unique():
    r1 = _frame_row(oreb=2)
    r2 = _frame_row(oreb=3)
    del r1["MATCHUP"]
    del r2["MATCHUP"]
    out = dedupe_game_log_frame(pl.DataFrame([r1, r2]))
    # no MATCHUP: can't tell near-dupe from distinct games; keep both
    assert out.height == 2


def test_frame_non_gamelog_unchanged():
    frame = pl.DataFrame([{"a": 1}, {"a": 1}])
    out = dedupe_game_log_frame(frame)
    assert out.height == 2
