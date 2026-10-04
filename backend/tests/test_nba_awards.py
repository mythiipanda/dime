import json
import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.sources import nba_awards as src

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "nba_awards"

LEBRON = 2544
GOBERT = 203497
CRAWFORD = 2037
OLADIPO = 203506
WESTBROOK = 201566


def _payload(player_id: int) -> dict:
    return json.loads(
        (FIXTURES / f"player_awards_{player_id}.json").read_text(
            encoding="utf-8"))


def _frame(player_id: int) -> pl.DataFrame:
    return src.parse_player_awards(_payload(player_id))


def _seasons(frame: pl.DataFrame, award: str) -> list[str]:
    return sorted(frame.filter(pl.col("AWARD") == award)["SEASON"].to_list())


def test_every_fixture_parses_to_the_declared_schema():
    for player_id in (LEBRON, GOBERT, CRAWFORD, OLADIPO, WESTBROOK):
        frame = _frame(player_id)
        assert frame.height > 0, player_id
        assert frame.schema == src.SCHEMA
        assert frame.columns == src.COLUMNS


def test_winners_carry_rank_one_and_no_ballot_detail():
    frame = _frame(LEBRON)
    assert set(frame["RANK"].to_list()) == {1}
    assert set(frame["RANK_LABEL"].to_list()) == {"1"}
    for column in ("POINTS_WON", "POINTS_MAX", "AWARD_SHARE",
                   "VOTES_FIRST", "VOTES_SECOND", "VOTES_THIRD",
                   "COACH", "AGE"):
        assert frame[column].null_count() == frame.height, column
    assert set(frame["SOURCE_URL"].to_list()) == {"nba_api:PlayerAwards"}


def test_lebron_real_winners():
    frame = _frame(LEBRON)
    assert frame["PLAYER"][0] == "LeBron James"
    assert _seasons(frame, "MVP") == [
        "2008-09", "2009-10", "2011-12", "2012-13"]
    assert _seasons(frame, "ROY") == ["2003-04"]
    assert "ALL_NBA" in set(frame["AWARD"].to_list())


def test_gobert_real_dpoy_winners():
    assert _seasons(_frame(GOBERT), "DPOY") == [
        "2017-18", "2018-19", "2020-21", "2023-24"]


def test_crawford_real_sixth_man_winners():
    assert _seasons(_frame(CRAWFORD), "6MOY") == [
        "2009-10", "2013-14", "2015-16"]


def test_oladipo_real_mip_winner():
    assert _seasons(_frame(OLADIPO), "MIP") == ["2017-18"]


def test_westbrook_real_mvp_winner():
    assert _seasons(_frame(WESTBROOK), "MVP") == ["2016-17"]


def test_weekly_monthly_and_all_star_rows_are_not_awards():
    for player_id in (LEBRON, GOBERT, CRAWFORD, OLADIPO, WESTBROOK):
        awards = set(_frame(player_id)["AWARD"].to_list())
        assert awards <= set(src.DESCRIPTION_AWARD.values()), player_id


def test_unmapped_descriptions_are_skipped():
    payload = _payload(LEBRON)
    raw_count = len(payload["resultSets"][0]["rowSet"])
    frame = src.parse_player_awards(payload)
    assert frame.height < raw_count


def test_empty_payload_parses_to_empty_typed_frame():
    frame = src.parse_player_awards({"resultSets": []})
    assert frame.height == 0
    assert frame.schema == src.SCHEMA


def test_module_points_at_the_nba_api_winners_table():
    assert src.SOURCE == "nba_api"
    assert src.TABLE == "silver_award_winners"
    assert set(src.DESCRIPTION_AWARD.values()) == {
        "MVP", "DPOY", "ROY", "6MOY", "MIP",
        "ALL_NBA", "ALL_DEFENSE", "ALL_ROOKIE"}
