import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import possessions  # noqa: E402

ATL = 1610612737
BOS = 1610612738
CLE = 1610612739

PILOT_PARQUET = Path(
    "/home/hatch/workspace/goals/dime-playground/hidden_files"
    "/possession-log-scratch/nba_play_by_play_2025.parquet"
)


def _row(order, clock, period, team_id, tricode, action, sub="", desc="",
         home="", away="", shot_value=0, sec=None):
    return {
        "order_index": order,
        "clock": clock,
        "period": period,
        "team_id": team_id,
        "team_tricode": tricode,
        "action_type": action,
        "sub_type": sub,
        "description": desc or action,
        "score_home": home,
        "score_away": away,
        "shot_value": shot_value,
        "seconds_remaining": sec,
    }


def _pt(m, s):
    return f"PT{m:02d}M{s:04.1f}S"


def test_period_base():
    assert possessions.period_base(1) == 720.0
    assert possessions.period_base(4) == 720.0
    assert possessions.period_base(5) == 300.0
    assert possessions.period_base(6) == 300.0


def test_elapsed_sec():
    assert possessions.elapsed_sec(1, 720.0) == 0.0
    assert possessions.elapsed_sec(1, 697.0) == 23.0
    assert possessions.elapsed_sec(5, 300.0) == 0.0
    assert possessions.elapsed_sec(5, 290.0) == 10.0


def test_clock_text():
    assert possessions.clock_text("PT12M00.00S") == "12:00"
    assert possessions.clock_text("PT11M37.00S") == "11:37"
    assert possessions.clock_text("PT00M04.30S") == "0:04"


def test_opening_tip_joins_fresh_possession_and_oreb_continues():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st"),
        _row(1, _pt(12, 0), 1, BOS, "BOS", "Jump Ball", "",
             "Jump Ball Horford vs. Capela: Tip to Wallace"),
        _row(2, _pt(11, 43), 1, ATL, "ATL", "Missed Shot", "Jump Shot",
             "MISS Risacher 27' 3PT Jump Shot", shot_value=3),
        _row(3, _pt(11, 42), 1, ATL, "ATL", "Rebound", "Unknown",
             "Risacher REBOUND (Off:1 Def:0)"),
        _row(4, _pt(11, 38), 1, ATL, "ATL", "Missed Shot", "Jump Shot",
             "MISS Johnson 14' Driving Floating Bank Jump Shot",
             shot_value=2),
        _row(5, _pt(11, 37), 1, BOS, "BOS", "Rebound", "Unknown",
             "Horford REBOUND (Off:0 Def:1)"),
    ]
    out = possessions.parse_game_possessions(rows)
    assert len(out) == 1
    first = out[0]
    assert first["possession_number"] == 1
    assert first["period"] == 1
    assert first["off_team_id"] == ATL
    assert first["def_team_id"] == BOS
    assert first["off_abbr"] == "ATL"
    assert first["clock_in"] == "12:00"
    assert first["clock_out"] == "11:37"
    assert first["clock_in_sec"] == 720.0
    assert first["clock_out_sec"] == 697.0
    assert first["points"] == 0
    assert first["events"] == ["PERIOD-START", "TIP", "MISS3", "OREB",
                               "MISS2", "DREB"]


def test_turnover_ends_and_steal_opens_next():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st"),
        _row(1, _pt(10, 57), 1, BOS, "BOS", "Turnover", "Bad Pass",
             "Brown Bad Pass Turnover (P1.T1)", home="0", away="0"),
        _row(2, _pt(10, 57), 1, ATL, "ATL", "", "", "Daniels STEAL (1 STL)"),
        _row(3, _pt(10, 55), 1, ATL, "ATL", "Turnover", "Bad Pass",
             "Daniels Bad Pass Turnover (P1.T2)"),
    ]
    out = possessions.parse_game_possessions(rows)
    assert [p["possession_number"] for p in out] == [1, 2]
    assert out[0]["off_abbr"] == "BOS"
    assert out[0]["events"] == ["PERIOD-START", "TOV"]
    assert out[1]["off_abbr"] == "ATL"
    assert out[1]["events"] == ["NOTE", "TOV"]


def test_and1_free_throws_stay_with_scoring_possession():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st",
             home="18", away="20"),
        _row(1, _pt(2, 54), 1, BOS, "BOS", "Made Shot", "Jump Shot",
             "Tatum 5' Driving Reverse Layup (4 PTS)", home="20",
             away="20", shot_value=2),
        _row(2, _pt(2, 54), 1, ATL, "ATL", "Foul", "Shooting",
             "Mathews S.FOUL (P2.PN) (C.Kirkland)"),
        _row(3, _pt(2, 54), 1, BOS, "BOS", "Free Throw", "Free Throw 1 of 1",
             "Tatum Free Throw 1 of 1 (5 PTS)", home="21", away="20"),
        _row(4, _pt(2, 39), 1, ATL, "ATL", "Made Shot", "Jump Shot",
             "Nance Jr. 26' 3PT Jump Shot (5 PTS)", home="21", away="23",
             shot_value=3),
    ]
    out = possessions.parse_game_possessions(rows)
    assert len(out) == 2
    assert out[0]["events"] == ["PERIOD-START", "MAKE2", "FOUL",
                                "FT1OF1-MAKE"]
    assert out[0]["points"] == 3
    assert out[0]["score_home_in"] == 18
    assert out[0]["score_away_in"] == 20
    assert out[0]["score_home_out"] == 21
    assert out[0]["score_away_out"] == 20
    assert out[1]["off_abbr"] == "ATL"


def test_foul_first_possession_takes_offense_from_free_throws():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st",
             home="5", away="7"),
        _row(1, _pt(9, 11), 1, ATL, "ATL", "Foul", "Shooting",
             "Johnson S.FOUL (P1.T1) (D.Collins)"),
        _row(2, _pt(9, 11), 1, BOS, "BOS", "Free Throw", "Free Throw 1 of 2",
             "Brown Free Throw 1 of 2 (6 PTS)", home="6", away="7"),
        _row(3, _pt(9, 11), 1, BOS, "BOS", "Free Throw", "Free Throw 2 of 2",
             "MISS Brown Free Throw 2 of 2"),
        _row(4, _pt(9, 11), 1, ATL, "ATL", "Rebound", "Unknown",
             "Capela REBOUND (Off:1 Def:2)"),
    ]
    out = possessions.parse_game_possessions(rows)
    assert len(out) == 1
    assert out[0]["off_abbr"] == "BOS"
    assert out[0]["points"] == 1
    assert out[0]["events"] == ["PERIOD-START", "FOUL", "FT1OF2-MAKE",
                                "FT2OF2-MISS", "DREB"]


def test_team_rebound_splits_only_for_defense():
    rows = [
        _row(0, _pt(12, 0), 2, 0, "", "period", "start", "Start of 2nd",
             home="41", away="40"),
        _row(1, _pt(7, 42), 2, BOS, "BOS", "Missed Shot", "Jump Shot",
             "MISS White 28' 3PT Running Jump Shot", shot_value=3),
        _row(2, _pt(7, 41), 2, 0, "", "Rebound", "Unknown",
             "Hawks Rebound"),
        _row(3, _pt(7, 24), 2, ATL, "ATL", "Missed Shot", "Jump Shot",
             "MISS Okongwu 25' 3PT Jump Shot", shot_value=3),
        _row(4, _pt(7, 22), 2, BOS, "BOS", "Rebound", "Unknown",
             "Queta REBOUND (Off:0 Def:1)"),
        _row(5, _pt(7, 6), 2, BOS, "BOS", "Missed Shot", "Jump Shot",
             "MISS Holiday 27' 3PT Running Pull-Up Jump Shot", shot_value=3),
        _row(6, _pt(7, 5), 2, 0, "", "Rebound", "Unknown",
             "CELTICS Rebound"),
        _row(7, _pt(6, 40), 2, BOS, "BOS", "Missed Shot", "Jump Shot",
             "MISS Tatum 27' 3PT Jump Shot", shot_value=3),
        _row(8, _pt(6, 37), 2, BOS, "BOS", "Rebound", "Unknown",
             "Queta REBOUND (Off:2 Def:1)"),
        _row(9, _pt(6, 26), 2, BOS, "BOS", "Missed Shot", "Jump Shot",
             "MISS White 3PT Jump Shot", shot_value=3),
        _row(10, _pt(6, 24), 2, 0, "", "Rebound", "Unknown",
             "Hawks Rebound"),
        _row(11, _pt(6, 4), 2, ATL, "ATL", "Made Shot", "Jump Shot",
             "Daniels 6' Driving Floating Jump Shot (9 PTS)", home="41",
             away="42", shot_value=2),
    ]
    out = possessions.parse_game_possessions(rows)
    assert [p["possession_number"] for p in out] == [1, 2, 3, 4]
    assert out[0]["off_abbr"] == "BOS"
    assert out[0]["events"] == ["PERIOD-START", "MISS3", "TEAM-DREB"]
    assert out[1]["off_abbr"] == "ATL"
    assert out[1]["events"] == ["MISS3", "DREB"]
    assert out[2]["off_abbr"] == "BOS"
    assert out[2]["events"] == ["MISS3", "TEAM-OREB", "MISS3", "OREB",
                               "MISS3", "TEAM-DREB"]
    assert out[3]["off_abbr"] == "ATL"
    assert out[3]["events"] == ["MAKE2"]


def test_midgame_jump_ball_opens_new_possession():
    rows = [
        _row(0, _pt(12, 0), 3, 0, "", "period", "start", "Start of 3rd",
             home="81", away="75"),
        _row(1, _pt(3, 30), 3, ATL, "ATL", "Made Shot", "Jump Shot",
             "Nance Jr. 24' 3PT Jump Shot (11 PTS)", shot_value=3),
        _row(2, _pt(3, 10), 3, BOS, "BOS", "Jump Ball", "",
             "Jump Ball Queta vs. Okongwu: Tip to Hauser"),
        _row(3, _pt(3, 0), 3, BOS, "BOS", "Made Shot", "Jump Shot",
             "Brown 21' Jump Shot (26 PTS)", home="83", away="75",
             shot_value=2),
    ]
    out = possessions.parse_game_possessions(rows)
    assert len(out) == 2
    assert out[1]["events"] == ["TIP", "MAKE2"]
    assert out[1]["off_abbr"] == "BOS"
    assert out[1]["points"] == 2


def test_period_end_closes_and_next_start_opens():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st",
             home="31", away="29"),
        _row(1, _pt(0, 3), 1, ATL, "ATL", "Missed Shot", "Jump Shot",
             "MISS Daniels 59' 3PT Pullup Jump Shot", shot_value=3),
        _row(2, _pt(0, 0), 1, 0, "", "period", "end", "End of 1st"),
        _row(3, _pt(12, 0), 2, 0, "", "period", "start", "Start of 2nd"),
        _row(4, _pt(11, 39), 2, BOS, "BOS", "Made Shot", "Jump Shot",
             "Pritchard 26' 3PT Jump Shot (3 PTS)", home="34", away="29",
             shot_value=3),
    ]
    out = possessions.parse_game_possessions(rows)
    assert len(out) == 2
    assert out[0]["events"] == ["PERIOD-START", "MISS3", "PERIOD-END"]
    assert out[0]["off_abbr"] == "ATL"
    assert (out[0]["score_home_in"], out[0]["score_away_in"]) == (31, 29)
    assert out[1]["events"] == ["PERIOD-START", "MAKE3"]
    assert out[1]["off_abbr"] == "BOS"


def test_next_play_foul_opens_new_possession():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st",
             home="0", away="3"),
        _row(1, _pt(10, 35), 1, BOS, "BOS", "Made Shot", "Pullup Jump shot",
             "Brown 27' 3PT Pullup Jump Shot (3 PTS)", home="3", away="3",
             shot_value=3),
        _row(2, _pt(10, 24), 1, BOS, "BOS", "Foul", "Shooting",
             "Brown S.FOUL (P1.T1) (R.Acosta)"),
        _row(3, _pt(10, 24), 1, ATL, "ATL", "Free Throw", "Free Throw 1 of 2",
             "MISS Capela Free Throw 1 of 2"),
        _row(4, _pt(10, 24), 1, ATL, "ATL", "Free Throw", "Free Throw 2 of 2",
             "MISS Capela Free Throw 2 of 2"),
        _row(5, _pt(10, 24), 1, BOS, "BOS", "Rebound", "Unknown",
             "Tatum REBOUND (Off:0 Def:1)"),
    ]
    out = possessions.parse_game_possessions(rows)
    assert len(out) == 2
    assert out[0]["events"] == ["PERIOD-START", "MAKE3"]
    assert out[0]["off_abbr"] == "BOS"
    assert out[1]["off_abbr"] == "ATL"
    assert out[1]["events"] == ["FOUL", "FT1OF2-MISS", "FT2OF2-MISS",
                               "DREB"]
    assert out[1]["points"] == 0


def test_orphan_period_end_after_close_is_dropped():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st",
             home="100", away="99"),
        _row(1, _pt(0, 1), 1, ATL, "ATL", "Missed Shot", "Jump Shot",
             "MISS Rivers 25' 3PT Jump Shot", shot_value=3),
        _row(2, _pt(0, 1), 1, BOS, "BOS", "Rebound", "Unknown",
             "Lauvergne REBOUND (Off:0 Def:4)"),
        _row(3, _pt(0, 0), 1, 0, "", "period", "end", "End of 1st"),
    ]
    out = possessions.parse_game_possessions(rows)
    assert len(out) == 1
    assert out[0]["events"] == ["PERIOD-START", "MISS3", "DREB"]


def test_unmapped_team_rebound_raises():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st"),
        _row(1, _pt(10, 0), 1, BOS, "BOS", "Missed Shot", "Jump Shot",
             "MISS White 3PT Jump Shot", shot_value=3),
        _row(2, _pt(10, 0), 1, 0, "", "Rebound", "Unknown",
             "Nowhere Rebound"),
    ]
    with pytest.raises(ValueError):
        possessions.parse_game_possessions(rows)


def test_teamless_shot_clock_turnover_resolves_offense_from_description():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st"),
        _row(1, _pt(11, 30), 1, 0, "", "Turnover", "Shot Clock Violation",
             "CAVALIERS Turnover: Shot Clock (T#9)"),
        _row(2, _pt(11, 10), 1, BOS, "BOS", "Made Shot", "Jump Shot",
             "Brown 25' 3PT Jump Shot (3 PTS)", shot_value=3),
        _row(3, _pt(10, 50), 1, CLE, "CLE", "Made Shot", "Jump Shot",
             "Mitchell 12' Jump Shot (2 PTS)", shot_value=2),
    ]
    out = possessions.parse_game_possessions(rows)
    assert [p["possession_number"] for p in out] == [1, 2, 3]
    assert out[0]["off_abbr"] == "CLE"
    assert out[0]["events"] == ["PERIOD-START", "TOV"]
    assert out[1]["off_abbr"] == "BOS"
    assert out[2]["off_abbr"] == "CLE"


def test_teamless_replay_between_possessions_does_not_open():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st"),
        _row(1, _pt(10, 57), 1, BOS, "BOS", "Turnover", "Bad Pass",
             "Brown Bad Pass Turnover (P1.T1)", home="0", away="0"),
        _row(2, _pt(10, 57), 1, 0, "", "Instant Replay", "",
             "Support Ruling - ruling stands"),
        _row(3, _pt(10, 40), 1, ATL, "ATL", "Made Shot", "Jump Shot",
             "Risacher 10' Jump Shot (2 PTS)", home="0", away="2",
             shot_value=2),
    ]
    out = possessions.parse_game_possessions(rows)
    assert len(out) == 2
    assert out[0]["events"] == ["PERIOD-START", "TOV", "REPLAY"]
    assert out[1]["events"] == ["MAKE2"]


def test_teamless_replay_before_first_possession_is_dropped():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "Instant Replay", "",
             "Support Ruling - ruling stands"),
        _row(1, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st"),
        _row(2, _pt(11, 40), 1, ATL, "ATL", "Missed Shot", "Jump Shot",
             "MISS Risacher 3PT Jump Shot", shot_value=3),
        _row(3, _pt(11, 38), 1, BOS, "BOS", "Rebound", "Unknown",
             "Horford REBOUND (Off:0 Def:1)"),
    ]
    out = possessions.parse_game_possessions(rows)
    assert len(out) == 1
    assert out[0]["events"] == ["PERIOD-START", "MISS3", "DREB"]


def test_unresolvable_fragment_folds_into_previous_possession():
    rows = [
        _row(0, _pt(12, 0), 1, 0, "", "period", "start", "Start of 1st",
             home="0", away="0"),
        _row(1, _pt(11, 40), 1, BOS, "BOS", "Made Shot", "Jump Shot",
             "Brown 10' Jump Shot (2 PTS)", home="2", away="0",
             shot_value=2),
        _row(2, _pt(11, 35), 1, 0, "", "Turnover", "",
             "Support Ruling - ruling stands"),
        _row(3, _pt(11, 20), 1, ATL, "ATL", "Made Shot", "Jump Shot",
             "Risacher 10' Jump Shot (2 PTS)", home="2", away="2",
             shot_value=2),
    ]
    out = possessions.parse_game_possessions(rows)
    assert len(out) == 2
    assert out[0]["events"] == ["PERIOD-START", "MAKE2", "TOV"]
    assert out[1]["events"] == ["MAKE2"]


def _pilot_rows():
    import polars as pl

    frame = pl.read_parquet(PILOT_PARQUET)
    game = frame.filter(pl.col("game_id") == "0022400001")
    return sorted(game.to_dicts(), key=lambda r: int(r["order_index"] or 0))


@pytest.mark.skipif(not PILOT_PARQUET.exists(),
                    reason="pilot parquet not downloaded")
def test_pilot_game_possession_count_and_period_split():
    rows = _pilot_rows()
    out = possessions.parse_game_possessions(rows)
    assert len(out) == 198
    per_period: dict[int, int] = {}
    for p in out:
        per_period[int(p["period"])] = per_period.get(int(p["period"]), 0) + 1
    assert per_period == {1: 51, 2: 49, 3: 50, 4: 48}
    assert [p["possession_number"] for p in out] == list(range(1, 199))


@pytest.mark.skipif(not PILOT_PARQUET.exists(),
                    reason="pilot parquet not downloaded")
def test_pilot_game_pinned_possessions():
    rows = _pilot_rows()
    out = possessions.parse_game_possessions(rows)
    by_number = {int(p["possession_number"]): p for p in out}
    first = by_number[1]
    assert first["period"] == 1
    assert first["off_team_id"] == ATL
    assert first["def_team_id"] == BOS
    assert first["clock_in"] == "12:00"
    assert first["clock_out"] == "11:37"
    assert first["points"] == 0
    assert first["events"] == ["PERIOD-START", "TIP", "MISS3", "NOTE",
                               "OREB", "MISS2", "DREB"]
    eighth = by_number[8]
    assert eighth["off_abbr"] == "BOS"
    assert eighth["events"] == ["MAKE3"]
    assert eighth["points"] == 3
    assert (eighth["score_home_in"], eighth["score_away_in"]) == (0, 3)
    assert (eighth["score_home_out"], eighth["score_away_out"]) == (3, 3)
    fourteenth = by_number[14]
    assert fourteenth["off_abbr"] == "BOS"
    assert fourteenth["events"] == ["FOUL", "FT1OF2-MAKE", "FT2OF2-MISS",
                                   "DREB"]
    assert fourteenth["points"] == 1
    thirtysixth = by_number[36]
    assert thirtysixth["events"] == ["MAKE2", "FOUL", "TIMEOUT",
                                    "FT1OF1-MAKE"]
    assert thirtysixth["points"] == 3
    assert (thirtysixth["score_home_in"],
            thirtysixth["score_away_in"]) == (18, 20)
    assert (thirtysixth["score_home_out"],
            thirtysixth["score_away_out"]) == (21, 20)
    sixtyeighth = by_number[68]
    assert sixtyeighth["off_abbr"] == "BOS"
    assert sixtyeighth["events"] == ["NOTE", "MISS3", "TEAM-DREB"]
    assert sixtyeighth["clock_in"] == "7:47"
    assert sixtyeighth["clock_out"] == "7:41"
    sixtyninth = by_number[69]
    assert sixtyninth["off_abbr"] == "ATL"
    assert sixtyninth["events"] == ["SUB", "SUB", "MISS3", "DREB"]
    onethirtyninth = by_number[139]
    assert onethirtyninth["events"] == ["TIP", "MAKE2"]
    assert onethirtyninth["off_abbr"] == "BOS"
    assert (onethirtyninth["score_home_in"],
            onethirtyninth["score_away_in"]) == (81, 75)
    assert (onethirtyninth["score_home_out"],
            onethirtyninth["score_away_out"]) == (83, 75)
    oneninety = by_number[196]
    assert oneninety["events"] == ["TIMEOUT", "FOUL", "TIMEOUT", "TOV"]
    assert oneninety["off_abbr"] == "BOS"
    assert oneninety["clock_in_sec"] == pytest.approx(6.1)
    assert oneninety["clock_out_sec"] == pytest.approx(4.3)
    last = by_number[198]
    assert last["events"] == ["MISS2", "TEAM-OREB", "PERIOD-END"]
    assert last["off_abbr"] == "BOS"
    assert last["clock_in_sec"] == 0.0
    assert last["clock_out_sec"] == 0.0
